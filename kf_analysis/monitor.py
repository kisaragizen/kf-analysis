import ctypes
import time
import tkinter
from .coordinator import KFanalysis


def topic_event_default(data, criteria):
    # 主题级监控命中判断函数，可自定义
    # 提示行为：提示本轮新增回复数与命中数
    # 命中规则：新增回复由特定用户发出时命中
    # data 为待判定列表，每个元素都代表对应的主题，可用字段：
    # {topic_id, topic_sf, reply_count, topic_title, topic_time,
    #  view_count, tui_count, board_id, board_name, record_time, reply_list}
    # reply_list 为合规回复列表，每个元素都代表对应的回复，可用字段：
    # {topic_id, topic_sf, reply_id, username, homepage_id, homepage_sf, reply_text, floor,
    #  reply_box_color, reply_time, status, complete, image_list, keyword_list, hidden_content}
    tid = data["topic_id"]
    names = [n.strip() for n in criteria.split(",") if n.strip()]
    matched = [r for r in data["reply_list"] if r["username"] in names]
    monitor_message(tid, f"新增与命中：({len(data['reply_list'])}, {len(matched)})")
    data["reply_list"] = matched
    if matched:
        return data


def topic_action_default(matches):
    # 主题级监控命中执行函数，可自定义
    # 气泡提示本轮命中回复数＆命中用户名列表＆主题总回复数
    hits = matches["reply_list"]
    replies = matches["reply_count"]
    names = ", ".join(dict.fromkeys(r["username"] for r in hits))
    monitor_bubble(f"命中用户: {names}\n命中数量: {len(hits)}\n当前状态: {replies}")


def monitor_topic(
    config,
    links,
    gap=300,
    store=False,
    force=False,
    db_path="kf.db",
    event=topic_event_default,
    action=topic_action_default,
    criteria="",
):
    # 对若干主题进行持续监控，以 gap 秒为间隔循环访问
    # 当检测到主题被管理员设置为不可访问，或者连续访问失败达到 10 次时，停止对对应主题的监控
    # store 决定两种行为：①本地数据库 db_path 是否同步更新；②基线轮次历史信息水位取自 db_path 还是最新页面状态
    # force 用于指定基线轮次的行为：True=全量更新+历史信息也将参与命中判定；False=增量更新+仅基线建立后的新信息参与命中判定
    # 数据获取成功后，本函数将数据与 criteria 发送给 event → event 返回命中了其内部规则的数据 → 若存在命中，由本函数调用 action
    # criteria 为可由 CLI 调用传入的字符串，其格式与意义取决于 event 的实现，如果说 event 决定了判定逻辑，criteria 则指定了判定对象
    # 默认 event 行为为“新增回复由特定用户发出时命中”，此时 criteria 就可以用来指定用户名列表
    last = {tid: -1 for tid, sf in links}
    targets = [[tid, sf, 0] for tid, sf in links]
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")

    def poll(tid, sf, floor, ecrof):
        data = kf.fetch_onetopic(tid, sf, force=ecrof, return_header=True)
        if data in ("closed", "deleted"):
            monitor_message(tid, "监控退出（目标已经不可访问）")
            target[2] = False
            return []
        if data is False:
            target[2] += 1
            if target[2] < 10:
                monitor_message(tid, f"访问失败第 {target[2]} 次")
            else:
                monitor_message(tid, "监控退出（重试次数到达上限）")
                target[2] = False
            return []
        target[2] = 0
        if not ecrof:
            data["reply_list"] = [r for r in data["reply_list"] if r["floor"] > floor]
            last[tid] = max((r["floor"] for r in data["reply_list"]), default=floor)
        return data

    while True:
        for target in targets:
            tid, sf, retry = target
            if retry is False or last[tid] < 0:
                continue
            data = poll(tid, sf, last[tid], False)
            if data:
                matches = event(data, criteria)
                if matches:
                    action(matches)
        for target in targets:
            tid, sf, retry = target
            if retry is False or last[tid] > -1:
                continue
            if not retry:
                monitor_message(tid, "基线建立中")
            stored = kf.storage.get_topic_max_floor(tid)
            data = poll(tid, sf, stored, force)
            if not data:
                continue
            if stored < 0 or force:
                last[tid] = data["reply_list"][-1]["floor"]
            else:
                last[tid] = stored
            monitor_message(tid, f"基线已建立：{last[tid]}")
            if force:
                matches = event(data, criteria)
                if matches:
                    action(matches)
        time.sleep(gap)


