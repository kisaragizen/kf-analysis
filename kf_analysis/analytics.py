import json, sqlite3
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from . import utils


def text_length(text):
    if not text: return 0
    return len(text.encode("utf-8"))


def to_datetime(v):
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        return datetime.strptime(v.strip(), "%Y-%m-%d %H:%M:%S")
    return datetime.fromtimestamp(v)
def readable2unix(s): return int(to_datetime(s).timestamp())
def unix2readable(ts, fmt="%Y-%m-%d"): return to_datetime(ts).strftime(fmt)
def readable2weekday(ts): return "周" + "一二三四五六日"[to_datetime(ts).weekday()]


def query_data(start_time=None, end_time=None, username=None, board_name=None, db_path="kf.db", reverse=False):
    conds = []
    params = []
    if start_time is not None:
        conds.append("reply_time >= ?")
        params.append(readable2unix(start_time))
    if end_time is not None:
        conds.append("reply_time <= ?")
        params.append(readable2unix(end_time))
    if username is not None:
        conds.append("username = ?")
        params.append(username)
    if board_name is not None:
        conds.append("board_name = ?")
        params.append(board_name)
    where = " AND ".join(conds) if conds else "1"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT r.topic_id, r.reply_id, r.topic_sf, r.floor, r.username, "
            f"r.homepage_id, r.homepage_sf, r.reply_box_color, r.reply_time, r.reply_text, "
            f"r.record_time, r.status, r.image_list, r.complete, r.hidden_content, r.keyword_list, "
            f"t.board_id, t.board_name, t.title AS topic_title, t.reply_count, "
            f"t.topic_time, t.record_time AS topic_record_time, t.status AS topic_status "
            f"FROM reply r JOIN topic t ON r.topic_id = t.topic_id "
            f"WHERE {where} ORDER BY r.reply_time",
            params).fetchall()
        replies, topics = [], []
        tid_index = {}
        for row in rows:
            r = dict(row)
            for k in ("image_list", "hidden_content", "keyword_list"):
                r[k] = json.loads(r[k] or "[]")
            r["reply_length"] = text_length(r["reply_text"])
            r["topic_url"] = utils.topic_url(r["topic_id"], r["topic_sf"])
            tid = r["topic_id"]
            if tid not in tid_index:
                tid_index[tid] = len(topics)
                topics.append({
                    "topic_id": tid, "topic_sf": r["topic_sf"],
                    "board_id": r["board_id"], "board_name": r["board_name"],
                    "topic_title": r["topic_title"], "reply_count": r["reply_count"],
                    "topic_time": r["topic_time"], "record_time": r["topic_record_time"],
                    "status": r["topic_status"],
                    "topic_url": utils.topic_url(tid, r["topic_sf"]),
                    "reply_list": [],
                })
            del r["reply_count"], r["topic_time"], r["topic_record_time"], r["topic_status"]
            topics[tid_index[tid]]["reply_list"].append(r)
            replies.append(r)
        topics.sort(key=lambda t: t["topic_time"], reverse=reverse)
        if topics:
            tids = [t["topic_id"] for t in topics]
            placeholders = ",".join("?" * len(tids))
            agg_rows = conn.execute(
                f"SELECT topic_id, MAX(CASE WHEN floor = 0 THEN username END) AS username, "
                f"MAX(complete) AS complete FROM reply "
                f"WHERE topic_id IN ({placeholders}) GROUP BY topic_id", tids).fetchall()
            agg_map = {a["topic_id"]: a for a in agg_rows}
            for t in topics:
                agg = agg_map.get(t["topic_id"])
                t["username"] = agg["username"] if agg else None
                t["complete"] = agg["complete"] if agg else 0
        return replies, topics
    finally:
        conn.close()


def finish_plot(save, dpi=100, adjust=None):
    plt.tight_layout()
    if adjust: plt.subplots_adjust(**adjust)
    if save: plt.savefig(save, dpi=dpi)
    plt.show()


def annotate_values(x, y):
    for xi, yi in zip(x, y): plt.text(xi, yi, f"{yi:g}", ha="center", va="bottom")


def output_plot_bar(x, y, title=None, save=None, annotate=True, color="lightpink",
                    figsize=(16, 6), rotation=45):
    plt.figure(figsize=figsize)
    plt.bar(x, y, color=color)
    plt.axhline(y=0, zorder=0, color="black")
    if annotate:
        annotate_values(x, y)
    if title:
        plt.title(title)
    plt.xticks(x, rotation=rotation)
    finish_plot(save)


def output_plot_line(x, y, title=None, save=None, annotate=True, color="skyblue",
                     figsize=(16, 6), rotation=45):
    plt.figure(figsize=figsize)
    plt.plot(x, y, color=color, marker="o", markersize=8, linewidth=2.5)
    plt.grid(axis="y", alpha=0.3)
    if annotate:
        annotate_values(x, y)
    if title:
        plt.title(title)
    plt.xticks(x, rotation=rotation)
    finish_plot(save)


