from __future__ import annotations
import time
import logging
from typing import List, Dict

import httpx
import feedparser
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Source

# Тише для trafilatura
logging.getLogger("trafilatura").setLevel(logging.CRITICAL)

client = httpx.Client(timeout=20.0, headers={"User-Agent": "RADAR/1.0"})

STOP_PATTERNS_IN_TITLE = [
    "скачать приложение", "rss", "лента", "подпис", "подробнее",
    "читать далее", "подкаст", "комментарии", "о проекте", "карта сайта"
]

def good_title(t: str) -> bool:
    if not t:
        return False
    tl = t.lower().strip()
    if any(p in tl for p in STOP_PATTERNS_IN_TITLE):
        return False
    if len(tl) < 20:
        return False
    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _rss(url: str):
    # Качаем через httpx с нормальным UA (меньше 403/редиректов), потом парсим.
    resp = client.get(url, follow_redirects=True)
    resp.raise_for_status()
    text = resp.text
    return feedparser.parse(text)


def _clean_html(html: str) -> str:
    # Безопасно чистим: не дергаем парсер на пустых строках/не-HTML
    if not html:
        return ""
    if "<" not in html and ">" not in html:
        return str(html).strip()
    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False) or ""
        return text
    except Exception:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(" ", strip=True)

def fetch_source(src: Source, limit: int = 100) -> List[Dict]:
    items: List[Dict] = []
    if src.kind == "rss":
        feed = _rss(src.url)
        for e in feed.entries[:limit]:
            title = (e.get("title") or "").strip()
            if not good_title(title):
                continue
            ts = int(time.mktime(e.published_parsed)) if getattr(e, "published_parsed", None) else int(time.time())
            items.append({
                "source": src.name,
                "url": e.get("link"),
                "title": title[:400],
                "published_ts": ts,
                "lang": src.lang,
                "summary": _clean_html(e.get("summary", "")),
                "content": "",
                "cred_weight": src.weight,
                "source_group": src.group
            })
    else:
        # На будущее: поддержка html-страниц-лент (сейчас источники все RSS)
        resp = client.get(src.url)
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.select("a[href]")[:limit * 2]:
            href = a["href"]
            t = a.get_text(strip=True)
            if href.startswith(("http://", "https://")) and good_title(t):
                items.append({
                    "source": src.name,
                    "url": href,
                    "title": t[:400],
                    "published_ts": int(time.time()),
                    "lang": src.lang,
                    "summary": "",
                    "content": "",
                    "cred_weight": src.weight,
                    "source_group": src.group
                })
    return items

def fetch_all(sources: List[Source]) -> List[Dict]:
    out: List[Dict] = []
    for s in sources:
        try:
            out.extend(fetch_source(s))
        except Exception:
            # не валим пайплайн из-за одного источника
            continue
    return out
