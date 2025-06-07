2025.06.07 update:  
※ 本仓库已于今日完全重置提交历史，你可能需要重新clone仓库以避免历史冲突  
※ 部分修改信息获取部分代码，完全重构数据分析部分代码（为了更好的可复用性和可读性）  
1, 主数据结构更新，新增“信息获取时间”、“用户所选ID色彩”、“帖子楼层号”和“帖子pid”的获取  
2, 原有结构对帖子正文描述不准确，现将帖子正文拆分成url_list、image_list、fieldset_list和reply_text四部分  
3, 为避免今后主数据结构再次更新时还需要重新获取一遍历史主题数据，现在数据获取程序能同时备份html文档源代码了  
4, 完全重构数据分析部分代码，现在仅在文件开头修改相关参数就能自动完成新统计周期数据分析

2025.05.11 update:  
1, 主数据结构更新，新增了对“帖子被推次数”与“用户主页链接”的获取  
2, 移除了所有topic_datas中经过加密的pickle序列化数据文件（加密朱庇特分析记录仍保留），请kf私信获取  
```
topic_info {
    topic_url:      str,            #主题链接
    board_belong:   str,            #所属板块
    topic_title:    str,            #主题标题
    view_count:     int,            #点击量
    reply_count:    int,            #回复量
    tui_count:      int,            #被推数
    topic_time:     int,            #开帖时间timestamp(unix)
    record_time:    int,            #信息获取时间timestamp(unix)
    reply_list: [
        {
            username:           str,            #回帖人用户名
            userhomepage:       str,            #用户主页链接
            replyboxcolor:      str,            #用户所选ID色彩
            floor:              int,            #帖子楼层号
            pid:                str,            #该帖唯一编号（同时也是url参数之一）
            url_list:           list,           #该帖所有[url]标签对字符串
            image_list:         list,           #该帖所有图片url
            fieldset_list:      list,           #该帖所有[fieldset]标签对字符串（引用框/代码框/关键词/等）
            reply_time:         int,            #回帖时间timestamp(unix)
            reply_text:         str,            #正文内容（除去所有空格类字符与换行符）
            reply_text_length:  int,            #正文计数 （常见欧洲语言字母一单位，中日韩字符两单位）
            topic_belong:       str,            #该帖所属主题url
        }
        #以列表形式存储了代表着所有回复贴的字典
    ]
}
```

使用说明如下：  
※ decrypto.py接受命令行参数列表，如果你的.py是可接收拖拽文件的，直接拖上去就好了。  
【想查看更详细的统计数据】使用贴末所附密钥，利用decrypto解密对应月份的.ipynb.enc文件。  
【想要查看所有主题帖完整链接】使用贴末所附密钥，利用decrypto解密url_list.enc文件。  
【想要使用序列化的帖子数据进行分析而不想等待】请在kf论坛联系我，视情况我会给您数据。  
【想要自行获取数据】：  
　　　　运行kfanalysis.py即可，已测试近期6920帖无bug，应该已应对绝大部分特殊情况。  
　　　　需要注意主要有四个点：  
　　　　　　　　1，不要将四个时间间隔设置的太低，以免服务器感到压力；  
　　　　　　　　2，数据获取程序main函数入口处可以指定数据获取的工作模式，详见注释；  
　　　　　　　　3，KFanalysis.timestamplimit指定了只获取最后回复时间在该日期之后的主题帖（的所有回复贴）；  
　　　　　　　　4，请填写你自己的cookie和user-agent，cookie与user-agent有对应关系。