def calendar_heatmap(day_counts, start, end, title=None, save=None, cmap="OrRd",
                     count_label="回复贴数量", figsize=(22, 13), cell_height=0.5):
    start, end = to_datetime(start), to_datetime(end)
    counts = {to_datetime(k).date(): v for k, v in day_counts.items()}
    start_monday = start - timedelta(days=start.weekday())
    end_sunday = end + timedelta(days=6 - end.weekday())
    weeks = (end_sunday - start_monday).days // 7 + 1
    rows = (weeks + 1) // 2
    data = np.full((rows, 14), np.nan)
    mmdd = np.full((rows, 14), "", dtype=object)
    month_1st_row = {}
    s, e = start.date(), end.date()
    for row in range(rows):
        for col in range(14):
            week = row * 2 + col // 7
            cur = start_monday + timedelta(days=week * 7 + col % 7)
            d = cur.date()
            if week >= weeks or not s <= d <= e:
                continue
            m = cur.strftime("%m%d")
            data[row, col] = counts.get(d, 0)
            mmdd[row, col] = m
            if m.endswith("01"):
                month_1st_row.setdefault(int(m[:2]), row)
    fig, ax = plt.subplots(figsize=(figsize[0], 2.4 + rows * cell_height))
    cm = plt.colormaps[cmap]
    cm.set_bad(color="#F0F0F0")
    mesh = ax.pcolormesh(np.ma.masked_invalid(data), cmap=cm, vmin=0)
    ax.set_aspect("auto")
    ax.invert_yaxis()
    ax.set_ylim(rows, 0)
    valid = data[~np.isnan(data)]
    norm = plt.Normalize(vmin=0, vmax=valid.max() if valid.size else 1)
    for row in range(rows):
        for col in range(14):
            if not mmdd[row, col]:
                continue
            deep = norm(data[row, col]) >= 0.85
            ax.text(col + 0.5, row + 0.5, f"{int(data[row, col])}",
                    ha="center", va="center", fontsize=12, fontweight="bold",
                    color="white" if deep else "#222222")
            ax.text(col + 0.91, row + 0.91, mmdd[row, col],
                    ha="right", va="bottom", fontsize=8.5, fontweight="bold",
                    color="white" if deep else "#333333")
    ax.vlines(7, 0, rows, color="#999999", linewidth=2.5, alpha=0.45)
    for row in month_1st_row.values():
        if row > 0:
            ax.axhline(y=row, color="#999999", linewidth=1.5, alpha=0.35)
    ax.set_xticks(np.arange(14) + 0.5)
    ax.set_xticklabels(["周一", "周二", "周三", "周四", "周五", "周六", "周日"] * 2,
                       fontsize=10.5, fontweight="bold")
    for i, tick in enumerate(ax.get_xticklabels()):
        tick.set_color("#C62828" if i % 7 >= 5 else "#333333")
    ax_top = ax.twiny()
    ax_top.set_xlim(ax.get_xlim())
    ax_top.set_xticks([3.5, 10.5])
    ax_top.set_xticklabels(["第一周", "第二周"], fontsize=11.5, fontweight="bold", color="#444444")
    ax_top.tick_params(length=0, pad=10)
    ax_top.spines["top"].set_visible(False)
    ax.set_yticks([p + 0.5 for p in month_1st_row])
    ax.set_yticklabels([f"{m}月" for m in month_1st_row],
                       fontsize=10, fontweight="bold", color="#444444")
    ax.tick_params(axis="y", length=0, pad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylim(rows, 0)
    if title:
        ax.set_title(title, fontsize=18)
    cbar_ax = fig.add_axes([0.55, 0.045, 0.38, 0.025])
    cbar = fig.colorbar(mesh, cax=cbar_ax, orientation="horizontal")
    cbar.set_label(count_label, fontsize=11, fontweight="bold", color="#333333", labelpad=8)
    cbar.ax.tick_params(labelsize=8.5)
    cbar.outline.set_visible(False)
    finish_plot(save, adjust={"bottom": 0.14, "right": 0.93})


def plot_daily_bars(daily, title="每日新增账号估算", ylabel="账号/天", save=None,
                    color="cornflowerblue", figsize=(80, 6), ylim=None):
    x = [to_datetime(d) for d, _ in daily]
    y = [v for _, v in daily]
    plt.figure(figsize=figsize)
    plt.bar(x, y, color=color, width=1.0)
    ax = plt.gca()
    years = [date(yy, 1, 1) for yy in range(x[0].year, x[-1].year + 1)]
    ax.set_xticks(years)
    ax.set_xticklabels([str(yy.year) for yy in years])
    if ylim:
        plt.ylim(0, ylim)
        for xi, yi in zip(x, y):
            if yi > ylim:
                plt.text(xi, ylim * 0.98, f"{yi:.0f}", ha="right", va="top", fontsize=8, rotation=90)
    plt.title(title, fontsize=18)
    plt.ylabel(ylabel)
    finish_plot(save)
