"""本文件用于将各种功能封装为 CLI 调用
以下所有命令在实际运行时都需要前缀 python -m kf_analysis
======================================================================
fetch all [--force] [--db 路径]
    获取并解析所有板块的所有帖子数据，存入数据库
    可选参数 [--force]：决定是全量更新还是增量更新，缺省时为增量更新
    可选参数 [--db]：决定存储到哪个数据库文件中，缺省时为默认数据库
fetch board <fid> [--force] [--db 路径]
    获取并解析某板块的所有帖子数据，存入数据库，以 <fid> 指定板块
fetch topic <link>... [--force] [--file 链接文件] [--db 路径]
    获取并解析某帖子数据，存入数据库
    命令行参数传递链接时：<link> 间以空格分隔，每个 <link> 都以引号包裹
    文件形式传递链接时：每行一个链接，不需要带引号
search [--keyword | --username | --authorid] [--fid] [--store] [--force] [--db 路径]
    按标题关键词、用户名或用户 uid 搜索主题，可选是否同步入库
    要注意 keyword、username 与 authorid 只能指定且必须指定其中之一
    可选参数 [--fid]：只能取单个板块序号，缺省时为全站搜索
    可选参数 [--store]：决定是否同步入库所有搜索结果，其缺省时为仅查询
get json <link>
    获取并解析某帖子数据，不操作数据库，仅支持单个链接
    解析完成后会将数据存储到同目录文本文件中（JSON）
get usernames <link> [--dedup]
    获取某帖子用户名列表，不操作数据库，仅支持单个链接
    可选参数 [--dedup]：决定是否激活去重功能，缺省时不激活
get homepage <link>
    获取并解析某用户主页信息，不操作数据库，仅支持单个链接
buy <link> [--buy]
    主题购买，指定参数 [--buy] 时执行购买，否则仅查询价格
transfer <username_list> <amount> [--memo]
    贡献转账，向一个或多个用户名转账 <amount>（HB）
    username_list 为以半角逗号分隔用户名的单字符串
monitor topic <link>... [--file] [--store] [--force] [--criteria] [--gap] [--db 路径]
    持续监控指定主题，以 gap 秒为间隔循环增量抓取
    可选参数 [--gap]：决定监控周期（秒），缺省值为 300
    可选参数 [--store]：决定基线取自数据库还是实时值，也决定是否对指定数据库进行写入
    可选参数 [--force]：用于指定基线轮次的行为
                        True 时为全量更新+历史信息也将参与命中判定
                        False 时为增量更新+仅基线建立后的新信息参与命中判定
    可选参数 [--criteria]：判定依据字符串，格式与意义取决于 event 的实现
                           默认监控行为「当新增回复由特定用户发出时，进行气泡提示」
                           默认监控行为下该参数用于传递以半角逗号分隔的用户名列表
monitor board <fid>... [--file] [--store] [--force] [--criteria] [--func] [--gap] [--pages] [--db 路径]
    持续监控指定板块，以 gap 秒为间隔循环增量抓取
    可选参数 [--store]：仅决定基线取自数据库还是实时值，数据库是否写入要看 event 的实现
    可选参数 [--force]：用于指定基线轮次的行为
                        True 时为对扫描到的全部主题进行历史信息判定
    可选参数 [--func]：决定使用哪种默认 event，缺省值为 A
                       A 为展开优先（先展开后判定，全部动态主题入库）
                       B 为判定优先（先判定后展开，只有命中主题入库）
    可选参数 [--criteria]：判定依据字符串，格式与意义取决于 event 的实现
                           在两种默认 event 中，该参数用于传递以半角逗号分隔的用户名列表
    可选参数 [--pages]：决定每轮的扫描页数，缺省值为 2"""

import argparse
import json
import logging
import re
import time
from . import utils
from .actions import Actions, buy_topic, gbk_form, transfer_money
from .coordinator import KFanalysis
from .monitor import (
    board_event_expand_first,
    board_event_judge_first,
    monitor_board,
    monitor_topic,
)

logger = logging.getLogger("kf-analysis")


