import ctypes
import time
import tkinter
from .coordinator import KFanalysis


def monitor_event(data, criteria):
    # 监控命中判断函数，可自定义
    # 提示行为：提示本轮新增回复数与命中数
    # 命中规则：新增回复由特定用户发出时命中
    tid = data["topic_id"]
    names = [n.strip() for n in criteria.split(",") if n.strip()]
    matched = [r for r in data["reply_list"] if r["username"] in names]
    info_echo(tid, f"新增与命中：({len(data['reply_list'])}, {len(matched)})")
    data["reply_list"] = matched
    if matched:
        return data


def monitor_action(matches):
    # 监控命中执行函数，可自定义
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
    event=monitor_event,
    action=monitor_action,
    criteria="",
):
    # 对若干主题进行持续监控，以 gap 秒为间隔循环访问
    # store 用于指定是否要在监控时对本地数据库 db_path 进行更新，这两个参数同时决定了基线轮次如何判断历史信息水位
    # force 用于指定基线轮次的行为，True：全量更新+历史信息也将参与命中判定；False：增量更新+仅基线建立后的新信息参与命中判定
    # 数据获取成功时，本函数将数据与 criteria 发送给 event → event 将返回命中其内部规则的数据 → 存在命中时，本函数调用 action
    # criteria 为可由 CLI 调用传入的字符串，其格式与意义取决于 event 的实现，如果说 event 决定了判定逻辑，criteria 则指定了判定对象
    # 比如当 event 的行为是“新增回复由特定用户发出时命中”时，criteria 就可以用来指定用户名列表
    # 当检测到主题被关闭或被删除时，以及连续访问失败达到 10 次时，停止对对应主题的监控
    last = {tid: -1 for tid, sf in links}
    targets = [[tid, sf, 0] for tid, sf in links]
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")

    def poll(tid, sf, floor, ecrof):
        data = kf.fetch_onetopic(tid, sf, force=ecrof, return_header=True)
        if data in ("closed", "deleted"):
            info_echo(tid, "监控退出（目标已经不可访问）")
            target[2] = False
            return []
        if data is False:
            target[2] += 1
            if target[2] < 10:
                info_echo(tid, f"访问失败第 {target[2]} 次")
            else:
                info_echo(tid, "监控退出（重试次数到达上限）")
                target[2] = False
            return []
        target[2] = 0
        if not ecrof:
            data["reply_list"] = [r for r in data["reply_list"] if r["floor"] > floor]
        return data

    while True:
        # 循环轮次的逻辑描述
        for target in targets:
            tid, sf, retry = target
            if retry is False or last[tid] < 0:
                continue
            data = poll(tid, sf, last[tid], False)
            if data:
                matches = event(data, criteria)
                if matches:
                    action(matches)
        # 基线轮次的逻辑描述
        for target in targets:
            tid, sf, retry = target
            if retry is False or last[tid] > -1:
                continue
            if not retry:
                info_echo(tid, "基线建立中")
            stored = kf.storage.get_topic_max_floor(tid)
            data = poll(tid, sf, stored, force)
            if not data:
                continue
            if stored < 0 or force:
                last[tid] = data["reply_list"][-1]["floor"]
            else:
                last[tid] = stored
            info_echo(tid, f"基线已建立：{last[tid]}")
            if force:
                matches = event(data, criteria)
                if matches:
                    action(matches)
        time.sleep(gap)


def info_echo(tid, text):
    print(f"{time.strftime('%m-%d %H:%M:%S')} [{tid}] {text}")


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
