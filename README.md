2025.05.11 update:  
※ 请注意论坛cookie与user-agent有对应关系！
1, 主数据结构更新（见下方code块），新增了对“帖子被推次数”与“用户主页链接”的获取  
2, 移除了所有topic_datas中经过加密的pickle序列化数据文件（经过假名的朱庇特记事本分析记录仍保留），请在releases处获取
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
