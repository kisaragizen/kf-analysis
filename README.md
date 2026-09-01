# kf-analysis

绯月论坛活跃度数据获取与分析项目，v2.0.0 架构重构完成。  
v2.1.0 支持了部分论坛动作（发帖/编辑/买贴/转账），v2.2.0 完成了对任意 uid 注册时间的建模估算。  
数据获取支持 CLI 与 Python API 两种调用方式，数据持久化采用 SQLite，数据分析由 activity_analysis.ipynb 完成。  
移除原有硬编码逻辑，支持板块级与主题级增量抓取，并大幅优化页面解析逻辑与数据查询性能。  
经 216,389 条回复数据实测，数据抓取与入库结果符合预期（2026-09-01 时数据）。  

* 本项目运行在 bbs.kfpromax.com 域名下。  
* 本项目的文件内注释比 README.md 更详细。


## 配置填写
编辑 `kf_analysis/configure.json`，填写 `User-Agent`、`Cookie` 与 `Proxy` 信息。  
 `User-Agent` 与 `Cookie` 必须保持匹配，否则可能导致请求失败。`Proxy` 留空则使用直连。  
**除非你知道自己在做什么，否则不要改动四个 `timegap` 属性的默认值。**  
`boardlist` 用于指定 `fetch all` 命令需要获取的板块。


## CLI 调用
以下命令均省略前缀 `python -m kf_analysis`。  

CLI 命令主要分为三类：  
* `fetch`：获取并解析数据，并将结果写入默认或指定的数据库。  
* `get`：获取并解析数据，但不写入数据库，而是将结果输出到屏幕或写入文件。  
* `buy`、`transfer`：售价主题查价/购买；论坛银行转账。  
（并非全部论坛动作都有 CLI 调用支持，这是主动设计，详见**包内函数调用**章节）

**fetch 类命令**
```text
fetch all [--force] [--db <路径>]             # 获取所有板块的数据
fetch board <fid> [--force] [--db <路径>]     # 获取指定板块的数据
fetch topic <link>... [--force] [--file] [--db <路径>]    # 获取指定主题的数据
                                                          # 多个链接以空格分隔，各自使用引号包裹
                                                          # --file 指定包含主题链接的文件，每行一个链接
```
* `--force`：强制执行全量抓取；不指定时执行普通增量抓取。  
* `--db <路径>`：指定数据写入的数据库；不指定时使用默认数据库 `kf.db`。

**get 类命令**
```text
get json <link>                # 解析指定主题，并将完整数据写入 json_result.txt
get usernames <link> [--dedup] # 输出指定主题的参与用户列表；--dedup 指定是否去重
get homepage <link>            # 输出指定用户的主页信息
```

**buy / transfer 命令**
```text
buy <link> [--buy]                                             # 主题购买功能
transfer <username>[, <username>...] <amount> [--memo <附言>]  # 贡献转账功能
```
* `buy`：仅当指定 `--buy` 参数时才会执行购买，否则执行价格查询。  
* `transfer`：向一个或多个账号转账贡献，多个用户名以半角逗号分隔。

**查询数据库当前状态**
```text
state [--db <路径>]    # 返回数据库当前状态以及错误日志的最新十行
```

**调用示例**
```
python -m kf_analysis fetch all
python -m kf_analysis fetch board 5
python -m kf_analysis fetch topic "https://bbs.kfpromax.com/read.php?tid={$TID}&sf={$SF}"
python -m kf_analysis fetch topic --file links.txt
python -m kf_analysis get json "https://bbs.kfpromax.com/read.php?tid={$TID}&sf={$SF}"
python -m kf_analysis get usernames "https://bbs.kfpromax.com/read.php?tid={$TID}&sf={$SF}"
python -m kf_analysis get homepage "https://bbs.kfpromax.com/profile.php?action=show&uid={$UID}&sf={$SF}"
python -m kf_analysis buy "https://bbs.kfpromax.com/read.php?tid={$TID}&sf={$SF}" --buy
python -m kf_analysis transfer "{$USERNAME1}, {$USERNAME2}" 0.5 --memo "{$MEMO}"
python -m kf_analysis state
```


