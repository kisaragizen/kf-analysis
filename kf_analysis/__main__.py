""" __main__.py 采用了非常紧凑的写法（不然整体看起来会很丑）
    不过它也不需要什么可读性，唯一的作用就是将各种功能薄封装为 CLI 形式
    而所有 CLI 命令均已写在下方 """
""" CLI 命令调用（省略前缀 python -m kf_analysis）：
    fetch all [--force] [--db 路径]
        获取并解析所有板块的所有帖子数据，存入数据库
        可选参数 [--force]：决定是全量更新还是增量更新，缺省时为增量更新
        可选参数 [--db]：决定存储到那个数据库文件中，缺省时为默认数据库
    fetch board <fid> [--force] [--db 路径]
        获取并解析某板块的所有帖子数据，存入数据库，以 <fid> 指定板块
    fetch topic <link>... [--force] [--file 链接文件] [--db 路径]
        获取并解析某帖子数据，存入数据库
        命令行参数传递链接时：<link> 间以空格分隔，每个 <link> 都用引号包裹
        文件形式传递链接时：书写时注意每行一个链接，不需要带引号
    get json <link>
        获取并解析某帖子数据，但单独保存为 json 文件
    get usernames <link> [--dedup]
        获取某帖子用户名列表，指定参数 [--dedup] 时激活去重功能
    get homepage <link>
        获取并解析某用户主页信息
    state [--db 路径]
    buy <link> [--buy]
        主题购买，指定参数 [--buy] 时执行购买，否则仅查询价格
    transfer <用户名>[, <用户名>...] <amount> [--memo 附言]
        贡献转账，向一个或多个用户名转账 <amount>（HB）
        用户名间以半角逗号分隔（或半角逗号加空格）"""
import argparse, json, logging, re
from . import utils
from .coordinator import KFanalysis
from .actions import Actions, buy_topic, transfer_money


logger = logging.getLogger("kf-analysis")


def setup_logging():
    file = logging.FileHandler("error.log", encoding="utf-8")
    file.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    file.terminator = "\n\n"
    logger.addHandler(file)


def parse_link(link):
    r = utils.split_topic_link(link)
    if not r: print("链接输入非法"); raise SystemExit(1)
    return r


def main():
    setup_logging()
    parser = argparse.ArgumentParser(prog="kf-analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("target", choices=["all", "board", "topic"])
    fetch.add_argument("value", nargs="*")
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--file", default="")
    fetch.add_argument("--db", default="kf.db")
    get = sub.add_parser("get")
    get.add_argument("kind", choices=["json", "usernames", "homepage"])
    get.add_argument("link")
    get.add_argument("--dedup", action="store_true")
    state = sub.add_parser("state")
    state.add_argument("--db", default="kf.db")
    buy = sub.add_parser("buy")
    buy.add_argument("link")
    buy.add_argument("--buy", action="store_true")
    transfer = sub.add_parser("transfer")
    transfer.add_argument("username")
    transfer.add_argument("amount")
    transfer.add_argument("--memo", default="")
    args = parser.parse_args()
    if args.command in ("buy", "transfer"): actions = Actions(utils.load_config())
    elif args.command == "get": kf = KFanalysis(utils.load_config())
    else: kf = KFanalysis(utils.load_config(), db_path=args.db)
    if args.command == "buy":
        tid, sf = parse_link(args.link)
        price = buy_topic(actions.client, tid, sf, "buy" if args.buy else "")
        if price is None: print("购买失败")
        elif price == -1: print("已经购买")
        elif price == -2: print("无可购买内容")
        else: print(f"购买成功：{price}" if args.buy else f"价格查询：{price}")
    elif args.command == "transfer":
        names = [n.strip() for n in args.username.split(",") if n.strip()]
        if not names: print("用户名列表为空"); return
        for name in names: print(f"向 {name} 转账：" + transfer_money(actions.client, name, args.amount, memo=args.memo))
    if args.command == "fetch":
        if args.target == "all": kf.fetch_all(force=args.force)
        elif args.target == "board":
            if not args.value: print("缺少 fid"); return
            try: fid = int(args.value[0])
            except ValueError: print("fid 应为板块序号数字"); return
            if fid not in {f for _, f in kf.config.boardlist}: print("fid 错误或不存在于配置文件"); return
            kf.fetch_board(fid, force=args.force)
        elif args.target == "topic":
            if args.file:
                try:
                    with open(args.file, encoding="utf-8") as f: args.value += [line.strip() for line in f if line.strip()]
                except FileNotFoundError: print(f"链接文件 {args.file} 不存在"); return
            if not args.value: print("缺少 topic 链接"); return
            for i, (tid, sf) in enumerate(parse_link(link) for link in args.value): kf.fetch_onetopic(tid, sf, force=args.force, disp=True, index=i, total=len(args.value))
    elif args.command == "get":
        if args.kind == "homepage":
            uid = re.findall(r"uid=(\d+)", args.link); sf = re.findall(r"sf=([^&]+)", args.link)
            if not uid: print("请输入正确的用户主页链接"); return
            data = kf.get_homepage(int(uid[0]), sf[0] if sf else "")
            if not isinstance(data, dict): print(f"用户主页 {uid[0]} 获取失败"); return
            for key, val in data.items(): print(f"{key}：{val}")
            return
        tid, sf = parse_link(args.link)
        try: data = kf.get_topic_usernames(tid, sf, dedup=args.dedup) if args.kind == "usernames" else kf.get_topic_json(tid, sf)
        except Exception as e: print(f"帖子 ({tid}, {sf}) 获取失败，错误信息 {e}"); return
        if data in ("closed", "deleted"): print(f"该主题已被管理员关闭或删除: {data}")
        elif args.kind == "usernames" and isinstance(data, list): print(", ".join(data))
        elif isinstance(data, dict):
            with open("json_result.txt", "w", encoding="utf-8") as f: f.write(json.dumps(data, ensure_ascii=False, indent=2))
            print("数据已覆盖写入到 json_result.txt")
        else: print("获取失败")
    elif args.command == "state":
        stats = kf.storage.stats(); print(f"主题数: {stats['topic_count']}\n回复数: {stats['reply_count']}"); print(f"最近抓取时间: {stats['last_record_time']}\n")
        with open("error.log", encoding="utf-8") as f: print("".join(f.readlines()[-10:]))


if __name__ == "__main__": main()
