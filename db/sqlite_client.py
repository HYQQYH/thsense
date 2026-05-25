import sqlite3
from datetime import datetime
from typing import Optional

class SQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                time TEXT NOT NULL,
                source TEXT,
                url TEXT UNIQUE,
                content TEXT,
                raw_status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_news(raw_status);
            CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_news(time);

            CREATE TABLE IF NOT EXISTS classified_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER REFERENCES raw_news(id),
                category TEXT,
                status TEXT DEFAULT 'pending',
                analysis_report TEXT,
                analyzed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_classified_status ON classified_news(status);
            CREATE INDEX IF NOT EXISTS idx_classified_raw_id ON classified_news(raw_id);
        """)
        self.conn.commit()

    def insert_raw_news(self, news_list: list[dict]):
        for news in news_list:
            try:
                self.conn.execute("""
                    INSERT INTO raw_news (title, time, source, url, content, raw_status)
                    VALUES (:title, :time, :source, :url, :content, 'new')
                """, news)
            except sqlite3.IntegrityError:
                pass  # url 重复，跳过
        self.conn.commit()

    def get_all_raw_news(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM raw_news").fetchall()
        return [dict(row) for row in rows]

    def get_unclassified_news(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM raw_news WHERE raw_status = 'new'
        """).fetchall()
        return [dict(row) for row in rows]

    def mark_raw_news_classified(self, ids: list[int]):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(f"""
            UPDATE raw_news SET raw_status = 'classified'
            WHERE id IN ({placeholders})
        """, ids)
        self.conn.commit()

    def insert_classified_news(self, raw_ids: list[int], categories: list[str], status: str = "pending"):
        for raw_id, category in zip(raw_ids, categories):
            self.conn.execute("""
                INSERT INTO classified_news (raw_id, category, status)
                VALUES (?, ?, ?)
            """, (raw_id, category, status))
        self.conn.commit()

    def get_pending_analysis(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT cn.*, rn.title, rn.time, rn.source, rn.url, rn.content
            FROM classified_news cn
            JOIN raw_news rn ON cn.raw_id = rn.id
            WHERE cn.status = 'pending' 
        """).fetchall()
        return [dict(row) for row in rows]

    def mark_analyzed(self, classified_id: int, report_path: str):
        self.conn.execute("""
            UPDATE classified_news
            SET status = 'analyzed', analysis_report = ?, analyzed_at = ?
            WHERE id = ?
        """, (report_path, datetime.now().isoformat(), classified_id))
        self.conn.commit()

    def mark_error(self, classified_id: int):
        self.conn.execute("""
            UPDATE classified_news SET status = 'error' WHERE id = ?
        """, (classified_id,))
        self.conn.commit()

    def mark_filtered(self, classified_id: int):
        self.conn.execute("""
            UPDATE classified_news SET status = 'filtered' WHERE id = ?
        """, (classified_id,))
        self.conn.commit()

    def revert_analyzed_to_pending(self):
        self.conn.execute("""
            UPDATE classified_news SET status = 'pending' WHERE status = 'analyzed'
        """)
        self.conn.commit()

    def get_config(self, key: str) -> str:
        import os
        return os.environ.get(key.upper(), "")

    def close(self):
        self.conn.close()