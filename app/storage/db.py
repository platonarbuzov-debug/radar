import sqlite3, os, time
from contextlib import contextmanager

DB_PATH = os.path.join(os.getcwd(), "data", "radar.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT, url TEXT UNIQUE, title TEXT, published_ts INTEGER,
  lang TEXT, summary TEXT, content TEXT, entities TEXT, secids TEXT,
  source_group TEXT, cred_weight REAL, fetched_ts INTEGER
);
"""

@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA synchronous=NORMAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
