import re
import time
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
from .utils import split_userhome


def check_page_status(soup):
    # ↓帖子状态正常返回 "normal"，被管理员关闭时返回 "closed"
    # ↓被管理员删除时返回 "deleted"，目标不存在或安全码错误时返回 "incorrect"
    title = soup.find_all("title")[0].text
    if "此帖被管理员关闭" in title and not soup.find_all("div", class_="readtext"):
        return "closed"
    if "读取数据错误" in title and not soup.find_all("div", class_="readtext"):
        return "deleted"
    if "无安全验证" in title and not soup.find_all("div", class_="readtext"):
        return "incorrect"
    return "normal"


def parse_board_page(soup, detail=False):
    # detail=False 时的返回值：(topic_id, topic_sf, reply_num)
    # detail=True 时的返回值：{topic_id, topic_sf, topic_poster, topic_labels, topic_title, reply_num, view_count}
    # reply_num 直接返回在板块页解析到的数字，与项目口径不同，它是不包含主楼的
    result = []
    for tr in soup.find_all("tr"):
        tit = tr.find("div", class_="threadtit1")
        if not tit:
            continue
        if tr.find("td").get_text(strip=True) == "顶":
            continue
        link = next(
            a for a in tit.find_all("a") if a.attrs["href"].startswith("read.php?tid=")
        )
        tds = tr.find_all("td")
        b6 = tr.find("ul", class_="b_tit6")
        nums = b6.get_text("\n", strip=True).split("\n") if b6 else ["0"]
        rdict = {
            "topic_id": int(re.findall(r"tid=(\d+)", link.attrs["href"])[0]),
            "topic_sf": re.findall(r"sf=([^&]+)", link.attrs["href"])[0],
            "topic_poster": tds[3].find("a").text,
            "topic_labels": [
                f.get_text(strip=True).strip("[]")
                for f in tit.find_all("font")
                if f.find_parent("a") is not link
            ],
            "topic_title": link.text,
            "reply_num": int(nums[0]),
            "view_count": None if nums[1] == "-" else int(nums[1]),
        }
        if detail:
            result.append(rdict)
        else:
            rtuple = (rdict["topic_id"], rdict["topic_sf"], rdict["reply_num"])
            result.append(rtuple)
    return result


def parse_topic_info(soup, topic_id, topic_sf):
    # 解析主题页头部信息，注意在本项目中主题帖第 0 楼也算做回复贴
    # 点击量与被推数不再作为持久数据进行存储，但本函数仍保留对它们的解析，方便日后调用
    header_td = soup.select_one("td[style*='line-height:25px']")
    board_link = header_td.find_all("a", href=re.compile(r"fid="))[-1]
    topic_header = header_td.text
    numbers_split = re.findall(r"\d+", topic_header)
    numbers_split = [None] + numbers_split if len(numbers_split) == 6 else numbers_split
    # 资源区中点击量不可见，会导致 numbers_split 缺失一个元素，以 None 补足
    return {
        "topic_id": topic_id,
        "topic_sf": topic_sf,
        "reply_count": int(numbers_split[1]) + 1,
        "topic_title": soup.select_one("div.drow:nth-child(3) span").text,
        "topic_time": int(
            datetime.timestamp(
                datetime.strptime(
                    re.search(
                        r"发表时间：(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", topic_header
                    ).group(1),
                    "%Y-%m-%d %H:%M",
                )
            )
        ),
        "view_count": numbers_split[0],
        "tui_count": int(re.findall(r"\d+", soup.find("a", id="read_tui").text)[0]),
        "board_id": int(re.findall(r"fid=(\d+)", board_link.attrs["href"])[0]),
        "board_name": board_link.text,
        "record_time": int(time.time()),
    }


