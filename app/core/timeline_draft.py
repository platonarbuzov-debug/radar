import time, os, httpx, orjson as json
from typing import List, Dict

def build_timeline(items: List[Dict]):
    # items: [{source, url, published_ts, title}]
    events = sorted(
        [{"t":it["published_ts"], "source":it["source"], "url":it["url"], "title":it["title"]} for it in items],
        key=lambda x: x["t"]
    )
    return events

# Черновик через OpenRouter (если ключ есть)
def gen_draft_llm(event):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    prompt = f"""Ты — финансовый редактор. Дай черновик заметки по событию.
Формат:
Заголовок:
Лид (1 абзац):
• Буллет 1
• Буллет 2
• Буллет 3
Цитата (короткая):
Ссылки: {', '.join([s['url'] for s in event['sources'][:5]])}
Дано:
Заголовок кластера: {event['headline']}
Почему сейчас: {event['why_now']}
Сущности/тикеры: {', '.join(event.get('entities',[]))} / {', '.join(event.get('secids',[]))}
Короткие тезисы статей:
""" + "\n".join([f"- {x['title']}" for x in event["articles"]][:6])

    payload = {
      "model": "meta-llama/llama-3.1-70b-instruct",  # бесплатно/дёшево по OpenRouter; при лимитах замените
      "messages": [{"role":"user","content":prompt}],
      "temperature": 0.5,
      "max_tokens": 450
    }
    headers = {
      "Authorization": f"Bearer {key}",
      "HTTP-Referer": "https://example-radar",
      "X-Title": "RADAR Draft"
    }
    try:
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None

# Фолбэк без LLM
def gen_draft_rule_based(event):
    h = event['headline']
    why = event['why_now']
    bullets = []
    if event.get('secids'):
        bullets.append(f"Задействованные тикеры: {', '.join(event['secids'][:5])}")
    bullets.append(f"Подтверждений: {len(event['articles'])}, источники: {', '.join(sorted(set(a['source'] for a in event['articles'])))}")
    bullets.append(f"Таймлайн: {time.strftime('%d.%m %H:%M', time.localtime(event['timeline'][0]['t']))} → {time.strftime('%d.%m %H:%M', time.localtime(event['timeline'][-1]['t']))}")
    quote = event['articles'][0]['title'][:140] + "…"
    links = "\n".join([f"- {s['url']}" for s in event['sources'][:5]])
    return f"""Заголовок: {h}
Лид: {why}
• {bullets[0]}
• {bullets[1]}
• {bullets[2]}
Цитата: «{quote}»
Ссылки:
{links}
"""
