# kf-analysis

绯月论坛活跃度数据获取与分析项目。  
v2.0.0 架构重构完成；v2.1.0 支持了部分论坛动作（发帖/编辑/私信/买贴/转账）；  
v2.2.0 完成了对任意 uid 注册时间的建模估算；v2.3.0 新增了持续监控功能。  
绝大部分功能同时支持 CLI 与包内函数两种调用形式（小部分风险论坛动作只支持包内函数调用）。  
支持板块级与主题级增量抓取；实现“数据获取→数据分析→发帖”全流程自动化接口。  
经 406,158 条回复数据实测，数据抓取与入库结果符合预期（2026-09-18 时数据）。

* 本项目运行在 bbs.kfpromax.com 域名下。  
* 本项目的文件内注释比 README.md 更详细。


## 配置填写
编辑 `kf_analysis/configure.json`，填写 `User-Agent`、`Cookie` 与 `Proxy` 信息。  
 `User-Agent` 与 `Cookie` 必须保持匹配，否则可能导致请求失败。`Proxy` 留空则使用直连。  
**除非你知道自己在做什么，否则不要改动四个 `timegap` 属性的默认值。**  
`boardlist` 用于指定 `fetch all` 命令需要获取的板块。


## CLI 调用
以下命令均已省略前缀 `python -m kf_analysis`。  
（注意实际使用时不可省略该前缀）

CLI 命令主要分为四类：  
* `get`：获取并解析数据，将结果输出到屏幕或写入文本文件。  
* `fetch`：获取并解析数据，将结果写入默认的或指定的数据库。  
* `monitor`：对指定对象进行持续监控，按固定周期循环增量抓取。  
* `buy`、`transfer`：主题查价/购买；贡献转账。  
出于风险性与实用性考量，并未支持所有论坛动作的 CLI 调用，  
更多功能详见本文**包内函数调用**章节。

**fetch 类命令**
```text
fetch all [--force] [--db]                       # 获取所有板块的数据
fetch board <fid> [--force] [--db]               # 获取指定板块的数据
fetch topic <link>... [--force] [--file] [--db]  # 获取指定主题的数据
```

* `--force`：强制全量更新；不指定该参数时仅为增量更新。  
* `--db`：指定数据将写入哪个数据库，不指定该参数时使用默认数据库。  
* `fetch topic` 支持两种方式传递一个或多个链接：  
    * 以命令行参数指定时，多个链接间需以空格分隔并各自使用引号包裹。  
    * 以文件参数指定时，要注意每行一个链接。  

**get 类命令**
```text
get json <link>                 # 获取指定主题的数据
get usernames <link> [--dedup]  # 输出参与指定主题的用户名列表
get homepage <link>             # 输出指定用户的主页信息
```

* `get json` 命令会将获取到的数据写入同目录的文本文件。  
* `--dedup`：指定是否对获取到的用户名列表进行去重（保留首次出现的顺序）。

**monitor 命令**
```text
monitor topic <link>... [--file] [--store] [--force] [--criteria] [--gap] [--db]
```

* `--gap`：决定监控周期（秒），缺省值为 300
* `--store`：指定是否要在监控时对本地数据库进行更新
* `--force`：用于指定基线轮次的行为
    * True 时为全量更新+历史信息也将参与命中判定
    * False 时为增量更新+仅基线建立后的新信息参与命中判定
* `--criteria`：判定依据字符串，格式与意义取决于 event 的实现
* 默认监控行为「当新增回复由特定用户发出时，进行气泡提示」
* 默认监控行为下该参数用于传递以半角逗号分隔的用户名列表

**buy / transfer 命令**
```text
buy <link> [--buy]                          # 主题购买功能
transfer <username_list> <amount> [--memo]  # 贡献转账功能
```

* `--buy`：仅当指定该参数时执行购买，否则执行价格查询。  
* `<username_list>`：以半角逗号分隔用户名的单字符串。

**查询数据库当前状态**
```text
state [--db]  # 返回数据库当前状态
```

**部分调用示例**
```
python -m kf_analysis fetch topic "https://bbs.kfpromax.com/read.php?tid=00000&sf=fff"
python -m kf_analysis get json "https://bbs.kfpromax.com/read.php?tid=00000&sf=fff"
python -m kf_analysis transfer "user1, user2, user3" 0.5 --memo "thanks~"
python -m kf_analysis monitor topic --file links.txt --criteria "user1, user2, user3"
```


## 包内函数调用

