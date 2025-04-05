import requests, re, time, pickle
from bs4 import BeautifulSoup, NavigableString, Tag
from datetime import datetime


class KFanalysis:
    def __init__(self):
        # 第三个元素是置顶帖数量，需要切片跳过
        self.boardlist = [
            ["自由讨论区", "https://bbs.kfpromax.com/thread.php?fid=5&orderway=lastpost&page=", 0],
            ["个人日记区", "https://bbs.kfpromax.com/thread.php?fid=56&orderway=lastpost&page=", 1],
            ["网站管理投诉建议", "https://bbs.kfpromax.com/thread.php?fid=4&orderway=lastpost&page=", 2],
            ["原创绘画美图", "https://bbs.kfpromax.com/thread.php?fid=94&orderway=lastpost&page=", 0],
            ["ACG实物交流", "https://bbs.kfpromax.com/thread.php?fid=87&orderway=lastpost&page=", 0],
            ["电子产品交流", "https://bbs.kfpromax.com/thread.php?fid=86&orderway=lastpost&page=", 6],
            ["ACG文学作品", "https://bbs.kfpromax.com/thread.php?fid=115&orderway=lastpost&page=", 0],
            ["图片出处来源互助", "https://bbs.kfpromax.com/thread.php?fid=96&orderway=lastpost&page=", 0],
            ["寻求资源共享", "https://bbs.kfpromax.com/thread.php?fid=36&orderway=lastpost&page=", 0],
            ["动漫综合讨论区", "https://bbs.kfpromax.com/thread.php?fid=84&orderway=lastpost&page=", 0],
            ["动画资源下载", "https://bbs.kfpromax.com/thread.php?fid=92&orderway=lastpost&page=", 0],
            ["漫画小说下载", "https://bbs.kfpromax.com/thread.php?fid=127&orderway=lastpost&page=", 0],
            ["ACG音乐下载", "https://bbs.kfpromax.com/thread.php?fid=68&orderway=lastpost&page=", 0],
            ["Live资源下载", "https://bbs.kfpromax.com/thread.php?fid=163&orderway=lastpost&page=", 0],
            ["GalgameBT下载", "https://bbs.kfpromax.com/thread.php?fid=16&orderway=lastpost&page=", 2],
            ["Galgame网络硬盘下载", "https://bbs.kfpromax.com/thread.php?fid=41&orderway=lastpost&page=", 1],
            ["CG画集图片下载", "https://bbs.kfpromax.com/thread.php?fid=67&orderway=lastpost&page=", 0],
            ["GAL本子下载", "https://bbs.kfpromax.com/thread.php?fid=57&orderway=lastpost&page=", 0],
            ["无限制资源区", "https://bbs.kfpromax.com/thread.php?fid=9&orderway=lastpost&page=", 0],
            ["Galgame推荐", "https://bbs.kfpromax.com/thread.php?fid=102&orderway=lastpost&page=", 2],
            ["Galgame新作信息", "https://bbs.kfpromax.com/thread.php?fid=106&orderway=lastpost&page=", 1],
            ["Galgame综合讨论", "https://bbs.kfpromax.com/thread.php?fid=52&orderway=lastpost&page=", 1],
            ["游戏运行安装问题", "https://bbs.kfpromax.com/thread.php?fid=24&orderway=lastpost&page=", 7],
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Host": "bbs.kfpromax.com",
            "Cookie": "",
        }
        if not self.headers["Cookie"]: raise Exception("empty cookie!")
        self.proxies = {
            "http": "http://127.0.0.1:10809",
            "https": "http://127.0.0.1:10809",
        }

        self.timestamplimit = 1740412800
        # 只提取最后回复时间戳在这之后的新帖，推荐使用自由讨论曲第十页的最后一个完整天的零点整
        # 原始值1740412800代表2025-02-25，距当前最后一个完整天（2025-04-03）的最后一瞬间共38天
        self.timegap_board_out = 10
        self.timegap_board_in = 5
        self.timegap_topic_out = 10
        self.timegap_topic_in = 5
        # 分别为板块间切换间隔，板块内翻页间隔，主题帖见切换间隔，主题帖内翻页间隔
        # 虽然设置的有点长，但是也无所谓，毕竟所有主题帖和回复贴有timestamp，排除所有收集信息流程开始之后结束之前的帖子就好
        self.alltopic_url = {}

    def get_oneboard_url(self, url, disp=False):
    # 获取一个板块中所有帖子的链接（板块以最后回复时间倒序排序），组成列表并返回
    # 是我的论坛权限不够吗？我只能查看板块前十页的帖子，不过需要注意的是，不同板块每页的主题帖数量不同
    # 主题帖数量越多的板块越有低更新频率的倾向，需要写一个时间范围截断功能，使不在这个时间范围中的主题帖不会被提取info
    # 比如检查每一个主题帖的最终回复时间（帖子是最终回复时间倒序的），遇到第一个超脱时间范围的主题帖，则跳过对之后主题帖的处理
        def get_onepage_url(url):
            response = requests.get(url, headers=self.headers, proxies=self.proxies)
            soup = BeautifulSoup(response.text, features="lxml")
            resultinn = soup.find_all("div", class_="threadtit1")
            resultinn = [x.find_all("a")[-1].attrs["href"] for x in resultinn]
            return resultinn

        result = []
        for page in list(range(1, 11)):
            url2 = url + str(page)
            if disp: print(url2)
            result += get_onepage_url(url2)
            time.sleep(self.timegap_board_in)
        result = get_onepage_url(url+"1") + result
        result = list(dict.fromkeys(result))
        # 为避免timegap期间有帖子浮动到首页导致提取不完全，使用一个很简单解决办法
        # 因为一个板块不可能在整个get_oneboard_url期间浮动超过60帖，那就只需要末尾再提取一次首页然后去重就好了
        # 不过需要注意的是这个再次提取的首页需要插到整体最前，并使用能够保留顺序的去重代替set去重
        if disp: print(f"↑ {len(result)}topics extracted.\n")
        return result

    def get_alltopic_url(self):
        result = {}
        for x in self.boardlist:
            result[x[0]] = self.get_oneboard_url(x[1], disp=True)
            time.sleep(self.timegap_board_out)
        self.alltopic_url = result
        return result

    def text_count(self, text):
        # 中日韩字符范围（两单位）/常见西语字母范围（一单位）
        cjk_pattern = r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]'
        european_letters = (
            r'a-zA-Z'   # 基础拉丁字母
            r'À-ÿ'      # 拉丁字母扩展
            r'äöüßÄÖÜ'  # 德语特殊字母
            r'а-яА-ЯёЁ' # 西里尔字母
        )
        european_word_pattern = rf'[{european_letters}]+'
        cjk_chars = re.findall(cjk_pattern, text)
        european_words = re.findall(european_word_pattern, text)
        total_units = 2 * len(cjk_chars) + len(european_words)
        return total_units

    def get_onetopic_info(self, url, disp=False, index=0):
        def format_time(timestr):
            return int(datetime.timestamp(datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")))

        def get_onepage_replies(soup):
            divlist = soup.find_all("div", class_="readtext")
            replylist = []
            for x in divlist:
                xdict = {}
                xdict["username"] = x.find_all("div", "readidmsbottom")[0].a.text
                if xdict["username"] == "该用户禁言中": continue
                # 遇到被禁言的用户时会出bug，反正没正文也没用户名，直接给它跳咯
                xdict["reply_time"] = format_time(x.select_one("span[style='color:#999999;']").text.strip() + ":00")
                replay_box = x.select_one("td:nth-child(2) > div:nth-child(1)")
                # kf回帖的“引用回复、楼层回复、表情，文本”全部都在replay_box中

                replay_text = []
                img_list = []
                # 收集所有img是为了统计表情使用情况，本质上无法与非表情img标签区分，但表情包一定是多次使用
                fieldset_list = []
                # fieldset是引用回复/楼层回复/其他框框的直接节点，fieldset_list是为了收集所有回复类框框的被回复用户名

                # 下方的条件判断只保留了所有回复类fieldset，虽然没写，但其实优秀贴认证框框也同样有价值
                # ↑真的吗？感觉不咋有价值，很多实质上的优秀贴只在主题帖的标题表示了，而且表示方法还乱七八糟
                # 想精确判断主题帖的写很复杂的正则组了
                for x in replay_box.contents:
                    if isinstance(x, Tag):
                        if x.name == "img":
                            img_list.append(x.attrs["src"])

                        elif x.name == "fieldset" and x.legend.text == "Quote:":
                            # 关键词和两种回复都一样用fieldset，要加以区分
                            # 引用回复中，引用楼主第0楼与引用其他楼层形制略有区别，但前者还统计他干啥
                            un = x.text
                            if "Quote:引用第" in un:
                                un = re.findall("引用第\d+楼(.*)于\d{4}-\d{2}-\d{2}", un)
                                if un: un = un[0]
                                else: continue
                                # tid=715016&sf=39b第8756楼遇到的特殊情况
                            elif "Quote:回" in un:
                                if "楼(" in un:
                                    un = re.findall("回 \d+楼\((.*)\) 的帖子", un)[0]
                                else:
                                # tid=798326&sf=457的第3896楼遇到的特殊情况
                                    un = re.findall("回 \((.*)\) 的帖子", un)[0]
                            fieldset_list.append(un)

                        # 将a标签的text也视为回复贴正文的一部分
                        elif x.name == "a":
                            replay_text.append(x.text)

                    # 使用NavigableString类来判断是不是文本节点，前面的replay_box.contents限定了仅处理直接子节点
                    # 若是则保留，拼接得到回复文本,最后去除所有间隔符（使用translate）
                    elif isinstance(x, NavigableString):
                        replay_text.append(x)

                trans_table = str.maketrans('', '', '\xa0\r\t\n ')
                xdict["reply_text"] = "".join(replay_text).translate(trans_table)
                xdict["reply_text_length"] = self.text_count(xdict["reply_text"])
                xdict["img_list"] = img_list
                xdict["quote_list"] = fieldset_list
                replylist.append(xdict)
            return replylist

        topic_url = "https://bbs.kfpromax.com/" + url
        response = requests.get(topic_url, headers=self.headers, proxies=self.proxies)
        soup = BeautifulSoup(response.text, features="lxml")
        if soup.find_all("title")[0].text == "此帖被管理员关闭，暂时不能浏览 - 绯月ScarletMoon ":
            if disp: print(f"skip admin closes the topic: {topic_url}")
            return False

        topic_count_text = soup.select_one('tr:nth-child(2) > td:nth-child(1)').text.replace("\xa0", " ")
        numbers_split = re.findall("\d+", topic_count_text)
        if len(numbers_split) == 6:
            numbers_split = [0] + numbers_split
        # numbers_split元素数量为6（也就是少一个），认为这种状态下的点击量是不可见的，既然不可见那就视为0
        topic_info = {
            "topic_url": topic_url,
            "board_belong": re.findall("(.*) >>", topic_count_text)[0],
            "topic_title": soup.select_one("div.drow:nth-child(3) span").text,
            "view_count": int(numbers_split[0]),
            "reply_count": int(numbers_split[1]),
            "topic_time": format_time(
                f"{numbers_split[2]}-{numbers_split[3]}-{numbers_split[4]} {numbers_split[5]}:{numbers_split[6]}:00"),
        }
        replylist = get_onepage_replies(soup)
        topic_info["topic_author"] = replylist[0]["username"]
        current_page = topic_url

        def echo():
            print(f"{index:<5}{len(replylist):>5}/{topic_info['reply_count']:<5}   {topic_info['topic_title']}, {current_page}")

        if disp: echo()
        for page in range(2, (topic_info["reply_count"] // 20) + 2):
            """
            # 如果需要跳过部分帖子的某些楼层，在这里设置条件判断
            # 比如下面被跳进的帖子，一共8778个回帖，也太恐怖，直接跳进到不影响数据分析的页数
            if topic_url == "https://bbs.kfpromax.com/read.php?tid=715016&sf=39b":
                if page < 437:
                    continue
            """
            current_page = f"{topic_url}&page={page}"
            response = requests.get(current_page, headers=self.headers, proxies=self.proxies)
            soup = BeautifulSoup(response.text, features="lxml")
            replylist = replylist + get_onepage_replies(soup)

            if disp: echo()
            time.sleep(self.timegap_topic_in)
        topic_info["reply_list"] = replylist
        return topic_info

    def get_alltopic_info(self):
        if not self.alltopic_url:
            self.get_alltopic_url()
        result = []
        f = open("done_url_list", "rt")
        done_url_list = f.read().split("\n")
        f.close()
        with open("done_url_list", "at") as f:
            # 通过对done_url_list的读写，出了bug也能跳过重复
            # 为避免中途崩溃，选择将每个topic的信息都单独序列化为文件，存储于topic_datas
            for board_name in self.boardlist:
                board_urls = self.alltopic_url[board_name[0]][board_name[2]:]
                # [board_name[2]:]意在排除置顶帖
                board_urls_length = len(board_urls)
                i = 0
                for topic_url in board_urls:
                    if topic_url in done_url_list:
                        i += 1
                        print(f"skip {topic_url}")
                        continue
                    topic_data = self.get_onetopic_info(topic_url, disp=True, index=i)
                    if not topic_data: continue
                    # tid=1055251&sf=61a遇到的特殊情况，网站管理员关闭了该主题帖
                    if topic_data["reply_list"][-1]["reply_time"] < self.timestamplimit:
                        print(f"{i}/{board_urls_length} the rest part skipped.\n")
                        break
                    result.append(topic_data)
                    inn = open(rf"topic_datas\{topic_url.replace('?', '@')}", "wb")
                    pickle.dump(topic_data, inn)
                    inn.close()
                    f.write(topic_url + "\n")
                    f.flush()
                    i += 1
                    time.sleep(self.timegap_topic_out)
        self.all_topic_info = result
        return result


if __name__ == "__main__":
    kf = KFanalysis()
    # 持有alltopic_url时
    with open("alltopic_url_arhive", "rb") as f:
        alltopic_url = pickle.load(f)
        kf.alltopic_url = alltopic_url

    with open("alltopic_info_arhive", "wb") as f:
        kf.get_alltopic_info()
        pickle.dump(kf.all_topic_info, f)
"""
    # 未持有alltopic_url时
    def rewrite_timestampfile(obj):
        f = open("timestamp_archive", "wb")
        pickle.dump(obj, f)
        f.close()

    stime0 = int(time.time() // 1)
    rewrite_timestampfile([stime0])

    with open("alltopic_url_arhive", "wb") as f:
        kf.get_alltopic_url()
        pickle.dump(kf.alltopic_url, f)
    stime1 = int(time.time() // 1)
    rewrite_timestampfile([stime0, stime1])


    with open("alltopic_info_arhive", "wb") as f:
        kf.get_alltopic_info()
        pickle.dump(kf.all_topic_info, f)
    etime = int(time.time() // 1)
    rewrite_timestampfile([stime0, stime1, etime])
"""