## 包内函数调用
包内调用分为三个层级：**`analyser` 纯解析函数**、**`KFanalysis` 封装类**与 **`Actions` 封装类**。

**纯解析函数（`analyser`）**  
`analyser` 提供与网络请求、数据库无关的纯解析函数。  
调用方负责准备页面原始数据，并根据需要自行处理解析结果。
```python
from bs4 import BeautifulSoup
from kf_analysis import analyser

soup = BeautifulSoup(html_text, "lxml")                     # html_text 为页面原始字节
status = analyser.check_page_status(soup)                   # 判断主题状态：normal / closed / deleted / incorrect
info = analyser.parse_topic_info(soup, tid, sf)             # 根据第一页的 soup 解析主题头信息并返回 dict
replies = analyser.parse_replies([html_text], tid, sf)      # 传入 html_text 列表，解析所有楼层信息并返回 dict
```

* `analyser` 包含的其他函数：
    * `parse_board_page(soup)` → 解析板块页，返回该页所有主题的 URL 列表。
    * `parse_profile_page(soup)` → 解析用户主页信息，返回 dict。
* 以上仅为简易调用示例，更多说明请参阅 `analyser.py` 相关注释。

**KFanalysis 封装类（`coordinator`）**  
`KFanalysis` 对数据获取、解析及数据库操作进行统一封装。  
**CLI 调用只是 `KFanalysis` 的薄封装**，与 Python API 使用相同的业务逻辑。
```python
from kf_analysis import utils
from kf_analysis.coordinator import KFanalysis

cfg = utils.load_config()
kf = KFanalysis(cfg, db_path="kf.db")

kf.fetch_all(force=False)                            # ↔ fetch all
kf.fetch_board(5, force=False)                       # ↔ fetch board 5

tid, sf = utils.split_topic_link(link)               # 从链接中拆出帖号与安全码
kf.fetch_onetopic(tid, sf, force=False, disp=False)  # ↔ fetch topic

data = kf.get_topic_json(tid, sf)                    # ↔ get json
names = kf.get_topic_usernames(tid, sf, dedup=False) # ↔ get usernames
info = kf.get_homepage(uid, sf, db=False)            # ↔ get homepage
stats = kf.storage.stats()                           # ↔ state
```

* `fetch_all` 是多次 `fetch_board` 的调用，
* `fetch_board` 是多次 `fetch_onetopic` 的调用。
* `fetch_onetopic` 相关说明：
    * 返回值为 `dict` 时代表获取成功（增量更新时自动附带 `incremental` 标记）；
    *  `None` 无增量，`False` 访问失败，`"closed"` 主题关闭，`"deleted"` 主题删除；
    * 主题被关闭或删除时，若数据库中尚无该主题则插入对应的占位条目；
    * 若数据库中存在该主题，秉持数据完整原则不进行覆盖。
    * 访问失败可能原因为安全码错误/帖子不存在/网络限制/服务器拒绝；
    * 访问失败不对数据库进行任何写入，错误信息也将被记录至 `error.log`。
* `get_homepage` 相关说明：
    * db=False 时，仅返回获取到的 dict；
    * db=True 时，将信息同步写入 hp.db 中。
    * 该函数没有增量更新功能，使用时需要前置检测。

