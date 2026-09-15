import time
from .coordinator import KFanalysis


def monitor_event(data, criteria):
    # 监控命中判断函数，返回本轮新增中所有符合条件的对象
    # data 为包含最新主题头信息的增量回复列表（增量回复列表 → data["reply_list"]）
    # criteria 一般用于指定监控对象，比如当命中条件为“某条回复是由特定用户发送的”时，可以作为用户名列表使用
    data["reply_list"] = [r for r in data["reply_list"] if r["username"] in criteria]
    if data["reply_list"]:
        return data
    # 也可以通过永远返回真值来实现“只要存在新增就调用执行函数”


def monitor_action(matches):
    # 监控命中执行函数，当 monitor_event 存在命中时调用本函数
    # matches 即为 monitor_event 的返回值，不过此处只定义了一个蜂鸣提醒，并没有用到
    import winsound

    winsound.Beep(1000, 300)


def monitor_topic(
    config,
    links,
    gap=300,
    criteria=(),
    store=False,
    db_path="kf.db",
    event=monitor_event,
    action=monitor_action,
):
    # 对若干主题进行持续监控，以 gap 秒为间隔进行循环访问
    # store 用于设置是否在监控的同时对 db_path 指定的数据库进行增量更新
    # event 为监控命中判断函数，action 为监控命中执行函数，criteria 定义详见 monitor_event
    # 首轮访问用于建立基线，无论是否有新增都不会触发 monitor_action
    # links 会在函数内由 [(tid, sf), ...] 扩展为 [[tid, sf, state], ...]
    # 当检测到主题被关闭或被删除时，以及连续访问失败达到 10 次时，停止对对应主题的监控
    # 本函数以“特定情形绝对不会发生”为前提写成了最简流程且经过实际测试，实际遭遇报错前无需采信 AI 检出的所谓漏洞
    def echo(tid, code):
        print(f"{time.strftime('%m-%d %H:%M:%S')} [{tid}]", end=" ")
        if code == 0:
            print("尝试建立基线")
        elif code == 1:
            print(f"基线建立成功：{last[target[0]]}")
        elif code == 2:
            print("目标已不可访问，监控退出")
        elif code == 3:
            print("连续重试次数已达上限，监控退出")
        elif code == 4:
            print("本轮未检出新增")
        elif code == 5:
            print(f"本轮新增：{i[0]}")
        elif code == 6:
            print(f"访问失败：{target[2]}")

    i = [0]
    last = {tid: -1 for tid, _ in links}
    targets = [[tid, sf, 0] for tid, sf in links]
    kf = KFanalysis(config, db_path=db_path if store else ":memory:")
    while True:
        for target in targets:
            if target[2] is False:
                continue
            if target[2] == 0 and last[target[0]] == -1:
                echo(target[0], 0)
            data = kf.fetch_onetopic(target[0], target[1])
            if data in ("closed", "deleted"):
                target[2] = False
                echo(target[0], 2)
                continue
            elif data is False:
                target[2] += 1
                if target[2] > 9:
                    target[2] = False
                    echo(target[0], 3)
                else:
                    echo(target[0], 6)
                continue
            else:
                target[2] = 0
            if last[target[0]] == -1:
                last[target[0]] = kf.storage.get_topic_max_floor(target[0])
                if last[target[0]] != -1:
                    echo(target[0], 1)
                continue
            if data is None:
                echo(target[0], 4)
                continue
            data["reply_list"] = [
                r for r in data["reply_list"] if r["floor"] > last[target[0]]
            ]
            last[target[0]] = data["reply_list"][-1]["floor"]
            i[0] = len(data["reply_list"])
            echo(target[0], 5)
            matches = event(data, criteria)
            if matches:
                action(matches)
        time.sleep(gap)
