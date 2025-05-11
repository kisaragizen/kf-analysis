2025.05.11 update:  
※ 请注意论坛cookie与user-agent有对应关系！  
1, 主数据结构更新（见下方code块），新增了对“帖子被推次数”与“用户主页链接”的获取  
2, 移除了所有topic_datas中经过加密的pickle序列化数据文件（加密朱庇特分析记录仍保留），请kf私信获取
```
topic_info {
    topic_url:      str,            #主题帖链接
    board_belong:   str,            #所属板块
    topic_title:    str,            #主题帖标题
    view_count:     int,            #点击量
    reply_count:    int,            #回复量
    tui_count:      int,            #被推数
    topic_time:     int,            #开帖时间timestamp
    topic_author:   str,            #楼主用户名
    reply_list: [
        {
            username:           str,            #回帖人用户名
            userhomepage:       str,            #回帖人主页链接
            reply_time:         int,            #回帖时间timestamp
            reply_text:         str,            #正文内容
            reply_text_length:  int,            #正文计数 （常见欧洲语言字母一单位，中日韩字符两单位）
            img_list: [url0, url1, url2, ...]   #图片url列表（表情也在其中，可用于统计全站/个人表情使用情况）
            quote_list: [un0, un1, un2, ...]    #被引用用户名列表
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
　　　　运行kfanalysis.py即可，已测试近期5222帖无bug，应该已应对绝大部分特殊情况。  
　　　　需要注意主要有五个点：  
　　　　　　　　0，在kfanalysis.py同目录下新建topic_datas文件夹（重要！）；  
　　　　　　　　1，不要将四个时间间隔设置的太低，以免服务器感到压力；  
　　　　　　　　2，默认设置是使用解密后的url_list情况的，如果不打算依靠url_list（能够获取更新的主题帖列表），请注意程序入口处的注释，根据注释提示调节注释符号位置以激活对应功能；  
　　　　　　　　3，KFanalysis.timestamplimit指定了只获取最后回复时间在该日期之后的主题帖（的所有回复贴）；  
　　　　　　　　4，请填写你自己的cookie和user-agent，cookie与user-agent有对应关系。