def render_body(node, parts, images):
    # ↑本函数递归实现，将文本节点加入 parts，将块级元素与 br 标签转为换行符
    # ↑提取 url 标签的文本与链接并加入 parts，提取 img 标签的链接分别加入 parts 与 images
    if isinstance(node, NavigableString):
        parts.append(str(node))
        return
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name in ("br", "hr"):
            parts.append("\n")
        elif child.name == "img":
            src = child.attrs.get("src")
            if src is None:
                continue
            images.append(src)
            parts.append(src)
        elif child.name == "a":
            t = child.get_text()
            href = child.attrs.get("href")
            parts.append(t if href is None or t == href else f"{t}({href})")
        elif child.name in ("p", "div"):
            parts.append("\n")
            render_body(child, parts, images)
            parts.append("\n")
        elif child.name == "fieldset":
            # ↓经过 parse_replies 的前置处理，fieldset 已经不存在无意义内容框体了
            for gc in child.children:
                if getattr(gc, "name", None) == "legend":
                    continue
                render_body(gc, parts, images)
        else:
            render_body(child, parts, images)


def parse_replies(page_list, topic_id, topic_sf, username_dict=None):
    # ↑page_list 为主题帖所有页面的字节列表，按楼层时间顺序排列，翻页由调用方完成
    def compact(text):
        # ↓合并连续换行，统一空白类字符形式，得到紧凑正文
        text = re.sub(r"[ \t　\xa0]+", " ", text)
        text = re.sub(r"\n *", "\n", text)
        text = re.sub(r"(?:\r\n?|\n)+", "\n", text)
        return text.strip()

    # ↓username_dict 为主题帖内用户名词典，实时记录发言用户，用于判断关键词是否为用户名关键词
    # ↓关键词列表是为了脱离 quote 文本解析方法也能体现回复关系，KF论坛的 quote 文本存在被发帖人随意更改的不可预测性
    # ↓但是关键词中又存在非用户名关键词，为解决此问题，引入 username_dict 并使本函数能一次性解析所有 page
    replylist = []
    if username_dict is None:
        username_dict = {}
    for content in page_list:
        soup = BeautifulSoup(content, "lxml")
        divlist = soup.find_all("div", class_="readtext")
        for x in divlist:
            xdict = {}
            xdict["topic_id"] = topic_id
            xdict["topic_sf"] = topic_sf
            div_id = x.attrs["id"]
            xdict["reply_id"] = (
                "TPC" + str(topic_id) if div_id == "pidtpc" else div_id.upper()
            )
            # ↑回复贴 reply_id 格式说明：主题回复贴 TPC<tid>；回复回复贴 PID<pid>
            user_a = x.select_one("div.readidmsbottom a")
            xdict["username"] = user_a.text
            # ↓提取回复者主页链接与框体颜色
            xdict["homepage_id"], xdict["homepage_sf"] = split_userhome(
                user_a.attrs["href"]
            )
            xdict["reply_box_color"] = user_a.attrs["style"][6:]
            # ↓开始提取所在楼层数和回贴时间
            xdict["floor"] = x.select_one(
                "span[style*='font-size:16px;font-weight:bold']"
            ).text
            xdict["floor"] = (
                0
                if "楼主" in xdict["floor"]
                else int(re.findall(r"\d+", xdict["floor"])[0])
            )
            xdict["reply_time"] = int(
                datetime.timestamp(
                    datetime.strptime(
                        x.select_one(
                            "div[style*='line-height:30px'] span[style='color:#999999;']"
                        ).text.strip()
                        + ":00",
                        "%Y-%m-%d %H:%M:%S",
                    )
                )
            )
            if xdict["homepage_id"] is None:
                # ↓禁言中用户与账户被删除用户的共同标志是 homepage_id 为空
                # ↓此类用户相关发言不存在 reply_box，进行最小化记录
                xdict.update(
                    reply_text=None,
                    image_list=[],
                    complete=0,
                    keyword_list=[],
                    hidden_content=[],
                )
                xdict["status"] = "banned"
                replylist.append(xdict)
                continue
            # ↓reply_box 为回复贴正文容器，其中包含正文，fieldset 类标签，一般标签
            # ↓fieldset 包括：引用框 / 等级权限框 / 购买权限框 / 关键词列表 ←四种有意义内容
            # ↓以及近期发帖 / 自助评分提示（两种） / 优秀贴提示 / 扣分提示 / 锁贴提示 / 移区提示 ←等无意义内容
            reply_box = x.select_one("td:nth-child(2) > div:nth-child(1)")
            xdict["status"] = (
                "hidden" if reply_box.find("span", class_="k_f18") else "active"
            )
            # ↑因进度分不足而暂时隐藏的楼层的标志为 class="k_f18"，标记此类帖子状态为 hidden
            # ↓outer_fs_list 为最外层 fieldset 框体列表，keyword_list 是关键词列表
            # ↓若多种 fieldset 相互嵌套，也只按最外层 fieldset 判断类型，并只保留实际文本
            outer_fs_list = []
            keyword_list = []
            complete = 0
            for fs in reply_box.find_all("fieldset"):
                legend = fs.find("legend")
                lt = legend.text
                if (
                    "此帖售价" in lt
                    or "神秘等级" in lt
                    or (lt == "提示" and "设定了加密" in fs.get_text())
                ):
                    # ↑分别为购买框标志 / 等级框满足标志 / 等级框不满足标志
                    # ↓先遍历所有框体，然后通过判断该框体外层是否还有框体来判断是否为最外层
                    if fs.find_parent("fieldset") is None:
                        outer_fs_list.append(fs)
                elif lt == "关键词":
                    keyword_list += [a.text for a in fs.find_all("a")]
            # ↓关键词列表的目的是体现回复关系，所以只保留用户名关键词（通过 username_dict 实现）
            xdict["keyword_list"] = [kw for kw in keyword_list if kw in username_dict]
            username_dict[xdict["username"]] = 1
            # ↓complete 判定，0：帖子没有权限框；1：帖子有权限框且全部可读；2：存在不可读的权限框
            # ↓如何判定存在不可读的权限框？当检测到购买按钮仍存在时；当检测到 fs 中存在字符串“设定了加密”时
            for fs in outer_fs_list:
                if (
                    fs.find("input", onclick=lambda v: v and "buytopic" in v)
                    or "设定了加密" in fs.get_text()
                ):
                    complete = 2
                else:
                    complete = max(complete, 1)
            xdict["complete"] = complete
            # ↓当所有权限框均为可读状态时，提取实际文本
            # ↓hidden_content 字段说明：type 为框体类型，text 为实际文本
            # ↓因为 legend 标签对并不直接包裹文本，直接从 DOM 层面移除就好
            if complete == 1:
                xdict["hidden_content"] = []
                for q in outer_fs_list:
                    legend_text = q.find("legend").text
                    for leg in q.find_all("legend"):
                        leg.decompose()
                    parts = []
                    render_body(q, parts, [])
                    xdict["hidden_content"].append(
                        {
                            "type": "售价" if "此帖售价" in legend_text else "加密",
                            "text": compact("".join(parts)),
                        }
                    )
            else:
                xdict["hidden_content"] = []
            # ↓提取 reply_text 实际文本前，先移除所有无意义框和已经另外存储的权限框
            for fs in reply_box.find_all("fieldset", class_="read_fds"):
                fs.decompose()
            for fs in reply_box.find_all("fieldset"):
                legend = fs.find("legend")
                if fs in outer_fs_list or "自助评分" in legend.text:
                    fs.decompose()
            for div in reply_box.find_all(
                "div", style=lambda v: v and "line-height:30px" in v
            ):
                div.decompose()
            parts, images = [], []
            render_body(reply_box, parts, images)
            xdict["reply_text"] = compact("".join(parts))
            xdict["image_list"] = images
            replylist.append(xdict)
    return replylist


