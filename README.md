2025.06.07 update:  
※ 本仓库已于今日完全重置提交历史，你可能需要重新clone仓库以避免历史冲突  
※ 部分修改信息获取模块，完全重构数据分析模块（为了更好的可复用性和可读性）  
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
※ decrypto.py接受命令行参数列表，如果你的.py是可接收拖拽文件的，也可以拖动解密。  
【想查看更详细的统计数据】使用贴末所附密钥，利用decrypto解密对应月份的.ipynb.enc文件。  
【想要查看所有主题帖完整链接】使用贴末所附密钥，利用decrypto解密url_list.enc文件。  
【想要自行获取数据】：  
　　　　运行kfanalysis.py即可，已测试近期6920帖无bug。  
　　　　运行kfanalysis.py注意事项：  
　　　　　　　　1，请在headers处设置自己的ua和cookie；  
　　　　　　　　2，请在timestamplimit处指定一个unix时间戳，程序会获取发表时间在其后的所有帖子；  
　　　　　　　　3，timegap开头四个变量用于控制翻页时间，请不要设定的太低以免服务器有压力；  
　　　　　　　　4，程序入口处变量mode可以指定工作模式（主题帖链接来源），默认为2（由程序重新获取），在使用其他两个模式前请确定对应文件存在于工作目录（如想使用模式0需要先解码url_list.enc）；  
　　　　运行data_analysis_code.ipynb注意事项：  
　　　　　　　　1，数据分析模块读取所有kfanalysis.py所获取的pickle序列化文件；  
　　　　　　　　2，基本上改改第一个语句块中的起止时间就能进行常规活跃数据分析；  
　　　　　　　　3，助人王分析需要人工录入部分数据，默认被禁用，可修改语句块最上方标志位布尔值启用；  
　　　　　　　　4，总和统计/个人统计功能均默认被禁用，如有需要可修改语句块最上方标志位布尔值启用；  
　　　　　　　　5，你几乎可以使用valid_reply_list_unstructured列表统计出一切自己想要的结果，它存储着所有合规的帖子对象，详见对应注释。  