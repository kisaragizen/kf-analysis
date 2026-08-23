""" __main__.py 采用了超级紧凑写法（只有它是这样），可读性会很差
    不过它也不需要可读性，因为它的作用只有CLI 命令解析而已
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
        获取某帖子用户名列表，可选参数 [--dedup] 决定是否对列表进行去重
    get homepage <link>
        获取并解析某用户主页信息
    state [--db 路径]
    buy <link> [--buy]
        查询售价主题（默认仅查价），可选 [--buy] 执行购买；购买失败（余额不足等）会有提示
    transfer <username> <amount> [--memo 附言]
        论坛银行转账（hack.php 银行接口），向 <username> 转账 <amount>（HB）
        可选参数 [--memo]：附言（银行页面为 GBK 编码） """
import argparse, json, logging, re
from . import utils
from .coordinator import KFanalysis
from .actions import Actions, buy_topic, transfer_money


logger = logging.getLogger("kf-analysis")


def setup_logging():
    file = logging.FileHandler("error.log", encoding="utf-8"); file.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")); file.terminator = "\n\n"; logger.addHandler(file)


def parse_link(link):
    r = utils.split_topic_link(link)
    if not r: print("链接输入非法，请输入 kfpromax 域名的最小完整链接"); raise SystemExit(1)
    return r


def main():
    setup_logging()
    parser = argparse.ArgumentParser(prog="kf-analysis")
    sub = parser.add_subparsers(dest="command")
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
    buy.add_argument("link", help="售价主题链接")
    buy.add_argument("--buy", action="store_true", help="执行购买（默认仅查价）")
    transfer = sub.add_parser("transfer")
    transfer.add_argument("value", nargs="+", help="<username> <amount>")
    transfer.add_argument("--memo", default="", help="转账附言")
    args = parser.parse_args()
    if args.command in ("buy", "transfer"): actions = Actions(utils.load_config())
    elif args.command == "get": kf = KFanalysis(utils.load_config())
    else: kf = KFanalysis(utils.load_config(), db_path=args.db)
    if args.command == "buy":
        tid, sf = parse_link(args.link)
        price = buy_topic(actions.client, tid, sf, "buy" if args.buy else "")
        if price is None: print("购买失败：购买后仍显示售价框（余额不足或已被购买）")
        elif price == -1: print("已购买")
        elif price == -2: print("无可购买内容")
        else: print(f"购买成功，价格：{price}" if args.buy else f"可购买，价格：{price}")
    elif args.command == "transfer":
        if len(args.value) < 2: print("用法：transfer <username> <amount> [--memo 附言]"); return
        text = transfer_money(actions.client, args.value[0], args.value[1], memo=args.memo)
        print("银行响应：" + text[:300])
        return
    if args.command == "fetch":
        if args.target == "all": kf.fetch_all(force=args.force)
        elif args.target == "board":
            if not args.value: print("缺少 fid"); return
            try: fid = int(args.value[0])
            except ValueError: print("fid 需为数字"); return
            if fid not in {f for _, f in kf.config.boardlist}: print("未知 fid"); return
            kf.fetch_board(fid, force=args.force)
        elif args.target == "topic":
            if args.file:
                try:
                    with open(args.file, encoding="utf-8") as f: args.value += [line.strip() for line in f if line.strip()]
                except FileNotFoundError: print(f"链接文件 {args.file} 不存在"); return
            if not args.value: print("缺少 topic 链接"); return
            parsed = [parse_link(link) for link in args.value]
            for i, (tid, sf) in enumerate(parsed): kf.fetch_onetopic(tid, sf, force=args.force, disp=True, index=i, total=len(parsed))
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
            text = json.dumps(data, ensure_ascii=False, indent=2)
            with open("json_result.txt", "w", encoding="utf-8") as f: f.write(text)
            print("数据已覆盖写入到 json_result.txt")
        else: print("获取失败")
    elif args.command == "state":
        stats = kf.storage.stats(); print(f"主题数: {stats['topic_count']}\n回复数: {stats['reply_count']}"); print(f"最近抓取时间: {stats['last_record_time']}\n")
        with open("error.log", encoding="utf-8") as f: tail = f.readlines()[-10:]
        print("".join(tail))


if __name__ == "__main__": main()