**Actions 封装类（`actions`）**  
发帖/编辑/原始内容获取/购买/转账（前三种功能暂不考虑实现 CLI 调用）。
```python
from kf_analysis.actions import Actions, buy_topic, transfer_money

acts = Actions(config)                                    # config 可缺省，缺省时会从配置文件读
acts.post_reply(tid, sf, "正文")                          # 回复贴发帖函数
acts.post_topic(fid, "正文", title="标题")                # 主题帖发帖函数
acts.edit_post(tid, sf, pid, article, content="新正文")   # 帖子编辑函数
data = acts.get_post_content(tid, sf, pid, article)       # 获取帖子原始内容
price = buy_topic(acts.client, tid, sf)                   # 查价：价格 / -1 已购买 / -2 无可购买内容
buy_topic(acts.client, tid, sf, "buy")                    # 执行购买，失败返回 None
transfer_money(acts.client, "username", 0.5, memo="附言") # 银行转账
```

* 目前 `post_topic` 函数只支持**没有强制二级分类的普通板块**。
* 帖子原始内容指帖子 bbcode 标签尚未经服务器转义的原始文本，需要对目标贴子的编辑权限。
* **以下功能未列出**：`upload_image`, `search_user_sf`, `search_topic_sf`。

**其他重要函数**  
```python
from kf_analysis import analytics
replies, topics = analytics.query_data(start_time, end_time, username, board_name, db_path, reverse)
# 每个参数都是可缺省的，全部缺省则读入整个数据库，否则按照参数指定的范围读取数据
# 返回值有两个，分别是散装回复列表与按主题聚合的回复列表
```


## 数据库结构
kf.db 分为 topic 与 reply 两张表，topic 表只存储主题头信息，主题楼则被视作楼层数为零的回复。  
`image_list`, `hidden_content`, `keyword_list` 以 JSON 形式存库，由 `query_data` 函数读取时解析回 list。
```
topic 表：
topic_id    INTEGER PRIMARY KEY,   #主题链接 tid（帖号）
topic_sf    TEXT,                  #主题链接 sf （安全码）
board_id    INTEGER,               #所属板块 fid
board_name  TEXT,                  #所属板块名称
title       TEXT,                  #主题标题
reply_count INTEGER,               #回复量（包含主题第零楼）
topic_time  INTEGER,               #开帖时间 timestamp(unix)
record_time INTEGER,               #信息获取时间 timestamp(unix)
status      TEXT                   #active 正常 / closed 被关 / deleted 被删
```
```
reply 表：
reply_id        TEXT,        #回复编号（主楼=TPC<tid>，回复=PID<pid>）
topic_id        INTEGER NOT NULL REFERENCES topic(topic_id),   #所属主题 tid
topic_sf        TEXT,        #所属主题 sf
floor           INTEGER,     #楼层号
username        TEXT,        #回帖人用户名
homepage_id     INTEGER,     #用户主页 uid（禁言/删号用户为空）
homepage_sf     TEXT,        #用户主页 sf （即便被禁言/删号也非空）
reply_box_color TEXT,        #回复框颜色
reply_time      INTEGER,     #回帖时间
record_time     INTEGER,     #信息获取时间
reply_text      TEXT,        #紧凑化正文（若被禁言为 NULL/若被隐藏为提示信息）
status          TEXT,        #active 正常 / hidden 隐藏 / banned 禁言或删号
image_list      TEXT,        #图片 url 列表，JSON 数组字符串
complete        INTEGER,     #权限框是否全部解锁：0 不存在权限框；1 有且全部可读；2 存在部分或全部不可读
hidden_content  TEXT,        #已解锁的权限框内容，JSON
keyword_list    TEXT,        #引用的用户名关键词，JSON
PRIMARY KEY (topic_id, reply_id)
```

hp.db 是 `get_homepage` 函数在 db=True 时的存储对象。
```
homepage 表：
uid      INTEGER PRIMARY KEY,   #用户主页 uid
sf       TEXT,                  #用户主页 sf
username TEXT,                  #用户名称
regdate  TEXT,                  #注册日期
ok       INTEGER                #是否获取成功：1 成功；0 失败
```


## 数据分析
数据分析部分依赖本项目的 `analytics` 模块，由 `activity_analysis.ipynb` 完成。