def board_event_expand_first(
    new_topic,
    active_topic,
    topic_list,
    board_id,
    store,
    force,
    criteria,
    phase,
    db_path,
    config,
    monitor_time,
):
    # 板块级监控命中判断函数①：先展开后判定（所有有动态主题都会入库）
    # store=True 时会在监控的同时更新 db_path；store=False 时则进入仅监控模式
    # 三个主题列表的元素均包含这些字段：{topic_id, topic_sf, topic_poster, topic_labels, topic_title, reply_num, view_count, reply_from}
    # new_topic 为本轮检出的新增主题；active_topic 为本轮检出的有动态主题；topic_list 为本轮扫描到的所有主题
    # phase 用于标注当前轮次是基线轮还是循环轮；monitor_time 用于标注监控启动时间，可以用于过滤陈旧回复
    # 命中判定：检查增量部分中是否存在由特定用户发出的帖子（由 criteria 指定用户名列表）
    # 基线行为：force=True 时对扫描到的所有主题（topic_list）的全量信息进行入库与判定
    # 循环行为：对本轮扫描到的所有有动态主题（active_topic）的增量部分进行入库与判定
    if phase == "base":
        if not force:
            return []
        ecrof = True
        rows = topic_list
        monitor_message(board_id, f"历史信息判定：{len(rows)} 主题")
    else:
        ecrof = False
        rows = active_topic
        monitor_message(board_id, f"{len(new_topic)} 新增主题 & {len(rows)} 动态主题")
    hits = []
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")
    for row in rows:
        tid, sf = row["topic_id"], row["topic_sf"]
        floor = row["reply_from"] if row["reply_from"] > -1 else None
        data = kf.fetch_onetopic(tid, sf, force=ecrof, floor=floor)
        if data in ("closed", "deleted"):
            row["unreachable"] = True
            continue
        if data is False:
            monitor_message(tid, "因网络错误而展开失败")
            continue
        if phase == "loop":
            if row["reply_from"] > -1:
                data["reply_list"] = [
                    r for r in data["reply_list"] if r["floor"] > row["reply_from"]
                ]
            elif not store:
                data["reply_list"] = [
                    r
                    for r in data["reply_list"]
                    if r["reply_time"] >= monitor_time - 60
                ]
        matches = topic_event_default(data, criteria)
        if matches:
            hits.append((row, matches))
    return hits


def board_event_judge_first(
    new_topic,
    active_topic,
    topic_list,
    board_id,
    store,
    force,
    criteria,
    phase,
    db_path,
    config,
    monitor_time,
):
    # 板块级监控命中判断函数②：先判定后展开（只有被命中主题才会入库）
    # 命中判定：检查新增主题列表中是否存在由特定用户发出的主题（由 criteria 指定用户名列表）
    # 需要注意的是，展开失败的已命中主题同样会被上报，只不过数据体为 None
    # 其余行为与参数解释请参考 board_event_expand_first 处的注释
    names = [n.strip() for n in criteria.split(",") if n.strip()]
    if not names:
        monitor_message(board_id, "先判定后展开模式必须指定 criteria")
        return False
    if phase == "base":
        if not force:
            return []
        ecrof = True
        rows = topic_list
        monitor_message(board_id, f"历史信息判定：{len(rows)} 主题")
    else:
        ecrof = False
        rows = new_topic
        monitor_message(
            board_id, f"{len(new_topic)} 新增主题 & {len(active_topic)} 动态主题"
        )
    matches = []
    rows = [r for r in rows if r["topic_poster"] in names]
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")
    for row in rows:
        tid, sf = row["topic_id"], row["topic_sf"]
        floor = row["reply_from"] if row["reply_from"] > -1 else None
        data = kf.fetch_onetopic(tid, sf, force=ecrof, floor=floor)
        if data in ("closed", "deleted"):
            row["unreachable"] = True
        if data is False:
            monitor_message(tid, "因网络错误而展开失败")
        matches.append((row, data if isinstance(data, dict) else None))
    return matches


def board_action_default(matches):
    # 板块级监控命中执行函数，默认行为为气泡提示
    lines = []
    for row, _ in matches[:3]:
        lines.append(f"作者：{row['topic_poster']}\n" f"标题：{row['topic_title']}")
    monitor_bubble(f"命中主题: {len(matches)}\n{"\n".join(lines)}")