def setup_logging():
    file = logging.FileHandler("error.log", encoding="utf-8")
    file.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    file.terminator = "\n\n"
    logger.addHandler(file)


def parse_link(link):
    r = utils.split_topic_link(link)
    if not r:
        print("链接输入非法")
        raise SystemExit(1)
    return r


def build_parser():
    parser = argparse.ArgumentParser(prog="kf-analysis")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch")
    fetch.add_argument("target", choices=["all", "board", "topic"])
    fetch.add_argument("value", nargs="*")
    fetch.add_argument("--file")
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--db", default="kf.db")

    get = sub.add_parser("get")
    get.add_argument("kind", choices=["json", "usernames", "homepage"])
    get.add_argument("link")
    get.add_argument("--dedup", action="store_true")

    search = sub.add_parser("search")
    search_target = search.add_mutually_exclusive_group(required=True)
    search_target.add_argument("--keyword")
    search_target.add_argument("--username")
    search_target.add_argument("--authorid")
    search.add_argument("--fid", default="all")
    search.add_argument("--store", action="store_true")
    search.add_argument("--force", action="store_true")
    search.add_argument("--db", default="kf.db")

    buy = sub.add_parser("buy")
    buy.add_argument("link")
    buy.add_argument("--buy", action="store_true")
    transfer = sub.add_parser("transfer")
    transfer.add_argument("username")
    transfer.add_argument("amount")
    transfer.add_argument("--memo", default="")
    state = sub.add_parser("state")
    state.add_argument("--db", default="kf.db")

    monitor = sub.add_parser("monitor")
    monitor.add_argument("target", choices=["topic", "board"])
    monitor.add_argument("value", nargs="*")
    monitor.add_argument("--file")
    monitor.add_argument("--store", action="store_true")
    monitor.add_argument("--force", action="store_true")
    monitor.add_argument("--criteria", default="")
    monitor.add_argument("--gap", type=int, default=300)
    monitor.add_argument("--pages", type=int, default=2)
    monitor.add_argument("--func", choices=["A", "B"], default="A")
    monitor.add_argument("--db", default="kf.db")

    return parser