* **Cell 1**：`query_data` 函数及其参数的说明
* **Cell 2**：调用 `query_data`，从数据库中读取符合指定条件的全部主题及回复数据。
* **Cell 3**：总体活跃度统计与可视化，包括：
     * 总活跃主题数及日均值；
     * 总新增回复数及日均值；
     * 总参与人数及日均值；
     * 每日回复量日历热力图；
     * 每日发言用户数折线图；
     * 各板块活跃主题数、新增回复数柱状图。
* **Cell 4**：用户活跃度排行，包括回复数量、回复字节数及活跃天数比例。
* **Cell 5**：将 Cell 4 所得数据渲染为有颜色分区的表格图像。
* **Cell 6**：账号新增与留存分析：前置单元A，将未入库的账号补入hp.db以提升分析精度。
* **Cell 7**：账号新增与留存分析：前置单元B，统计时段回复数量分布（假设注册数量分布权重）。
* **Cell 8**：账号新增与留存分析：根据 Cell 7 所得权重估算时刻T用户数量并输出天粒度柱状图。
* **Cell 9**：统计期间活跃账号的留存情况（注册年份分布）。
* **Cell A**：主题热度排行，包括新增回复数量、讨论持续天数。
* **Cell B**：资源主题贡献排行，分为整体与自购两部分。

```
关于任意uid注册时间的建模估算（复制自cell8）：
假设我们有一张24小时热度分布权重表，表中元素相加为1
当已知点数量为1，代表将一天分成了2份，接下来我们需要在权重表中找到从左向右加和到恰好等于50%的点
当已知点数量为n，代表将一天分成了n+1份，接下来我们需要在权重表中分别找到从左向右加和恰好等于k/(n+1)处的点
（实际上是先定位到小时然后在小时内线性插值，关于此处精度的改善可以从权重表入手，在上一个cell提高权重表时间粒度，但这也意味着更长的计算时间）
为避免重复计算，先找出单日已知点数量的最大值N，然后前置地分别算出当已知点数量为1到N时，每个点的对应时刻，后面只需要查表赋值就好
为了得到T时刻的uid最大值，我们需要找到已知点中早于T与晚于T的最近点，然后根据Ut=Ua+(Ub-Ua)×Wa得到结果，Wa指时刻A到时刻T占时刻A到时刻B的权重比例
```

绘图函数：
```python
from kf_analysis import analytics

analytics.output_plot_bar(x, y, title, save, annotate, color, figsize, rotation)                          # 柱状图
analytics.output_plot_line(x, y, title, save, annotate, color, figsize, rotation)                         # 折线图
analytics.calendar_heatmap(day_counts, start, end, title, save, cmap, count_label, figsize, cell_height)  # 热力图
analytics.plot_daily_bars(daily, title, save, color, figsize, ylim)                                       # 每日新增柱状图
```


## 文件结构
```
kf_analysis/
├── __main__.py           # CLI 入口
├── configure.json        # 配置文件
├── coordinator.py        # 行为编排
├── service.py            # 网络请求与数据库操作
├── analyser.py           # 页面解析
├── actions.py            # 论坛动作
├── analytics.py          # 数据库查询与绘图
└── utils.py              # 杂项工具
activity_analysis.ipynb   # 数据分析笔记本
error.log                 # 错误日志·自动生成
kf.db                     # 默认数据库·自动生成
hp.db                     # 主页信息数据库·自动生成
```


## 更新日志
* 2026.09.01 v2.2.0 update:   任意UID注册时间建模估算的实现
* 2026.08.23 v2.1.0 update:   发帖/编辑/买贴/转账功能的实现
    * 2026.08.24 v2.1.1 update: gbk_len函数修复；upload_image函数实现
    * 2026.08.26 v2.1.2 update: 转账功能CLI调用支持多用户名；转账成功判断逻辑修复
* 2026.08.14 v2.0.0 update:   完全重构
* 2025.06.07 v1.1.0 update:   主数据结构优化
* 2025.05.11 v1.0.0 original: 初始版本
