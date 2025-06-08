import requests, re, time, pickle, os
from bs4 import BeautifulSoup
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
            "Host": "bbs.kfpromax.com",
            "User-Agent": "",
            "Cookie": "",
        }
        if not self.headers["Cookie"]: raise Exception("empty cookie!")
        if not self.headers["User-Agent"]: raise Exception("empty User-Agent!")
        self.proxies = {
            "http": "http://127.0.0.1:10809",
            "https": "http://127.0.0.1:10809",
        }

        self.timestamplimit = 1746720000
        # 只提取最后回复时间戳在这之后的新主题帖，推荐使用自由讨论区第十页的最后一个完整天的零点整
        # 除特殊情况外，提取全部回复贴，即回复贴的提取不会收到该时间戳的限制
        self.timegap_board_out = 5
        self.timegap_board_in = 3
        self.timegap_topic_out = 5
        self.timegap_topic_in = 3
        # 分别为板块间切换间隔，板块内翻页间隔，主题帖见切换间隔，主题帖内翻页间隔
        # 虽然设置的有点长，但是也无所谓，毕竟所有主题帖和回复贴有timestamp，排除所有收集信息流程开始之后结束之前的帖子就好
        self.alltopic_url = {}

    def get_oneboard_url(self, url, disp=False):
    # 获取一个板块中所有帖子的链接（最后回复时间倒序排序），组成列表并返回
    # 不同板块每页的主题帖数量不同，主题帖数量越多的板块越有低更新频率的倾向
    # 需要写一个时间范围截断功能，使不在这个时间范围中的主题帖不会被提取info（已完成）
        def get_onepage_url(url):
            response = requests.get(url, headers=self.headers, proxies=self.proxies)
            soup = BeautifulSoup(response.text, features="lxml")
            resultinn = soup.find_all("div", class_="threadtit1")
            resultinn = [x.find_all("a")[-1].attrs["href"] for x in resultinn]
            resultinn = [re.sub("&fpage.*", "", x) for x in resultinn]
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
            r'0-9'
            r'a-zA-Z'   # 基础拉丁字母
            r'À-ÿ'      # 拉丁字母扩展
            r'äöüßÄÖÜ'  # 德语特殊字母
            r'а-яА-ЯёЁ' # 西里尔字母
        )
        european_word_pattern = rf'[{european_letters}]'
        cjk_chars = re.findall(cjk_pattern, text)
        european_words = re.findall(european_word_pattern, text)
        total_units = 2 * len(cjk_chars) + len(european_words)
        return total_units

    def get_onetopic_info(self, url, disp=False, index=0):
        def format_time(timestr):
            return int(datetime.timestamp(datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")))

        def get_onepage_replies(soup, topic_url):
            divlist = soup.find_all("div", class_="readtext")
            replylist = []
            for x in divlist:
                xdict = {}
                xdict["username"] = x.find_all("div", "readidmsbottom")[0].a.text
                if xdict["username"] == "该用户禁言中": continue
                # 遇到被禁言的用户时会出bug，反正没正文也没用户名，直接给它跳咯
                xdict["userhomepage"] = x.find("div", class_="readidmsbottom").a.attrs["href"]
                xdict["replyboxcolor"] = x.find_all("div", "readidmsbottom")[0].a.attrs["style"][6:]
                try:
                    xdict["floor"] = x.select_one("span[style='font-size:16px;font-weight:bold;']").text
                    # 普通用户样式
                except:
                    xdict["floor"] = x.select_one("span[style='font-size:16px;font-weight:bold;color:#ff6666;']").text
                    # 管理成员样式
                xdict["floor"] = 0 if "楼主" in xdict["floor"] else int(re.findall("\d+", xdict["floor"])[0])
                xdict["pid"] = x.attrs["id"]
                # 注意0楼的pid统一为pidtpc
                xdict["reply_time"] = format_time(x.select_one("span[style='color:#999999;']").text.strip() + ":00")
                reply_box = x.select_one("td:nth-child(2) > div:nth-child(1)")
                xdict["url_list"] = [str(q) for q in reply_box.find_all("a") if q.attrs["href"][:4]=="http"]
                xdict["image_list"] = [q.attrs["src"] for q in reply_box.find_all("img")]
                xdict["fieldset_list"] = reply_box.find_all("fieldset")
                fieldset_text_list = [q.get_text() for q in xdict["fieldset_list"]]
                all_text = reply_box.get_text()
                all_text = re.findall(r"\nTOP\n看TA\n回复\n菜单(.*)", all_text, flags=re.DOTALL)[0]
                for q in fieldset_text_list:
                    all_text = all_text.replace(q, "")
                trans_table = str.maketrans('', '', '\u3000\xa0\r\t\n ')
                xdict["reply_text"] = all_text.translate(trans_table)
                xdict["reply_text_length"] = self.text_count(xdict["reply_text"])
                xdict["topic_belong"] = topic_url
                xdict["fieldset_list"] = [str(q) for q in xdict["fieldset_list"]]
                replylist.append(xdict)
            return replylist

        topic_url = "https://bbs.kfpromax.com/" + url
        response = requests.get(topic_url, headers=self.headers, proxies=self.proxies)
        f = open("topic_sources/" + f"{url.replace('?', '@')}&page=1", "wt", encoding="gbk")
        # 这个html源码保存功能实现于按时间戳跳过陈旧贴之前，所以它会错误地存储第一个陈旧贴的第一页
        f.write(response.text.replace("\ufffd", ""))
        f.close()
        soup = BeautifulSoup(response.text, features="lxml")
        t = soup.find_all("title")[0].text
        if  t == "此帖被管理员关闭，暂时不能浏览 - 绯月ScarletMoon "\
        or  t == "读取数据错误（404 NOT FOUND）,原因：您要访问的链接无效,可能链接不完整,或数据已被删除! - 绯月ScarletMoon ":
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
            "reply_count": int(numbers_split[1]),
            "view_count": int(numbers_split[0]),
            "tui_count": int(re.findall("\d+", soup.find("a", id="read_tui").text)[0]),
            # 其实仔细想想帖子被推数和被浏览数还是具有一定参考价值的，因为低热度帖虽然不会被新一轮统计但同时这两项数据也不怎么会变
            "topic_time": format_time(
                f"{numbers_split[2]}-{numbers_split[3]}-{numbers_split[4]} {numbers_split[5]}:{numbers_split[6]}:00"),
            "record_time": int(time.time()),
        }
        replylist = get_onepage_replies(soup, topic_url)
        current_page = topic_url

        def echo():
            print(f"{index:<5}{len(replylist):>5}/{topic_info['reply_count']:<5}   {topic_info['topic_title']}, {current_page}")
        if disp: echo()
        for page in range(2, (topic_info["reply_count"] // 20) + 2):
            # 如果需要跳过部分帖子的某些前置页面，在这里设置
            skipped = {
                "https://bbs.kfpromax.com/read.php?tid=715016&sf=39b": 438,
                "https://bbs.kfpromax.com/read.php?tid=1027097&sf=e68": 148,
                "https://bbs.kfpromax.com/read.php?tid=798326&sf=457": 304,
                "https://bbs.kfpromax.com/read.php?tid=614788&sf=569": 167,
            }
            if topic_url in skipped and page < skipped[topic_url]: continue

            current_page = f"{topic_url}&page={page}"
            response = requests.get(current_page, headers=self.headers, proxies=self.proxies)
            f = open("topic_sources/"+f"{url.replace('?', '@')}&page={page}", "wt", encoding="gbk")
            f.write(response.text.replace("\ufffd", ""))
            f.close()
            # 源代码存储。上面相似部分是存储第一页，这里是存储后续页
            soup = BeautifulSoup(response.text, features="lxml")
            replylist = replylist + get_onepage_replies(soup, topic_url)

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
    mode = 2
    # 默认为2，填好cookie和ua即可运行
    # 也可以解码urllist后使用模式0
    kf = KFanalysis()

    if not os.path.exists("topic_datas"): os.mkdir("topic_datas")
    if not os.path.exists("topic_sources"): os.mkdir("topic_sources")
    if not os.path.exists("done_url_list"):
        f = open("done_url_list", "wt")
        f.close()

    if mode == 0:
    # 使用urllist时
        with open("url_list", "rt") as f:
            allurl = f.read().split("\n")
        f = open("done_url_list", "rt")
        done_url_list = f.read().split("\n")
        f.close()
        with open("done_url_list", "at") as f:
            for i, url in enumerate(allurl):
                if url in done_url_list:
                    print(f"{i+1}, skipped.")
                    continue
                topic_data = kf.get_onetopic_info(url=url, disp=True, index=i+1)
                inn = open(rf"topic_datas\{url.replace('?', '@')}", "wb")
                pickle.dump(topic_data, inn)
                inn.close()
                f.write(url + "\n")
                f.flush()
                time.sleep(kf.timegap_topic_out)
    elif mode == 1:
    # 持有alltopic_url时
        with open("alltopic_url_arhive", "rb") as f:
            alltopic_url = pickle.load(f)
            kf.alltopic_url = alltopic_url
        with open("alltopic_info_arhive", "wb") as f:
            kf.get_alltopic_info()
            pickle.dump(kf.all_topic_info, f)
    else:
    # 未持有alltopic_url时
        with open("alltopic_url_arhive", "wb") as f:
            kf.get_alltopic_url()
            pickle.dump(kf.alltopic_url, f)
        with open("alltopic_info_arhive", "wb") as f:
            kf.get_alltopic_info()
            pickle.dump(kf.all_topic_info, f)