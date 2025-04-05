**0.主要文件**
kfanalysis.py                      #获取帖子信息并序列化（python）
data_analysis_code.ipynb           #反序列化并进行数据分析（jupyter notebook, python）
data_analysis_record.ipynb.enc     #带有详细分析结果的data_analysis_code.ipynb（已加密）
decrypto.py                        #解密程序
done_url_list                      #kfanalysis.py必需文件，用于跳过已提取过信息的主题帖
topic_datas/*                      #各主题帖的结构化信息（pickle序列化文件，已加密）

**1.查看数据**
data_analysis_record.ipynb.enc 中存储了所有分析结果的更详细版本，topic datas 目录下所有 .enc 文件都存储着对应主题帖的全部结构化信息（pickle序列化文件）。
但为了确保站内信息不会外泄，若想查看/使用这些文件，请运行 decrypto.py 进行解密（解密完成后请删除原 .enc 文件，以免影响程序正常运行）。
解密所需密钥详见信息发布贴。

**2.使用说明**
进行任何其他操作前，请确保 kfanalysis.py 中 line-37 的 "Cookie" 已被正确填写，获取论坛中任何信息都受限于该 "Cookie" 所拥有的权限。
本项目代码在任何时候，以 topic 指代主题帖，以 reply 指代回复贴，所有时间标志以 timestamp(int, Asia/Shanghai) 或 "%Y%m%d"[2:] 形式存在。

直接运行 kfanalysis.py 时，由于项目已附带 alltopic_url 文件，会自动开始提取该文件所指示的三月份全主题帖信息。
想要重新开始，需要将 line-256 到 line-263 注释掉并取消后续语句的多行注释，或 from kfanalysis import KFanalysis 后创建新 KFanalysis 对象，调用其中 get_alltopic_info 方法。
此时会自动获取所有板块中以“最后回复时间倒序”排列的前 10 页主题帖链接（若权限不足/超过，可通过 line-69 更改这个范围）。
随后将对这些主题帖链接进行信息提取，并设定如果某主题帖过于冷门（即最后回复时间过于久远）则不进行信息提取，这个标准的设置在 line-45 处。
最后将提取到的所有信息进行 pickle 序列化，以供使用 data_analysis_code.ipynb(jupyter notebook) 进行数据分析。

为确保服务器不会有压力，请合理设置 line-48 到 line51 的四个冷却时间，分别为板块间切换间隔/板块内翻页间隔/主题帖间切换间隔/主题帖内翻页间隔。
由于信息提取流程是先“提取所有板块主题帖链接”再“根据这些链接进行信息提取”，无论后者有多慢都不会影响数据完整性，
即“本在后续页面的帖子经由其他用户回复浮动到了最前页”的情况无法对后者造成影响，而前者也已通过 line-76 到 line-78 所描述的逻辑规避了风险。

若要跳过某主题帖的某些页数时（如某主题帖有300页而其中前299页都是无用信息时），可参考 line-199 到 line-205 所述逻辑在同位置编写条件判断语句。
若要添加统计优秀信息/购买信息/神秘等级限制信息/锁定信息的功能，需要修改 fieldset 标签相关语句。
已实现跳过已提取过信息的主题帖功能，调试会很方便。

**3.数据结构**
于此贴出 kfanalysis.py 的核心数据结构（data_analysis_code.ipynb的数据结构繁多，详见内部注释）：
topic_info {
    topic_url:      str,            #主题帖链接
    board_belong:   str,            #所属板块
    topic_title:    str,            #主题帖标题
    view_count:     int,            #点击量
    reply_count:    int,            #回复量
    topic_time:     int,            #开帖时间timestamp
    topic_author:   str,            #楼主用户名
    reply_list: [
        {
            username:           str,            #回帖人用户名
            reply_time:         int,            #回帖时间timestamp
            reply_text:         str,            #正文内容
            reply_text_length:  int,            #正文计数 （常见欧洲语言字母一单位，中日韩字符两单位）
            img_list: [url0, url1, url2, ...]   #图片url列表（表情也在其中，可用于统计全站/个人表情使用情况）
            quote_list: [un0, un1, un2, ...]    #被引用用户名列表
        }
        #以列表形式存储了代表着所有回复贴的字典
    ]
}