def main():
    setup_logging()
    args = build_parser().parse_args()

    if args.command == "monitor":
        if args.target == "topic":
            links = list(args.value)
            if args.file:
                try:
                    with open(args.file, encoding="utf-8") as f:
                        links += [line.strip() for line in f if line.strip()]
                except FileNotFoundError:
                    print("无法打开指定文件")
                    return
            if not links:
                print("待处理主题列表为空")
                return
            parsed = [parse_link(link) for link in links]
            monitor_topic(
                utils.load_config(),
                parsed,
                gap=args.gap,
                store=args.store,
                force=args.force,
                criteria=args.criteria,
                db_path=args.db,
            )
            return
        elif args.target == "board":
            boards = list(args.value)
            if args.file:
                try:
                    with open(args.file, encoding="utf-8") as f:
                        boards += [line.strip() for line in f if line.strip()]
                except FileNotFoundError:
                    print("无法打开指定文件")
                    return
            try:
                fids = [int(b) for b in boards]
            except ValueError:
                print("板块序号应为数字")
                return
            config = utils.load_config()
            unknown = set(fids) - set([bf for bn, bf in config.boardlist])
            if not fids:
                print("待处理板块列表为空")
                return
            elif unknown:
                print(f"如果你确定板块序号 {unknown} 存在，", end="")
                print("请先在 configure.json 中填写它们")
                return
            if args.func == "A":
                event = board_event_expand_first
            elif args.func == "B":
                event = board_event_judge_first
            monitor_board(
                config,
                fids,
                gap=args.gap,
                pages=args.pages,
                store=args.store,
                force=args.force,
                criteria=args.criteria,
                db_path=args.db,
                event=event,
            )
            return

    if args.command in ("buy", "transfer"):
        actions = Actions(utils.load_config())
    if args.command == "buy":
        tid, sf = parse_link(args.link)
        price = buy_topic(actions.client, tid, sf, "buy" if args.buy else "check")
        if not price:
            print("购买失败")
        elif price == -1:
            print("已经购买")
        elif price == -2:
            print("无可购买内容")
        else:
            print(f"购买成功：{price}" if args.buy else f"价格查询：{price}")
    elif args.command == "transfer":
        names = [n.strip() for n in args.username.split(",") if n.strip()]
        if not names:
            print("用户名列表为空")
            return
        for name in names:
            print(f"向 {name} 转账：", end="")
            print(transfer_money(actions.client, name, args.amount, memo=args.memo))

    if args.command == "fetch":
        kf = KFanalysis(utils.load_config(), db_path=args.db)
        if args.target == "all":
            kf.fetch_all(force=args.force)
        elif args.target == "board":
            if not args.value:
                print("需要指定板块序号")
                return
            try:
                fid = int(args.value[0])
            except ValueError:
                print("板块序号应为数字")
                return
            if fid not in {f for _, f in kf.config.boardlist}:
                print("如果你确定该板块序号存在，", end="")
                print("请先在 configure.json 中填写它")
                return
            kf.fetch_board(fid, force=args.force)
        elif args.target == "topic":
            if args.file:
                try:
                    with open(args.file, encoding="utf-8") as f:
                        args.value += [line.strip() for line in f if line.strip()]
                except FileNotFoundError:
                    print("无法打开指定文件")
                    return
            if not args.value:
                print("待处理主题列表为空")
                return
            parsed = [parse_link(link) for link in args.value]
            for i, (tid, sf) in enumerate(parsed):
                kf.fetch_onetopic(
                    tid,
                    sf,
                    index=i,
                    total=len(parsed),
                    force=args.force,
                    disp=True,
                )

    if args.command == "search":
        kf = KFanalysis(utils.load_config(), db_path=args.db)
        keyword = (
            gbk_form({"keyword": args.keyword}).decode().split("=", 1)[1]
            if args.keyword
            else None
        )
        pwuser = (
            gbk_form({"pwuser": args.username}).decode().split("=", 1)[1]
            if args.username
            else None
        )
        result = kf.get_search_results(
            keyword=keyword,
            pwuser=pwuser,
            authorid=args.authorid,
            fid=args.fid,
            store=args.store,
            force=args.force,
        )
        if result is False or args.store:
            return
        print()
        for row in result:
            print(utils.topic_url(row["topic_id"], row["topic_sf"]))
            print(f"    -{row['topic_title']}")
            print(f"    -{row['board_name']}")
            print(f"    -{row['topic_poster']}")
            print(f"    -{row['last_reply_time']}")
        return

    if args.command == "get":
        kf = KFanalysis(utils.load_config())
        if args.kind == "homepage":
            uid = re.findall(r"uid=(\d+)", args.link)
            sf = re.findall(r"sf=([^&]+)", args.link)
            if not uid or not sf:
                print("用户主页链接格式错误")
                return
            data = kf.get_homepage(int(uid[0]), sf[0])
            if not isinstance(data, dict):
                print("用户主页信息获取失败")
                return
            for key, val in data.items():
                print(f"{key}：{val}")
            return
        tid, sf = parse_link(args.link)
        try:
            if args.kind == "usernames":
                data = kf.get_topic_usernames(tid, sf, dedup=args.dedup)
            elif args.kind == "json":
                data = kf.get_topic_json(tid, sf)
        except Exception:
            print("数据获取失败A")
            return
        if data in ("closed", "deleted"):
            print("该主题已被关闭或删除")
        elif args.kind == "usernames" and isinstance(data, list):
            print(", ".join(data))
        elif args.kind == "json" and isinstance(data, dict):
            with open("json_result.txt", "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
            print("数据已写入同目录文本文件")
        else:
            print("数据获取失败B")
        return

    if args.command == "state":
        stats = KFanalysis(utils.load_config(), db_path=args.db).storage.stats()
        last = stats["last_record_time"]
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last))
        print(f"主题数: {stats['topic_count']}\n回复数: {stats['reply_count']}")
        print(f"最后抓取时间: {stamp}\n")
        with open("error.log", encoding="utf-8") as f:
            print("".join(f.readlines()[-10:]))


if __name__ == "__main__":
    main()