**纯解析函数（`analyser`）**  
`analyser` 提供与网络请求、数据库无关的纯解析函数。  
```python
from kf_analysis import analyser

analyser.check_page_status(soup)                                      # 判断主题的可访问性
analyser.parse_topic_info(soup, topic_id, topic_sf)                   # 解析某主题的头信息并返回 dict
analyser.parse_replies(page_list, topic_id, topic_sf, username_dict)  # 解析所有页面的回复并返回 list
analyser.parse_board_page(soup)                                       # 解析板块页主题链接并返回 list
analyser.parse_profile_page(soup)                                     # 解析用户主页信息，返回 dict
```

* 详细说明见 `analyser.py` 对应位置的注释。

**KFanalysis 封装类（`coordinator`）**  
`KFanalysis` 对数据获取、解析及数据库操作进行统一封装。  
```python
from kf_analysis import utils
from kf_analysis.coordinator import KFanalysis

cfg = utils.load_config()
kf = KFanalysis(cfg, db_path="kf.db")
kf.fetch_all(force=False)                            # ↔ fetch all
kf.fetch_board(fid, force=False)                     # ↔ fetch board
kf.fetch_onetopic(tid, sf, force=False)              # ↔ fetch topic
data = kf.get_topic_json(tid, sf)                    # ↔ get json
names = kf.get_topic_usernames(tid, sf, dedup=False) # ↔ get usernames
info = kf.get_homepage(uid, sf, db=False)            # ↔ get homepage
stats = kf.storage.stats()                           # ↔ state
```

* `fetch_all` 是多次 `fetch_board` 的调用；
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
发主题/发回复/发私信/帖子编辑/获取原始内容/买贴/转账/主页链接探测。
```python
from kf_analysis import actions

acts = actions.Actions(config)
acts.post_reply(tid, sf, content, keywords)                        # 回复发帖
acts.post_topic(fid, content, title, keywords)                     # 主题发帖
acts.edit_post(tid, sf, pid, article, content, title, keywords)    # 帖子编辑
acts.get_post_content(tid, sf, pid, article)                       # 原始内容获取
actions.buy_topic(client, topic_id, topic_sf, mode)                # 主题购买
actions.transfer_money(client, username, amount, memo)             # 贡献转账
actions.send_message(client, username, title, content, save)       # 私信发送
actions.search_user_hp(client, username)                           # 主页链接探测
```

* 详细说明见 `actions.py` 对应位置的注释。
* 目前 `post_topic` 函数只支持**没有强制二级分类的普通板块**。
* **以下功能未列出**：`upload_image`, `search_user_sf`, `search_topic_sf`。

**持续监控（`monitor`）**  
```python
from kf_analysis import monitor

monitor.monitor_topic(config, links, gap, store, force, db_path, event, action, criteria) # 持续监控主题
monitor.monitor_event(data, criteria)                                                     # 命中判定函数，可自定义行为
monitor.monitor_action(matches)                                                           # 命中执行函数，可自定义行为
```

* 详细说明见 `monitor.py` 对应位置的注释。

**其他重要函数**  
```python
from kf_analysis import analytics

analytics.query_data(start_time, end_time, username, board_name, db_path, reverse)
# 每个参数都是可缺省的，全部缺省则读入整个数据库，否则按照参数指定的范围读取数据
# 返回值有两个，分别是散装回复列表与按主题聚合的回复列表
analytics.query_generation(start_time, end_time, gap_days, db_path)
# 主题热度榜统计专用查询函数，按“讨论代际”弹性切割，而非按指定时间刚性切割
```


## 数据库结构
kf.db 分为 topic 与 reply 两张表。
```
topic 表：
topic_id    INTEGER PRIMARY KEY,   # tid
topic_sf    TEXT,                  # sf
board_id    INTEGER,               # 所属板块fid
board_name  TEXT,                  # 所属板块名称
title       TEXT,                  # 标题
reply_count INTEGER,               # 回复量
topic_time  INTEGER,               # 开帖时间
record_time INTEGER,               # 获取时间
status      TEXT                   # 可访问性
```
```
reply 表：
topic_id        INTEGER NOT NULL,  # 所属主题tid
topic_sf        TEXT,              # 所属主题sf
reply_id        TEXT,              # pid
floor           INTEGER,           # 楼层号
username        TEXT,              # 用户名
homepage_id     INTEGER,           # 用户主页uid
homepage_sf     TEXT,              # 用户主页sf
reply_box_color TEXT,              # 回复框颜色
reply_time      INTEGER,           # 回帖时间
record_time     INTEGER,           # 获取时间
reply_text      TEXT,              # 紧凑化正文
status          TEXT,              # 可访问性
image_list      TEXT,              # 图像链接列表
complete        INTEGER,           # 权限框是否全部解锁
hidden_content  TEXT,              # 已解锁的权限框内容
keyword_list    TEXT,              # 用户名类关键词
PRIMARY KEY (topic_id, reply_id),
FOREIGN KEY (topic_id) REFERENCES topic(topic_id)
```

