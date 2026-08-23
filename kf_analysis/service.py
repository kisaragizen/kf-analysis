import json, sqlite3, time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Client:
    def __init__(self, config):
        self.session = requests.Session()
        self.session.headers.update(config.headers)
        self.session.proxies.update(config.proxies)
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, url):
        return self.session.get(url, timeout=15)


class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.init_tables()

    def init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS topic (
            topic_id    INTEGER PRIMARY KEY,
            topic_sf    TEXT,
            board_id    INTEGER,
            board_name  TEXT,
            title       TEXT,
            reply_count INTEGER,
            topic_time  INTEGER,
            record_time INTEGER,
            status      TEXT
        );
        CREATE TABLE IF NOT EXISTS reply (
            topic_id        INTEGER NOT NULL REFERENCES topic(topic_id),
            reply_id        TEXT,
            topic_sf        TEXT,
            floor           INTEGER,
            username        TEXT,
            homepage_id     INTEGER,
            homepage_sf     TEXT,
            reply_box_color TEXT,
            reply_time      INTEGER,
            reply_text      TEXT,
            record_time     INTEGER,
            status          TEXT,
            image_list      TEXT,
            complete        INTEGER,
            hidden_content  TEXT,
            keyword_list    TEXT,
            PRIMARY KEY (topic_id, reply_id)
        );
        CREATE INDEX IF NOT EXISTS idx_reply_time ON reply(reply_time);
        """)

    def has_topic(self, topic_id):
        row = self.conn.execute("SELECT 1 FROM topic WHERE topic_id=?", (topic_id,)).fetchone()
        return row is not None

    def should_skip(self, topic_id, listing_count):
        row = self.conn.execute("SELECT reply_count FROM topic WHERE topic_id=?", (topic_id,)).fetchone()
        return row is not None and row[0] == listing_count + 1

    def get_topic_floor_count(self, topic_id):
        # 为什么不用 topic: reply_count？为了遇到最小化条目也能正常返回
        row = self.conn.execute("SELECT COUNT(*) FROM reply WHERE topic_id=?", (topic_id,)).fetchone()
        return row[0]

    def get_topic_usernames(self, topic_id):
        rows = self.conn.execute("SELECT DISTINCT username FROM reply WHERE topic_id=?", (topic_id,)).fetchall()
        return [r[0] for r in rows]

    def insert_closed_topic(self, topic_id, topic_sf, status):
        # 为被锁定贴与被删除贴添加占位最小化条目
        self.conn.execute(
            "INSERT INTO topic (topic_id, topic_sf, record_time, status) VALUES (?,?,?,?)",
            (topic_id, topic_sf, int(time.time()), status))
        self.conn.commit()

    def save_topic_tx(self, topic_info):
        # 全量保存。事务性处理，失败回退
        with self.conn:
            tid = topic_info["topic_id"]
            self.conn.execute("DELETE FROM reply WHERE topic_id=?", (tid,))
            self.conn.execute(
                "INSERT OR REPLACE INTO topic (topic_id, topic_sf, board_id, board_name, title, reply_count, "
                "topic_time, record_time, status) VALUES (?,?,?,?,?,?,?,?, 'active')",
                (tid, topic_info["topic_sf"], topic_info["board_id"], topic_info["board_name"],
                 topic_info["topic_title"], topic_info["reply_count"], topic_info["topic_time"],
                 topic_info["record_time"]))
            self.insert_replies(tid, topic_info)

    def save_incremental_tx(self, topic_info):
        # 增量保存。事务性处理，失败回退
        with self.conn:
            tid = topic_info["topic_id"]
            last_floor = self.conn.execute(
                "SELECT MAX(floor) FROM reply WHERE topic_id=?", (tid,)).fetchone()[0]
            self.insert_replies(tid, topic_info, last_floor)
            self.conn.execute(
                "UPDATE topic SET title=?, reply_count=?, record_time=? WHERE topic_id=?",
                (topic_info["topic_title"], topic_info["reply_count"], topic_info["record_time"], tid))

    def insert_replies(self, tid, topic_info, min_floor=None):
        # 全增量共用回复行写入，跳过楼层号低于 min_floor 的
        rows = []
        for r in topic_info["reply_list"]:
            if min_floor is not None and r["floor"] <= min_floor: continue
            rows.append((tid, r["reply_id"], r["topic_sf"], r["floor"], r["username"],
                         r["homepage_id"], r["homepage_sf"], r["reply_box_color"], r["reply_time"],
                         r["reply_text"], topic_info["record_time"], "active",
                         json.dumps(r["image_list"], ensure_ascii=False),
                         r["complete"],
                         json.dumps(r["hidden_content"], ensure_ascii=False),
                         json.dumps(r["keyword_list"], ensure_ascii=False)))
        self.conn.executemany(
            "INSERT INTO reply (topic_id, reply_id, topic_sf, floor, username, homepage_id, homepage_sf, "
            "reply_box_color, reply_time, reply_text, record_time, status, image_list, complete, "
            "hidden_content, keyword_list) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    def stats(self):
        topic_count = self.conn.execute("SELECT COUNT(*) FROM topic").fetchone()[0]
        reply_count = self.conn.execute("SELECT COUNT(*) FROM reply").fetchone()[0]
        last_record = self.conn.execute("SELECT MAX(record_time) FROM topic").fetchone()[0]
        return {"topic_count": topic_count, "reply_count": reply_count, "last_record_time": last_record}
