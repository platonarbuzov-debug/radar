from typing import List, Dict
import time
from app.storage.db import get_db

def upsert_articles(items: List[Dict]) -> int:
    with get_db() as conn:
        for it in items:
            conn.execute("""
            INSERT OR IGNORE INTO articles(
              source,url,title,published_ts,lang,summary,content,entities,secids,source_group,cred_weight,fetched_ts
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
              it["source"], it["url"], it["title"], it["published_ts"], it["lang"],
              it.get("summary",""), it.get("content",""), "[]","[]",
              it.get("source_group","MEDIA"), it.get("cred_weight",0.5), int(time.time())
            ))
        return conn.total_changes or 0
