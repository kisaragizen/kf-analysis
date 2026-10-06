import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from bs4 import BeautifulSoup
from . import analyser, utils
from .service import Client, Storage

logger = logging.getLogger("kf-analysis")
# 记录了各板块上次完成完整扫描时间的日志文件（早停功能依赖）
SWEEP_LOG = Path(__file__).with_name("sweep_log.json")
SWEEP_LOG_TEMP = SWEEP_LOG.with_name(SWEEP_LOG.name + ".tmp")


def load_sweep_log():
    if not SWEEP_LOG.exists():
        return {}
    with open(SWEEP_LOG, encoding="utf-8") as f:
        return json.load(f)


def get_sweep_time(fid):
    entry = load_sweep_log().get("boards", {}).get(str(fid))
    return entry["last_time"] if entry else -1


def record_sweep(fid, name, timestamp):
    data = load_sweep_log()
    data.setdefault("version", 1)
    boards = data.setdefault("boards", {})
    boards[str(fid)] = {"name": name, "last_time": timestamp}
    with open(SWEEP_LOG_TEMP, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    SWEEP_LOG_TEMP.replace(SWEEP_LOG)


# 板块名有两种：①板块索引栏显示名称；②板块真实名称
# 前者在 configure.json 中有定义（boardlist），后者定义如下
BOARD_IDS = {
    "论坛管理": 4,
    "自由讨论区": 5,
    "无限制资源区": 9,
    "Galgame BitTorrent区": 16,
    "游戏安装疑难互助": 24,
    "寻求资源": 36,
    "Galgame 网络硬盘区": 41,
    "GalGame综合讨论区": 52,
    "个人日记": 56,
    "GAL本子区": 57,
    "CG画册资源共享区": 67,
    "ACG音乐资源共享区": 68,
    "动漫综合讨论区": 84,
    "电子产品讨论区": 86,
    "ACG实物讨论区": 87,
    "动画资源共享区": 92,
    "自绘美少女": 94,
    "图片/作品出处询问版": 96,
    "GalGame推荐区": 102,
    "GalGame新作动态": 106,
    "文字类作品区": 115,
    "水楼林立": 125,
    "漫画轻小说共享区": 127,
    "LIVE类资源分享区": 163,
}


class KFanalysis:
    # 自动流程分三层，最底层为主题信息获取，可被单独调用
    # 将板块视为多次主题信息获取的调用，将整体视为多次板块的调用
    def __init__(self, config, db_path="kf.db"):
        self.config = config
        self.client = Client(config)
        self.storage = Storage(db_path)

    def get_oneboard_url(
        self,
        fid,
        disp=False,
        detail=False,
        order="lastpost",
        pages=10,
        recheck=True,
        early_stop=False,
    ):
        # detail=False 时的返回值：(topic_id, topic_sf, reply_num)
        # detail=True 时的返回值：{topic_id, topic_sf, topic_poster, topic_labels, topic_title, reply_num, view_count}
        # pages 为抓取页数，order=lastpost 为最后回复序，order=postdate 为主题发表序
        # 早停功能指的是，当遇到某页满足“①页中所有主题均无增量；②页中所有主题入库时间均不大于 last_time（该板块上次全量成功时间）”时
        # 为什么要加入判定条件②呢？为了防止“用户在本次全量前手动 fetch 过大量主题，且这些主题刚好没有任何后续增量且挤满一页”的极端情况
        # self.recordable 表示本次扫描能否作为板块扫描时间日志的依据，任何一页抓取失败都会将其置假
        result = []
        self.recordable = True
        last_sweep = get_sweep_time(fid) if early_stop else -1

        def get_onepage_url(page):
            url = (
                "https://bbs.kfpromax.com/thread.php?"
                f"fid={fid}&orderway={order}&page={page}"
            )
            try:
                response = self.client.get(url)
                if response.status_code != 200:
                    logger.error(
                        utils.log_error(
                            "E101", "coordinator.get_oneboard_url", f"板块 ({fid})"
                        )
                    )
                    return []
                return analyser.parse_board_page(
                    BeautifulSoup(response.content, "lxml"),
                    detail=detail,
                )
            except Exception:
                logger.error(
                    utils.log_error(
                        "E102", "coordinator.get_oneboard_url", f"板块 ({fid})"
                    )
                )
                return []

        if disp:
            print("\n=======================================================\n")
        for page in range(1, min(11, pages + 1)):
            rows = get_onepage_url(page)
            if not rows:
                if disp:
                    print(f"板块 {fid} 第 {page} 页访问失败")
                self.recordable = False
            else:
                if disp:
                    print(f"板块 {fid} 第 {page} 页访问成功")
                if early_stop:
                    if all(
                        self.storage.should_skip(r[0], r[2])
                        and self.storage.get_topic_record_time(r[0]) <= last_sweep
                        for r in (x.values() if detail else x for x in rows)
                    ):
                        if disp:
                            print(f"板块 {fid} 第 {page} 页触发早停")
                        break
                result += rows
            time.sleep(self.config.timegap_board_in)
        # 为了避免翻页期间有帖子浮动至首页导致提取不完全，可以「再次获取首页→插入最前→去重」
        # 这一行为建立在「pages × timegap_board_in 秒内浮动主题数不超过单页容量」的假设上
        if recheck:
            result = get_onepage_url(1) + result
        seen = {}
        for x in result:
            seen.setdefault(x["topic_id"] if detail else x[0], x)
        result_dedup = list(seen.values())
        if disp:
            print(f"↑ 板块 {fid} 解析完成，提取到 {len(result_dedup)} 条主题\n")
        return result_dedup

    def get_onetopic_info(
        self,
        topic_id,
        topic_sf,
        disp=False,
        index=0,
        total=1,
        force=False,
        return_header=False,
        floor=None,
    ):
        # 访问并解析一个 topic，始终获取第 1 页用于解析 topic 头信息（用于单独调用时的增量判断）
        # force 参数缺省时为普通增量更新，即便此前数据库中不存在对应 topic 条目也能正常运行
        # force 参数为 True 时为强制全量更新，会覆盖数据库中对应 topic 条目中的旧数据
        # return_header 参数为 True 时，即便不存在增量也会返回主题头信息，附带 header_only 标记
        # floor 参数非 None 时将使用 floor 作为增量判断中的已知水位，否则将使用数据库当前状态
        # 关于返回值：无更新=None；有更新=topic_info；失败=False；帖子存在但无法访问="closed"或"deleted"
        # 关于返回值：在普通增量更新模式下，topic_info 会附带 incremental 标记，用于帮助上层调用决定存储策略
        topic_url = utils.topic_url(topic_id, topic_sf)
        response = self.client.get(topic_url)
        if response.status_code != 200:
            logger.error(
                utils.log_error(
                    "E103",
                    "coordinator.get_onetopic_info",
                    f"帖子 ({topic_id}, {topic_sf})",
                )
            )
            return False
        soup = BeautifulSoup(response.content, "lxml")
        status = analyser.check_page_status(soup)
        if status in ("closed", "deleted"):
            return status
        if status == "incorrect":
            logger.error(
                utils.log_error(
                    "E104",
                    "coordinator.get_onetopic_info",
                    f"帖子 ({topic_id}, {topic_sf})",
                )
            )
            return False
        topic_info = analyser.parse_topic_info(soup, topic_id, topic_sf)
        db_total = self.storage.get_topic_max_floor(topic_id) + 1
        if type(floor) is int:
            db_total = floor + 1
        page_sources = [(1, response.content)]
        current_page = topic_url
        if force or db_total == 0:
            page_list = range(2, (topic_info["reply_count"] - 1) // 20 + 2)
            username_dict = None
        elif db_total < topic_info["reply_count"]:
            page_list = range(
                max(db_total // 20 + 1, 2), (topic_info["reply_count"] - 1) // 20 + 2
            )
            username_dict = {u: 1 for u in self.storage.get_topic_usernames(topic_id)}
        elif return_header:
            topic_info["reply_list"] = []
            topic_info["header_only"] = True
            topic_info["incremental"] = True
            return topic_info
        else:
            return None

        def echo():
            print(
                f"{index+1}/{total}  {len(page_sources):>5} / {len(page_list)+1:<5}  "
                f"{current_page}  {topic_info['topic_title']}"
            )

        if disp:
            echo()
        for page in page_list:
            current_page = f"{topic_url}&page={page}"
            response = self.client.get(current_page)
            if response.status_code != 200:
                logger.error(
                    utils.log_error(
                        "E105",
                        "coordinator.get_onetopic_info",
                        f"帖子 ({topic_id}, {topic_sf}, {page})",
                    )
                )
                return False
            page_sources.append((page, response.content))
            if disp:
                echo()
            time.sleep(self.config.timegap_topic_in)
        replylist = analyser.parse_replies(
            [content for _, content in page_sources], topic_id, topic_sf, username_dict
        )
        topic_info["reply_list"] = replylist
        if username_dict is not None:
            topic_info["incremental"] = True
        return topic_info

    def fetch_onetopic(
        self,
        topic_id,
        topic_sf,
        listing_count=None,
        force=False,
        disp=False,
        index=0,
        total=1,
        return_header=False,
        floor=None,
    ):
        if (
            not force
            and listing_count is not None
            and self.storage.should_skip(topic_id, listing_count)
        ):
            return None
        # 前置整体跳过描述A：强制全量抓取时不跳过；独立调用时不跳过；已存楼层数大于将存数据时不跳过
        # 前置整体跳过描述B：仅当调用来自上层函数、普通增量抓取且无增量时，进行前置跳过
        # 后置楼层跳过：指下层函数内部的跳过逻辑（即增量判断逻辑）
        try:
            data = self.get_onetopic_info(
                topic_id,
                topic_sf,
                disp=disp,
                index=index,
                total=total,
                force=force,
                return_header=return_header,
                floor=floor,
            )
        except Exception:
            logger.error(
                utils.log_error(
                    "E106",
                    "coordinator.fetch_onetopic",
                    f"帖子 ({topic_id}, {topic_sf})",
                )
            )
            return False
        # 帖子被关闭或被删除标志，最小化条目存储
        if data in ("closed", "deleted") and not self.storage.has_topic(topic_id):
            self.storage.insert_closed_topic(topic_id, topic_sf, status=data)
            return data
        # 链接键入错误与其他失败，不进行条目存储
        if not isinstance(data, dict):
            return data
        if data.get("header_only"):
            return data
        if data.get("incremental"):
            self.storage.save_incremental_tx(data)
        else:
            self.storage.save_topic_tx(data)
        time.sleep(self.config.timegap_topic_out)
        return data

    def fetch_board(self, fid, force=False, disp=True, early_stop=False):
        board_urls = self.get_oneboard_url(fid, disp=disp, early_stop=early_stop)
        for index, (topic_id, topic_sf, listing_count) in enumerate(board_urls):
            self.fetch_onetopic(
                topic_id,
                topic_sf,
                listing_count=listing_count,
                force=force,
                disp=disp,
                index=index,
                total=len(board_urls),
            )
        if self.recordable:
            name = dict((f, n) for n, f in self.config.boardlist).get(fid, "")
            record_sweep(fid, name, int(time.time()))

    def fetch_all(self, force=False, disp=True, early_stop=False):
        for _, fid in self.config.boardlist:
            self.fetch_board(fid, force=force, disp=disp, early_stop=early_stop)
            time.sleep(self.config.timegap_board_out)

    def get_topic_usernames(self, topic_id, topic_sf, dedup=False):
        data = self.get_onetopic_info(topic_id, topic_sf, force=True)
        # "closed"/"deleted"/False 标志原样返回
        if not isinstance(data, dict):
            return data
        usernames = [r["username"] for r in data["reply_list"]]
        if dedup:
            usernames = list(dict.fromkeys(usernames))
        return usernames

    def get_topic_json(self, topic_id, topic_sf):
        data = self.get_onetopic_info(topic_id, topic_sf, force=True)
        # "closed"/"deleted"/False 标志原样返回
        if not isinstance(data, dict):
            return data
        topic = {
            k: data[k]
            for k in (
                "topic_id",
                "topic_sf",
                "reply_count",
                "topic_title",
                "topic_time",
                "view_count",
                "tui_count",
                "board_id",
                "board_name",
            )
        }
        reply_keys = (
            "reply_id",
            "username",
            "homepage_id",
            "homepage_sf",
            "reply_box_color",
            "floor",
            "reply_time",
            "status",
            "reply_text",
            "image_list",
            "complete",
            "keyword_list",
            "hidden_content",
        )
        return {
            "topic": topic,
            "replies": [{k: r[k] for k in reply_keys} for r in data["reply_list"]],
        }

    def get_homepage(self, uid, sf, db=False):
        url = f"https://bbs.kfpromax.com/profile.php?action=show&uid={uid}&sf={sf}"
        response = self.client.get(url)
        if response.status_code != 200:
            logger.error(
                utils.log_error(
                    "E107", "coordinator.get_homepage", f"用户主页 ({uid}, {sf})"
                )
            )
            return False
        data = analyser.parse_profile_page(BeautifulSoup(response.text, "lxml"))
        if db:
            with sqlite3.connect("hp.db") as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS homepage "
                    "(uid INTEGER PRIMARY KEY, username TEXT, sf TEXT, regdate TEXT, ok INTEGER)"
                )
                regdate = data.get("注册时间", "") if data else ""
                username = data.get("用户名称", "") if data else ""
                conn.execute(
                    "INSERT OR REPLACE INTO homepage VALUES (?,?,?,?,?)",
                    (uid, username, sf, regdate, 1 if regdate else 0),
                )
        return data

    def get_index_url(self):
        # 首页动态信息获取的请求层
        # 返回值说明详见解析层注释（analyser.parse_index_page）
        url = "https://bbs.kfpromax.com/index.php"
        response = self.client.get(url)
        if response.status_code != 200:
            logger.error(utils.log_error("E108", "get_index_url", "INDEX_PAGE"))
            return False
        data = analyser.parse_index_page(BeautifulSoup(response.content, "lxml"))
        return data

    def get_search_results(
        self,
        keyword=None,
        pwuser=None,
        authorid=None,
        fid="all",
        store=False,
        force=False,
    ):
        # 搜索结果信息获取的请求层，负责构造搜索请求与翻页
        # 对于主题板块的归属，解析层只返回板块名，本函数负责将板块名映射为 fid
        # keyword 为标题关键字，pwuser 为用户名，authorid 为用户 uid，三者必选其一且不可同时指定
        # fid 可以在上述任一搜索方式下限定板块，并非本项目进行了什么后置过滤，而是论坛自带但被隐藏的功能
        # 实测论坛不支持同时指定多个 fid，如果存在类似需求，只能分别请求再由调用方拼合
        # 论坛支持使用 sid 来保持搜索会话，不过经过实测，保持相同 sid 时与保持相同 url 参数时的搜索行为一致
        # 搜索结果相同，都具备翻页稳定性，并且都在翻页时消耗搜索次数余额，所以本函数选择不依赖 sid
        if len([v for v in (keyword, pwuser, authorid) if v]) != 1:
            print("关键词、用户名与用户 uid 只能指定且必须指定其中之一\n")
            return False
        if pwuser:
            argues = f"step=2&pwuser={pwuser}&seekfid={fid}"
        elif authorid:
            argues = f"authorid={authorid}&seekfid={fid}"
        else:
            argues = f"step=2&keyword={keyword}&seekfid={fid}"

        def get_onepage_url(argues, page):
            url = f"https://bbs.kfpromax.com/search.php?{argues}&page={page}"
            response = self.client.get(url)
            if response.status_code != 200:
                logger.error(
                    utils.log_error(
                        "E109",
                        "get_search_results",
                        f"{argues} | PAGE {page}",
                    )
                )
                print("搜索请求失败")
                return False
            soup = BeautifulSoup(response.content, "lxml")
            result = analyser.parse_search_page(soup)
            if result is False:
                print("搜索结果为空")
            elif result is None:
                print("搜索余额耗尽")
            return result

        result = []
        page_data = get_onepage_url(argues, 1)
        if not page_data:
            return False
        last_page, total, remain = page_data["status"]
        result += page_data["results"]
        print(
            f"结果数量：{total} 条\n"
            f"剩余次数：{remain + 1} → {remain - last_page + 1}\n\n"
            f"PAGE 1 / {last_page} 解析完成"
        )
        for page in range(2, last_page + 1):
            page_data = get_onepage_url(argues, page)
            if not page_data:
                print(f"搜索请求在第 {page} 页失败，请重试")
                return False
            result += page_data["results"]
            print(f"PAGE {page} / {last_page} 解析完成")
        for row in result:
            row["board_id"] = BOARD_IDS.get(row["board_name"])
        if store:
            print()
            for index, row in enumerate(result):
                self.fetch_onetopic(
                    row["topic_id"],
                    row["topic_sf"],
                    force=force,
                    disp=True,
                    index=index,
                    total=total,
                )
        return result
