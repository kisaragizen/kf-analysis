import json, re
from dataclasses import dataclass
from pathlib import Path

READ_PHP = "https://bbs.kfpromax.com/read.php"


@dataclass
class Config:
    boardlist: list
    headers: dict
    proxies: dict
    timegap_board_out: int
    timegap_board_in: int
    timegap_topic_out: int
    timegap_topic_in: int


def load_config():
    path = Path(__file__).with_name("configure.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("同目录下没有找到 configure.json")
        raise SystemExit(1)
    headers = data.get("headers", {})
    if not headers.get("User-Agent") or not headers.get("Cookie"):
        print("请先在 configure.json 填入 User-Agent 与 Cookie")
        raise SystemExit(1)
    proxies = data.setdefault("proxies", {})
    if not proxies:
        print("proxies 为空，将以直连方式访问")
    elif {"http", "https"} > set(proxies):
        print("proxies 格式不正确，需同时包含 http 与 https")
        raise SystemExit(1)
    return Config(**data)


def topic_url(topic_id, topic_sf):
    return f"{READ_PHP}?tid={topic_id}&sf={topic_sf}"


def split_userhome(href):
    uid = re.findall(r"uid=(\d+)", href)
    sf = re.findall(r"sf=([^&]+)", href)
    return (int(uid[0]) if uid else None), (sf[0] if sf else None)


def split_topic_link(link):
    if not link.startswith(READ_PHP + "?"):
        return None
    tid = re.findall(r"tid=(\d+)", link)
    sf = re.findall(r"sf=([^&]+)", link)
    return (int(tid[0]), sf[0] if sf else "") if tid else None
