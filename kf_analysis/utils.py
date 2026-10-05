import json
import re
from dataclasses import dataclass
from pathlib import Path

READ_PHP = "https://bbs.kfpromax.com/read.php"


LOG_CODES = {
    "E101": "板块列表页获取失败",
    "E102": "板块列表页请求异常",
    "E103": "主题头信息获取失败",
    "E104": "主题不存在或安全验证未通过",
    "E105": "主题翻页获取失败",
    "E106": "主题请求异常",
    "E107": "用户主页获取失败",
    "E108": "论坛首页获取失败",
    "E109": "搜索结果获取失败",
    "W101": "PID 重复现象提示",
}


def log_error(code, site, detail):
    return f"[{code}] {site} | {detail}"


@dataclass
class Config:
    boardlist: list
    headers: dict
    proxies: dict
    timegap_board_out: int
    timegap_board_in: int
    timegap_topic_out: int
    timegap_topic_in: int


def load_config(identity=None):
    path = Path(__file__).with_name("configure.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("配置文件已损坏或缺失，请重新下载 configure.json")
        raise SystemExit(1)
    identities = data.pop("identities", {})
    if not identities:
        print("需要定义至少一个身份，格式请参考 README.md")
        raise SystemExit(1)
    if identity is None:
        identity = next(iter(identities))
        print(f"正在使用默认身份：{identity}")
    elif identity not in identities:
        print(f"没有名为 {identity} 的身份，请检查拼写错误")
        print(f"可用身份列表：{', '.join(identities)}")
        raise SystemExit(1)
    picked = identities[identity]
    data["headers"] = picked.get("headers", {})
    data["proxies"] = picked.get("proxies", {})
    required_a = {"User-Agent", "Cookie", "Host"}
    required_b = {"http", "https"}
    if (required_a & data["headers"].keys()) != required_a:
        print(f"headers 格式错误，需包含以下字段：{', '.join(required_a)}")
        raise SystemExit(1)
    if not data["proxies"]:
        print("未配置代理，将直连访问")
    elif (required_b & data["proxies"].keys()) != required_b:
        print(f"proxies 格式错误，需包含以下字段：{', '.join(required_b)}")
        raise SystemExit(1)
    else:
        print("代理已配置，经代理访问")
    empty = [k for k, v in (data["headers"] | data["proxies"]).items() if not v]
    if empty:
        print(f"以下字段为空，请填写后再运行：{', '.join(empty)}")
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