def parse_profile_page(soup):
    node = soup.find(string=re.compile("注册时间"))
    if node is None:
        return None
    fields = {}
    for line in node.find_parent("td").get_text().splitlines():
        if "：" in line:
            key, val = line.split("：", 1)
            fields[key.strip()] = val.strip()
    return fields


def parse_index_page(soup):
    # 论坛首页包含：最新被推=左上A/最新主题=左下B/最新动态=正中C
    # 本函数负责解析对列表B和列表C进行解析；不认为列表A具有统计价值
    # 因为列表A具有以下隐性限制：①老帖被推不上榜；②每个板块都有最大上榜名额
    # 所以“通过持续监控列表A获得首页相关板块的完整被推信息”是不可能的
    # {"active": [...], "new": [...]}
    # new: {topic_id, topic_sf, topic_title, time_text}
    # active: {topic_id, topic_sf, topic_poster, topic_title, reply_num, time_text, label}
    # reply_num 为不包含主楼的回复量，不过需要注意首页会将所有大于 99 回复量的主题都显示为 99+
    # 无法在不进一步展开的情况下得知对应主题的准确回复量，此时，本函数会将 reply_num 记为 None
    # time_text 为相对时间，形如：1分钟内/3分钟前/5小时前/7天前
    # 需要注意两个列表中该字段的语义不同：active 中为最后动态时刻，new 中为发表时刻
    # label 为首页特有的主题标签：讨论/日记/求助/聊天/数码，分别对应一个或多个板块
    active = []
    topic_eles = soup.find_all("div", class_="indexlbtc")
    topic_eles = [d.find("a") for d in topic_eles]
    for ele in topic_eles:
        topic_id, topic_sf = re.findall(r'[?&]tid=([^&]+)&sf=([^&]+)', ele["href"])[0]
        topic_title = ele["title"].removeprefix("《").removesuffix("》")
        reply_num = ele.find("span", class_="indexlbtc_h").get_text(strip=True)
        reply_num = int(reply_num) if reply_num.isdigit() else None
        label = ele.find("span", class_="indexlbtc_l").get_text(strip=True)
        time_text = ele.find("span", class_="indexlbtc_s").get_text(strip=True)
        topic_poster = ele["uname"]
        active.append(
            {
                "topic_id": int(topic_id),
                "topic_sf": topic_sf,
                "topic_poster": topic_poster,
                "topic_title": topic_title,
                "reply_num": reply_num,
                "time_text": time_text,
                "label": label,
            }
        )
    new = []
    topic_eles = soup.find_all("div", class_="rightboxa")[1].find_all("a")
    for ele in topic_eles:
        topic_id, topic_sf = re.findall(r'[?&]tid=([^&]+)&sf=([^&]+)', ele["href"])[0]
        topic_title = ele["title"].removeprefix("《").removesuffix("》")
        time_text = ele.find("span", class_="k_fr").get_text(strip=True)
        new.append(
            {
                "topic_id": int(topic_id),
                "topic_sf": topic_sf,
                "topic_title": topic_title,
                "time_text": time_text,
            }
        )
    return {"active": active, "new": new}


