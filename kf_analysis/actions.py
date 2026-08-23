# 暂不支持有强制主题分类的板块进行主题发帖
# 不影响这些板块中回复发帖/编辑发帖/获取帖子原始内容的功能
import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from .service import Client
from .utils import load_config, topic_url


def gbk_form(data):
    def enc(v): return quote(str(v).encode("gbk", errors="replace"), safe="")
    return "&".join(f"{enc(k)}={enc(v)}" for k, v in data.items()).encode("gbk")


def buy_topic(client, topic_id, topic_sf, mode):
    # 主题购买函数：目前论坛一个主题只允许主楼中存在一组购买框
    # 返回值说明：价格=可购买；-1=已购买；-2=无可购买内容；None=购买失败
    # 当 mode=buy 时才会执行购买，通过再次获取主题信息来判断是否购买成功
    def find_sale_box(soup):
        for q in soup.find_all("fieldset"):
            legend = q.find("legend")
            if legend and "此帖售价" in legend.text:
                return q
        return None
    soup = BeautifulSoup(client.get(topic_url(topic_id, topic_sf)).content, "lxml")
    fs = find_sale_box(soup)
    if fs is None: return -2
    button = fs.find("input", onclick=lambda v: v and "buytopic" in v)
    if button is None: return -1
    price = int(re.findall(r"此帖售价\s*(\d+)", fs.find("legend").text)[0])
    if mode == "buy":
        onclick = button["onclick"]
        client.get("https://bbs.kfpromax.com/" + re.search(r'location\.href="([^"]+)"', onclick).group(1))
        soup = BeautifulSoup(client.get(topic_url(topic_id, topic_sf)).content, "lxml")
        fs = find_sale_box(soup)
        if fs is not None and fs.find("input", onclick=lambda v: v and "buytopic" in v) is not None:
            return None
    return price


def transfer_money(client, username, amount, memo=""):
    headers = {"Content-Type": "application/x-www-form-urlencoded",
               "Referer": "https://bbs.kfpromax.com/hack.php?H_name=bank"}
    data = gbk_form({"action": "virement", "pwuser": username, "to_money": str(amount), "memo": memo})
    resp = client.session.post(headers["Referer"], data=data, timeout=15, headers=headers)
    return resp.content.decode("gbk", errors="replace")


class Actions:
    def __init__(self, config=None):
        self.client = Client(config if config is not None else load_config())

    def gbk_len(text):
        return len(text.encode("gbk", errors="replace"))

    def get_soup(self, url):
        return BeautifulSoup(self.client.get(url).content, "lxml")

    def get_form(self, soup):
        # 目标表单含有为防止 CSRF 的 verify 字段
        # 跳过其中的无名输入框；转换唯一 textarea 为键值对（原始正文）
        data = {}
        for form in soup.find_all("form"):
            if form.find("input", attrs={"name": "verify"}):
                for inp in form.find_all(["input", "textarea"]):
                    name = inp.get("name")
                    if not name: continue
                    if inp.name == "textarea": data[name] = inp.get_text()
                    else: data[name] = inp.get("value", "")
                return data
        return None

    def parse_response(self, content):
        text = content.decode("gbk", errors="replace")
        m = re.search(r"read\.php\?tid=(\d+)(?:&sf=([0-9a-fA-F]+))?", text)
        if m: return {"ok": True, "tid": int(m.group(1)), "sf": m.group(2), "message": "发表成功"}
        return {"ok": False, "tid": None, "sf": None, "message": "解析失败"}

    def post_reply(self, tid, sf, content, keywords=""):
        soup = self.get_soup(topic_url(tid, sf))
        data = self.get_form(soup)
        if not data or data.get("action") != "reply":
            return {"ok": False, "message": "未在目标页面找到回复表单"}
        data.update(atc_content=content, diy_guanjianci=keywords, Submit="回复帖子")
        return self.submit(data)

    def post_topic(self, fid, content, title, keywords=""):
        post_url = f"https://bbs.kfpromax.com/post.php?fid={fid}&newthread=1"
        soup = self.get_soup(post_url)
        data = self.get_form(soup)
        if not data: return {"ok": False, "message": "主题发帖页面获取失败/解析失败"}
        data.update(atc_title=title, atc_content=content, diy_guanjianci=keywords, Submit="确定发表")
        return self.submit(data)

    def get_modify_page(self, tid, sf, pid, article):
        soup = self.get_soup(topic_url(tid, sf))
        topic_data = self.get_form(soup)
        if not topic_data: return None, "帖子ID或楼层不存在"
        fid = topic_data["fid"]
        modify_url = (f"https://bbs.kfpromax.com/post.php?action=modify"
                      f"&fid={fid}&tid={tid}&pid={pid}&article={article}")
        soup = self.get_soup(modify_url)
        data = self.get_form(soup)
        if data: return data, None
        title = soup.find("title").text
        if "无权限" in title: return None, "对此贴没有编辑权限"
        if "非法" in title: return None, "目标楼层不存在"
        return None, "编辑页获取失败"

    def get_post_content(self, tid, sf, pid="tpc", article=0):
        data, err = self.get_modify_page(tid, sf, pid, article)
        if not data: return {"ok": False, "message": err}
        return {"ok": True, "title": data.get("atc_title", ""), "content": data.get("atc_content", "")}

    def edit_post(self, tid, sf, pid="tpc", article=0,
                  content=None, title=None, keywords=None):
        data, err = self.get_modify_page(tid, sf, pid, article)
        if not data:
            return {"ok": False, "message": err}
        if content is not None:
            data["atc_content"] = content
        if title is not None:
            data["atc_title"] = title
        if keywords is not None:
            data["diy_guanjianci"] = keywords
        data["Submit"] = "确定发表"
        result = self.submit(data)
        if result.get("ok"):
            result.update(tid=tid, sf=sf)
        return result

    def submit(self, data):
        if self.gbk_len(data.get("atc_title", "")) > 100:
            return {"ok": False, "message": "标题超过 100 字节（GBK）"}
        if self.gbk_len(data.get("atc_content", "")) < 12:
            return {"ok": False, "message": "正文少于 12 字节（GBK）"}
        if self.gbk_len(data.get("atc_content", "")) > 50000:
            return {"ok": False, "message": "正文超过 50000 字节（GBK）"}
        post_url = "https://bbs.kfpromax.com/post.php"
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=gbk"}
        resp = self.client.session.post(post_url, data=gbk_form(data), timeout=15, headers=headers)
        return self.parse_response(resp.content)
