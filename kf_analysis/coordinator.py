import logging, time
from bs4 import BeautifulSoup
from . import analyser, utils
from .service import Client, Storage


logger = logging.getLogger("kf-analysis")


class KFanalysis:
# 自动流程分三层，最底层为主题信息获取，可被单独调用
# 将板块视为多次主题信息获取的调用，将整体视为多次板块的调用
    def __init__(self, config, db_path="kf.db"):
        self.config = config
        self.client = Client(config)
        self.storage = Storage(db_path)

    def get_oneboard_url(self, fid, disp=False):
        def get_onepage_url(page):
            url = f"https://bbs.kfpromax.com/thread.php?fid={fid}&orderway=lastpost&page={page}"
            try:
                response = self.client.get(url)
                if response.status_code != 200:
                    logger.error(f"板块 {fid} 访问失败，状态码 {response.status_code}")
                    return []
                return analyser.parse_board_page(BeautifulSoup(response.content, "lxml"))
            except Exception as e:
                logger.error(f"板块 {fid} 访问失败，错误信息 {e}", exc_info=True)
                return []
        result = []
        print()
        for page in range(1, 11):
            if disp: print(f"板块 {fid} 第 {page} 页访问成功")
            result += get_onepage_url(page)
            time.sleep(self.config.timegap_board_in)
        result = get_onepage_url(1) + result
        # 为避免翻页期间有帖子浮动到首页导致提取不完全，最后再获取一次第一页的数据，插入列表最前并去重
        # 这种方法是建立在【10×timegap_board_in 秒内新增或浮动主题帖数量不超过该板块的单页容量】假设上的
        seen = {}
        for x in result:
            seen.setdefault(x[0], x)
        result_dedup = list(seen.values())
        if disp: print(f"↑ 板块 {fid} 解析完成，提取到 {len(result_dedup)} 条主题\n")
        return result_dedup

    def get_onetopic_info(self, topic_id, topic_sf, disp=False, index=0, total=1, force=False):
        # 访问并解析一个 topic，始终获取第 1 页用于解析 topic 头信息（用于单独调用时的增量判断）
        # force 参数缺省时为普通增量更新，即便此前数据库中不存在对应 topic 条目也能正常运行
        # force 参数为 True 时为强制全量更新，会覆盖数据库中对应 topic 条目中的旧数据
        # 关于返回值：无更新=None；有更新=topic_info；失败=False；帖子存在但无法访问="closed"或"deleted"
        # 关于返回值：在普通增量更新模式下，topic_info 会附带 incremental 标记，用于帮助上层调用决定存储策略
        topic_url = utils.topic_url(topic_id, topic_sf)
        response = self.client.get(topic_url)
        if response.status_code != 200:
            logger.error(f"帖子 ({topic_id}, {topic_sf}) 访问失败，状态码 {response.status_code}")
            return False
        soup = BeautifulSoup(response.content, "lxml")
        status = analyser.check_page_status(soup)
        if status in ("closed", "deleted"): return status
        if status == "incorrect":
            logger.error(f"帖子不存在或安全码错误 ({topic_id}, {topic_sf})，状态码 {response.status_code}")
            return False
        topic_info = analyser.parse_topic_info(soup, topic_id, topic_sf)
        db_total = self.storage.get_topic_floor_count(topic_id)
        page_sources = [(1, response.content)]
        current_page = topic_url
        if force or db_total == 0:
            page_list = range(2, (topic_info["reply_count"] - 1) // 20 + 2)
            username_dict = None
        elif db_total < topic_info["reply_count"]:
            page_list = range(max(db_total // 20 + 1, 2), (topic_info["reply_count"] - 1) // 20 + 2)
            username_dict = {u: 1 for u in self.storage.get_topic_usernames(topic_id)}
        else:
            return None
        def echo():
            print(f"{index+1}/{total}  {len(page_sources):>5} / {len(page_list)+1:<5}  "
                  f"{current_page}  {topic_info['topic_title']}")
        if disp: echo()
        for page in page_list:
            current_page = f"{topic_url}&page={page}"
            response = self.client.get(current_page)
            if response.status_code != 200:
                logger.error(f"帖子 ({topic_id}, {topic_sf}) 访问失败，状态码 {response.status_code}")
                continue
            page_sources.append((page, response.content))
            if disp: echo()
            time.sleep(self.config.timegap_topic_in)
        replylist = analyser.parse_replies([content for _, content in page_sources],
                                           topic_id, topic_sf, username_dict)
        topic_info["reply_list"] = replylist
        if username_dict is not None:
            topic_info["incremental"] = True
        return topic_info

    def fetch_onetopic(self, topic_id, topic_sf, listing_count=None, force=False, disp=False, index=0, total=1):
        if not force and listing_count is not None and self.storage.should_skip(topic_id, listing_count): return None
        # 前置整体跳过描述A：强制全量抓取时不跳过；独立调用时不跳过；已存楼层数大于将存数据时不跳过
        # 前置整体跳过描述B：仅当调用来自上层函数、普通增量抓取且无增量时，进行前置跳过
        # 后置楼层跳过：指下层函数内部的跳过逻辑（即增量判断逻辑）
        try:
            data = self.get_onetopic_info(topic_id, topic_sf, disp=disp, index=index, total=total, force=force)
        except Exception as e:
            logger.error(f"帖子 ({topic_id}, {topic_sf}) 访问失败，错误信息 {e}", exc_info=True)
            return False
        # 帖子被关闭或被删除标志，代表帖子曾真实存在，最小化条目存储
        if data in ("closed", "deleted") and not self.storage.has_topic(topic_id):
            self.storage.insert_closed_topic(topic_id, topic_sf, status=data)
            return data
        # 链接键入错误与其他失败态，帖子曾真实存在性为否或无法判定，不进行条目存储
        if not isinstance(data, dict):
            return data
        if data.get("incremental"):
            self.storage.save_incremental_tx(data)
        else:
            self.storage.save_topic_tx(data)
        time.sleep(self.config.timegap_topic_out)
        return data

    def fetch_board(self, fid, force=False, disp=True):
        board_urls = self.get_oneboard_url(fid, disp=disp)
        for index, (topic_id, topic_sf, listing_count) in enumerate(board_urls):
            self.fetch_onetopic(topic_id, topic_sf, listing_count=listing_count,
                                force=force, disp=disp, index=index, total=len(board_urls))

    def fetch_all(self, force=False, disp=True):
        for _, fid in self.config.boardlist:
            self.fetch_board(fid, force=force, disp=disp)
            time.sleep(self.config.timegap_board_out)

    def get_topic_usernames(self, topic_id, topic_sf, dedup=False):
        data = self.get_onetopic_info(topic_id, topic_sf, force=True)
        # "closed"/"deleted"/"incorrect"/False 标志原样返回
        if not isinstance(data, dict):
            return data
        usernames = [r["username"] for r in data["reply_list"]]
        if dedup:
            usernames = list(dict.fromkeys(usernames))
        return usernames

    def get_topic_json(self, topic_id, topic_sf):
        data = self.get_onetopic_info(topic_id, topic_sf, force=True)
        # "closed"/"deleted"/"incorrect"/False 标志原样返回
        if not isinstance(data, dict):
            return data
        topic = {k: data[k] for k in ("topic_id", "topic_sf", "reply_count", "topic_title",
                                      "topic_time", "view_count", "tui_count", "board_id", "board_name")}
        reply_keys = ("reply_id", "username", "homepage_id", "homepage_sf", "reply_box_color",
                      "floor", "reply_time", "status", "reply_text", "image_list",
                      "complete", "keyword_list", "hidden_content")
        return {"topic": topic, "replies": [{k: r[k] for k in reply_keys} for r in data["reply_list"]]}

    def get_homepage(self, uid, sf):
        url = f"https://bbs.kfpromax.com/profile.php?action=show&uid={uid}&sf={sf}"
        response = self.client.get(url)
        if response.status_code != 200:
            logger.error(f"用户主页 (uid={uid}, sf={sf}) 访问失败，状态码 {response.status_code}")
            return False
        return analyser.parse_profile_page(BeautifulSoup(response.content, "lxml"))