def parse_search_page(soup):
    # 本函数负责对搜索结果页进行解析（也能够用于对用户主题页的解析）
    # 返回值形如 {"results": [...], "status": (总页数, 总结果数, 剩余搜索次数)}
    # results 元素为 {topic_id, topic_sf, topic_title, board_name, topic_poster, last_reply_time}
    # 搜索结果页无法直接解析主题所属板块的 fid，上级调用可以根据 coordinator 提供的对照表进行转换
    # 需要注意 last_reply_time 不是主题发表时间而是主题最后被回复的时间
    if soup.find("a", href=re.compile(r"javascript:history\.go\(-1\)")):
        if "今日搜索次数耗尽" in soup.get_text():
            return None
        return False
    result = []
    trs = soup.select("table.thread1 tr")
    for tr in trs[2:-1]:
        tds = tr.find_all("td")
        links = tr.find_all("a")
        pattern = r'[?&]tid=([^&]+)&sf=([^&]+)'
        topic_id, topic_sf = re.findall(pattern, links[0]["href"])[0]
        topic_title = links[0].get_text(strip=True)
        board_name = tds[1].get_text(strip=True)
        topic_poster = links[1].get_text(strip=True)
        last_reply_time = links[1].next_sibling.next_sibling.strip()
        result.append(
            {
                "topic_id": int(topic_id),
                "topic_sf": topic_sf,
                "topic_title": topic_title,
                "board_name": board_name,
                "topic_poster": topic_poster,
                "last_reply_time": last_reply_time,
            }
        )
    head = trs[0].get_text(" ", strip=True)
    total = re.search(r"共搜索到了\s*(\d+)\s*条信息", head)
    remain = re.search(r"本日剩余搜索次数\s*(\d+)\s*次", head)
    last = re.search(r"…(\d+)页", head)
    status = (
        int(last.group(1)) if last else 1,
        int(total.group(1)),
        int(remain.group(1)),
    )
    return {"results": result, "status": status}