def monitor_board(
    config,
    fids,
    gap=300,
    pages=2,
    store=False,
    force=False,
    db_path="kf.db",
    event=board_event_expand_first,
    action=board_action_default,
    criteria="",
):
    # 对若干板块进行持续监控，轮次间隔为 gap 秒，监控对象为主题序与回复序的前 pages 页
    # 本函数只负责对两个主题列表进行扫描，并根据扫描结果得到板块动态信息，并传送给 event 函数
    # event 函数将决定如何处理板块动态信息：主题是否又在何时需要展开，是否同步进行数据库写入，如何进行命中判定
    # event 函数会将命中信息（其数据结构由 event 函数决定）返回给本函数，命中信息不为空时将由本函数触发 action 函数
    # 本函数不涉及对任何本地数据库的写入，store 与 db_path 只决定基线取自哪里：True 时读库，False 时读实时值
    r_water = {}
    t_water = {}
    blocked = set()
    monitor_time = int(time.time())
    retries = dict.fromkeys(fids, 0)
    from_db = store and not force
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")

    while True:
        for fid, retry in retries.items():
            if retry is False:
                continue
            loopturn = fid in t_water
            rows = kf.get_oneboard_url(
                fid,
                detail=True,
                pages=pages,
                order="lastpost",
                recheck=False,
            )
            post = kf.get_oneboard_url(
                fid,
                detail=True,
                pages=pages,
                order="postdate",
                recheck=False,
            )
            if not (rows and post):
                retries[fid] += 1
                if retries[fid] < 10:
                    monitor_message(fid, f"访问失败第 {retries[fid]} 次")
                else:
                    monitor_message(fid, "监控退出（重试次数到达上限）")
                    retries[fid] = False
                continue
            retries[fid] = 0
            all_topic = {}
            new_topic = []
            active_topic = []
            newest = 0
            rows = [r for r in rows if r["topic_id"] not in blocked]
            post = [r for r in post if r["topic_id"] not in blocked]
            for row in rows:
                tid = row["topic_id"]
                real_floor = row["reply_num"]
                past_floor = r_water.get(tid, -1)
                row["reply_from"] = past_floor
                all_topic[tid] = row
                if loopturn and real_floor > past_floor:
                    active_topic.append(row)
            for row in post:
                tid = row["topic_id"]
                row["reply_from"] = (
                    all_topic[tid]["reply_from"]
                    if tid in all_topic
                    else r_water.get(tid, -1)
                )
                all_topic[tid] = row
                newest = max(newest, tid)
                if loopturn and tid > t_water[fid]:
                    new_topic.append(row)
            if loopturn:
                t_water[fid] = max(t_water[fid], newest)
            else:
                known = [
                    r["topic_id"]
                    for r in post
                    if from_db and kf.storage.get_topic_max_floor(r["topic_id"]) > -1
                ]
                t_water[fid] = max(known) if known else newest
                monitor_message(fid, f"基线已建立：{len(all_topic)}")
            phase = "loop" if loopturn else "base"
            topic_list = list(all_topic.values())
            matches = event(
                new_topic,
                active_topic,
                topic_list,
                fid,
                store,
                force,
                criteria,
                phase,
                db_path,
                config,
                monitor_time,
            )
            if matches is False:
                return
            for row in rows + post:
                if row.get("unreachable"):
                    blocked.add(row["topic_id"])
            for row in rows:
                tid = row["topic_id"]
                if store:
                    r_water[tid] = kf.storage.get_topic_max_floor(tid)
                else:
                    r_water[tid] = row["reply_num"]
            if matches:
                action(matches)
        time.sleep(gap)


def monitor_bubble(text, duration=2000, border=1):
    win = tkinter.Tk()
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    tkinter.Label(
        win,
        text=text,
        font=("TkDefaultFont", 10),
        bg="#222222",
        fg="#ffffff",
        padx=7,
        pady=7,
        justify="left",
        highlightthickness=border,
        highlightbackground="#FF8C00",
    ).pack()
    win.update_idletasks()
    area = (ctypes.c_long * 4)()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0)
    gap = round((area[3] - area[1]) * 0.012)
    x = area[2] - win.winfo_width() - gap
    y = area[3] - win.winfo_height() - gap
    win.geometry(f"+{x}+{y}")
    win.after(duration, win.destroy)
    win.mainloop()


def monitor_message(tid, text):
    print(f"{time.strftime('%m-%d %H:%M:%S')} [{tid}] {text}")
