# kf-analysis

绯月论坛活跃度数据获取与分析项目 v2.0.0，完成了架构级重构与全面优化。  
数据获取支持 CLI 与 Python API 两种调用方式，数据持久化采用 SQLite，数据分析由 activity_analysis.ipynb 完成。  
移除原有硬编码逻辑，支持板块级与主题级增量抓取，并大幅优化页面解析逻辑与数据查询性能。  
经 201,248 条回复数据实测，数据抓取与入库结果符合预期。  

* 本项目运行在 bbs.kfpromax.com 域名下。  
* 本项目的文件内注释比 README.md 更详细。


## 配置填写
编辑 `kf_analysis/configure.json`，填写 `User-Agent`、`Cookie` 与 `Proxy` 信息。  
 `User-Agent` 与 `Cookie` 必须保持匹配，否则可能导致请求失败。`Proxy` 留空则使用直连。  
**除非你知道自己在做什么，否则不要改动四个 `timegap` 属性的默认值。**  
`boardlist` 用于指定 `fetch all` 命令需要获取的板块。


## CLI 调用
以下命令均省略前缀 `python -m kf_analysis`。  

CLI 命令主要分为两类：  
* `fetch`：获取并解析数据，并将结果写入默认或指定的数据库。  
* `get`：获取并解析数据，但不写入数据库，而是将结果输出到屏幕或写入文件。

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

**查询数据库当前状态**
```text
state [--db <路径>]    # 返回数据库当前状态以及错误日志的最新十行
```

**调用示例**
```
python -m kf_analysis fetch all
python -m kf_analysis fetch board 5
python -m kf_analysis fetch topic "https://bbs.kfpromax.com/read.php?tid=12345&sf=abc"
python -m kf_analysis fetch topic --file links.txt
python -m kf_analysis get json  "https://bbs.kfpromax.com/read.php?tid=12345&sf=abc"
python -m kf_analysis get usernames "https://bbs.kfpromax.com/read.php?tid=12345&sf=abc"
python -m kf_analysis get homepage "https://bbs.kfpromax.com/profile.php?action=show&uid=123&sf=abc"
python -m kf_analysis state
```


## 包内函数调用
包内调用分为两个层级：**`analyser` 纯解析函数**与 **`KFanalysis` 封装类**。

**纯解析函数（`analyser`）**  
`analyser` 提供与网络请求、数据库无关的纯解析函数。  
调用方负责准备页面原始数据，并根据需要自行处理解析结果。
```python
from bs4 import BeautifulSoup
from kf_analysis import analyser

soup = BeautifulSoup(html_text, "lxml")                     # html_text 为页面原始字节
status = analyser.check_page_status(soup)                   # 判断主题状态：normal / closed / deleted / incorrect
info = analyser.parse_topic_info(soup, tid, sf)             # 根据第一页的 soup 解析主题头信息并返回 dict
replies = analyser.parse_replies([html_text], tid, sf)       # 传入 html_text 列表，解析所有楼层信息并返回 dict
```
以上仅为简易调用示例，完整说明请参阅 `analyser.py` 中的函数注释。  
`analyser` 包含的其他函数：  
* `buy_topic(client, tid, sf, mode)` → 主题购买函数；默认仅返回价格，`mode="buy"` 时执行购买。  
* `parse_board_page(soup)` → 解析板块页，返回该页所有主题的 URL 列表。  
* `parse_profile_page(soup)` → 解析用户主页信息，返回 dict。

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
info = kf.get_homepage(uid, sf)                      # ↔ get homepage
stats = kf.storage.stats()                           # ↔ state
```
返回值约定（完整说明请参阅 `coordinator.py` 中的函数注释）：  
`fetch_onetopic()`：  
* `None`：无增量。  
* `False`：访问失败。  
* `"closed"`：主题已关闭。  
* `"deleted"`：主题已删除。  
* `dict`：获取成功，返回 `topic_info`；增量时会附带 `incremental` 标记。  
主题被关闭或删除时，若数据库中尚无该主题，则会插入对应的占位条目。  
帖子不存在或安全码错误时，记录至 `error.log`，不写入数据库。

**其他重要函数**  
```python
from kf_analysis import analytics

replies, topics = analytics.query_data(start_time, end_time, username, board_name, db_path, reverse)
# 每个参数都是可缺省的，全部缺省则读入整个数据库，否则按照参数指定的范围读取数据
# 返回值有两个，分别是散装回复列表与按主题聚合的回复列表
```


## 数据库结构
sqlite3，WAL 模式，两张表（topic 表与 reply 表）。  
本项目中，主题第零楼也视作回复，楼层号为0。
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
※ image_list / hidden_content / keyword_list 以 JSON 字符串存库，使用 query_data 函数读取时解析回 list。


## 数据分析
数据分析部分依赖本项目的 `analytics` 模块，由 `activity_analysis.ipynb` 完成。

* **Cell 1**：说明 `query_data` 函数及其参数。
* **Cell 2**：调用 `query_data`，从数据库中读取符合指定条件的全部主题及回复数据。
* **Cell 3**：总体活跃度统计与可视化，包括：
     * 总活跃主题数及日均值；
     * 总新增回复数及日均值；
     * 总参与人数及日均值；
     * 每日回复量日历热力图；
     * 每日发言用户数折线图；
     * 各板块活跃主题数、新增回复数柱状图。
* **Cell 4**：用户活跃度排行，包括回复数量、回复字节数及活跃天数比例。
* **Cell 5**：主题热度排行，包括新增回复数量、讨论持续天数；自动识别并标记 HB 相关主题。
* **Cell 6**：资源主题数量排行（总体 / 自购）、求助区实质优秀主题数量排行，以及求助区情况概述。

绘图函数：
```python
from kf_analysis import analytics

analytics.output_plot_bar(x, y, title, save, annotate, color, figsize, rotation)                          # 柱状图
analytics.output_plot_line(x, y, title, save, annotate, color, figsize, rotation)                         # 折线图
analytics.calendar_heatmap(day_counts, start, end, title, save, cmap, count_label, figsize, cell_height)  # 热力图
```


## 文件结构
```
kf_analysis/
├── __main__.py           # CLI 入口
├── configure.json        # 配置文件
├── coordinator.py        # 行为编排
├── service.py            # 网络请求与数据库操作
├── analyser.py           # 页面解析
├── analytics.py          # query_data 函数与绘图函数
└── utils.py              # 杂项工具
activity_analysis.ipynb   # 数据分析笔记本
error.log                 # 错误日志（自动生成）
json_result.txt           # get json 命令输出（自动生成）
kf.db                     # 默认数据库（自动生成）
```


### 更新展望
※ 借助 get_homepage 实现自动化使用插值法估算月度新增账号


## 更新日志
2026.08.14 update:   架构重构（v2.0.0）  
2025.06.07 update:   优化主数据结构（v1.1.0）  
2025.05.11 original: 初始版本（v1.0.0）