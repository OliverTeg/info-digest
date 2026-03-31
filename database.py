"""
数据存储模块 — 使用 SQLite 管理 RSS 源和文章数据
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "info_digest.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.executescript("""
            -- RSS 订阅源
            CREATE TABLE IF NOT EXISTS feeds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT,
                url         TEXT UNIQUE NOT NULL,
                category    TEXT DEFAULT '',
                group_name  TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                last_fetched_at TEXT
            );

            -- 文章/条目
            CREATE TABLE IF NOT EXISTS articles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id         INTEGER NOT NULL,
                title           TEXT,
                link            TEXT UNIQUE,
                author          TEXT DEFAULT '',
                summary         TEXT DEFAULT '',
                content         TEXT DEFAULT '',
                published       TEXT,
                fetched_at      TEXT DEFAULT (datetime('now')),
                is_read         INTEGER DEFAULT 0,
                is_deleted      INTEGER DEFAULT 0,
                ai_summary      TEXT DEFAULT '',
                ai_summary_zh   TEXT DEFAULT '',
                reading_time    INTEGER DEFAULT 0,
                keywords        TEXT DEFAULT '',
                summarized_at   TEXT,
                FOREIGN KEY (feed_id) REFERENCES feeds(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id);
            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published DESC);

            -- 用户画像（单用户，只存一行，id=1）
            CREATE TABLE IF NOT EXISTS user_profile (
                id           INTEGER PRIMARY KEY DEFAULT 1,
                name         TEXT DEFAULT '',
                profession   TEXT DEFAULT '',
                interests    TEXT DEFAULT '',   -- JSON 数组，如 ["AI","技术","财经"]
                goals        TEXT DEFAULT '',   -- JSON 数组，如 ["学习新技术","追踪市场"]
                custom_note  TEXT DEFAULT '',   -- 用户自由补充的说明
                created_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            );
        """)


# ────────────────────── Feed CRUD ──────────────────────

def add_feed(url: str, title: str = "", category: str = "", group_name: str = "") -> dict:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO feeds (url, title, category, group_name) VALUES (?, ?, ?, ?)",
            (url, title, category, group_name),
        )
        return {"id": cur.lastrowid, "url": url, "title": title}


def remove_feed(feed_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        return cur.rowcount > 0


def list_feeds() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM feeds ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_feed(feed_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        return dict(row) if row else None


def update_feed_title(feed_id: int, title: str):
    with get_db() as conn:
        conn.execute("UPDATE feeds SET title = ? WHERE id = ?", (title, feed_id))


def update_feed(feed_id: int, url: str = None, title: str = None, category: str = None, group_name: str = None) -> bool:
    """修改订阅源信息"""
    fields, params = [], []
    if url is not None:
        fields.append("url = ?"); params.append(url)
    if title is not None:
        fields.append("title = ?"); params.append(title)
    if category is not None:
        fields.append("category = ?"); params.append(category)
    if group_name is not None:
        fields.append("group_name = ?"); params.append(group_name)
    if not fields:
        return False
    params.append(feed_id)
    with get_db() as conn:
        cur = conn.execute(f"UPDATE feeds SET {', '.join(fields)} WHERE id = ?", params)
        return cur.rowcount > 0


def update_last_fetched(feed_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE feeds SET last_fetched_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), feed_id),
        )


# ────────────────────── Article CRUD ──────────────────────

def save_articles(feed_id: int, articles: list[dict]) -> int:
    """批量保存文章，跳过已存在的（按 link 去重）。返回新增数量。"""
    inserted = 0
    with get_db() as conn:
        for a in articles:
            try:
                conn.execute(
                    """INSERT INTO articles
                       (feed_id, title, link, author, summary, content, published, is_paywalled)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        feed_id,
                        a.get("title", ""),
                        a.get("link", ""),
                        a.get("author", ""),
                        a.get("summary", ""),
                        a.get("content", ""),
                        a.get("published", ""),
                        1 if a.get("is_paywalled") else 0,
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # 重复文章，跳过
    return inserted


def list_articles(feed_id: int | None = None, limit: int = 50, offset: int = 0, include_deleted: bool = False) -> list[dict]:
    with get_db() as conn:
        clauses = []
        params: list = []
        if not include_deleted:
            clauses.append("is_deleted = 0")
        if feed_id is not None:
            clauses.append("feed_id = ?")
            params.append(feed_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM articles {where} ORDER BY published DESC, fetched_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]


def get_article(article_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        return dict(row) if row else None


def mark_article_read(article_id: int):
    with get_db() as conn:
        conn.execute("UPDATE articles SET is_read = 1 WHERE id = ?", (article_id,))


def update_article_content(article_id: int, content: str, is_paywalled: int = 0):
    """更新文章正文内容（用于摘要前二次全文抓取）"""
    with get_db() as conn:
        conn.execute(
            "UPDATE articles SET content = ?, is_paywalled = ? WHERE id = ?",
            (content, is_paywalled, article_id),
        )


def delete_article(article_id: int):
    """软删除"""
    with get_db() as conn:
        conn.execute("UPDATE articles SET is_deleted = 1 WHERE id = ?", (article_id,))


# ────────────────────── AI 摘要相关 ──────────────────────

def update_article_summary(article_id: int, ai_summary: str = "", ai_summary_zh: str = "",
                           reading_time: int = 0, keywords: str = "", title_zh: str = ""):
    """更新文章的 AI 摘要字段（含标题翻译）"""
    with get_db() as conn:
        conn.execute(
            """UPDATE articles
               SET ai_summary = ?, ai_summary_zh = ?, reading_time = ?,
                   keywords = ?, title_zh = ?, summarized_at = datetime('now')
               WHERE id = ?""",
            (ai_summary, ai_summary_zh, reading_time, keywords, title_zh, article_id),
        )


def list_articles_pending_summary(limit: int = 10) -> list[dict]:
    """列出尚未生成 AI 摘要的文章"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE is_deleted = 0 AND (ai_summary IS NULL OR ai_summary = '')
               ORDER BY fetched_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def migrate_db():
    """数据库迁移：为旧表添加新字段（安全幂等）"""
    new_columns = [
        ("ai_summary", "TEXT DEFAULT ''"),
        ("ai_summary_zh", "TEXT DEFAULT ''"),
        ("title_zh", "TEXT DEFAULT ''"),
        ("reading_time", "INTEGER DEFAULT 0"),
        ("keywords", "TEXT DEFAULT ''"),
        ("summarized_at", "TEXT"),
        ("is_paywalled", "INTEGER DEFAULT 0"),  # 1=疑似付费墙，内容不完整
    ]
    with get_db() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
        for col_name, col_type in new_columns:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
                print(f"  [迁移] 已添加字段: articles.{col_name}")


# ────────────────────── 用户画像 ──────────────────────

def get_user_profile() -> dict | None:
    """获取用户画像（单用户，id=1）"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
        return dict(row) if row else None


def save_user_profile(name: str, profession: str, interests: str,
                      goals: str, custom_note: str = "") -> dict:
    """保存或更新用户画像（upsert）"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_profile (id, name, profession, interests, goals, custom_note, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, profession=excluded.profession,
                 interests=excluded.interests, goals=excluded.goals,
                 custom_note=excluded.custom_note, updated_at=excluded.updated_at""",
            (name, profession, interests, goals, custom_note),
        )
    return get_user_profile()