* 表中所有时间均以 UNIX 时间戳形式存储。
* `status` / topic：active 正常 / closed 被关 / deleted 被删
* `status` / reply：active 正常 / hidden 隐藏 / banned 禁言或删号
* `complete`：0 不存在权限框 / 1 有且全部可读 / 2 存在部分或全部不可读
* `image_list`, `hidden_content`, `keyword_list` 以 JSON 形式存库。
* 若为普通楼层，`reply_id` 格式为 PID<pid\>，若为主题楼，则格式为 TPC<tid\>。


hp.db 中只存在 homepage 表，  
hp.db 是 `get_homepage` 函数在 db=True 时的存储对象。
```
homepage 表：
uid      INTEGER PRIMARY KEY,   #用户主页uid
sf       TEXT,                  #用户主页sf
username TEXT,                  #用户名称
regdate  TEXT,                  #注册日期
ok       INTEGER                #是否获取成功
```


## 数据分析
Jupyter-Lab: activity_analysis.ipynb

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
* **Cell A**：主题热度排行（回复数量顺序、讨论天数顺序）。
* **Cell B**：资源主题贡献排行，分为整体与自购两部分。

```
关于任意uid注册时间的建模估算：
假设我们有一张24小时热度分布权重表，表中元素相加为1
当已知点数量为1，代表将一天分成了2份，接下来我们需要在权重表中找到从左向右加和到恰好等于50%的点
当已知点数量为n，代表将一天分成了n+1份，接下来我们需要在权重表中分别找到从左向右加和恰好等于k/(n+1)处的点
（实际上是先定位到小时然后在小时内线性插值，关于此处精度的改善可以从权重表入手，在上一个cell提高权重表时间粒度，但这也意味着更长的计算时间）
为避免重复计算，先找出单日已知点数量的最大值N，然后前置地分别算出当已知点数量为1到N时，每个点的对应时刻，后面只需要查表赋值就好
为了得到T时刻的uid最大值，我们需要找到已知点中早于T与晚于T的最近点，然后根据Ut=Ua+(Ub-Ua)×Wa得到结果，Wa指时刻A到时刻T占时刻A到时刻B的权重比例
```


## 文件结构
```
kf_analysis/
├── __main__.py           # CLI 入口
├── configure.json        # 配置文件
├── coordinator.py        # 行为编排
├── monitor.py            # 持续监控
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
* 2026.09.17 v2.3.3
    * 支持通过 force 参数控制基线轮次是否参与命中判定
    * 修复主题头信息无法被 event 函数利用的问题
    * 优化默认命中行为
    * 整理命令行参数解析相关代码
* 2026.09.15 v2.3.2
    * 支持主题热度榜跨月统计
    * 优化错误日志输出格式
    * black+ruff 规范化
* 2026.09.09 v2.3.1
    * 修复被删帖判定条件错误
* 2026.09.08 v2.3.0
    * 实现对主题进行持续监控
* 2026.09.07 v2.2.1
    * 论坛动作支持：私信
    * 支持已知用户名时直接获取用户主页链接
    * 支持未知用户名时暴力搜索用户主页安全码
* 2026.09.01 v2.2.0
    * 实现建模估算任意 UID 注册时间
* 2026.08.26 v2.1.2
    * 修复转账完成状态解析对象错误
    * 支持单次命令行调用向多个用户转账
* 2026.08.24 v2.1.1
    * 修复 gbk_len 函数调用报错
    * 支持向 inari 图床上传图片
* 2026.08.23 v2.1.0
    * 论坛动作支持：发帖＆编辑
    * 论坛动作支持：买贴＆转账
* 2026.08.14 v2.0.0
    * 重构完成
* 2025.06.07 v1.1.0
    * 解析优化（已弃用）
* 2025.05.11 v1.0.0
    * 初始版本（已弃用）


## 更新展望
* 板块级与主页级监控功能的实现
* fetch 与 get 支持对用户主题列表的抓取
