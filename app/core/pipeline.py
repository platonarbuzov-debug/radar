import time, hashlib
from collections import defaultdict
from typing import List, Dict

from app.core.config import SOURCES, HOTNESS_WEIGHTS, TOP_K_DEFAULT
from app.fetchers.rss_html import fetch_all
from app.storage.ingest import upsert_articles
from app.storage.db import get_db
from app.nlp.entities import extract_secids
from app.nlp.embeddings import embed_texts, cluster_texts
from app.nlp.topics import (
    infer_targets, relevance_score, company_secids, REL_MIN
)
from app.scoring.hotness import (
    recency_score, velocity_score, credibility_score, confirmations_score,
    breadth_score, norm_clip, combine_logistic
)
from app.core.impact import price_impact_metrics

MIN_RETURN = 5         # минимум карточек
EXTRA_THRESHOLD = 0.62 # добавляем сверх лимита, если hotness высокий


def _hash_titles(titles:List[str]) -> str:
    return hashlib.sha1(("||".join(sorted(set(titles)))).encode()).hexdigest()[:16]

def _validity(cred_scores, groups, max_age_ts, now_ts):
    cred = credibility_score(cred_scores)
    conf = confirmations_score(groups)
    rec  = recency_score(max_age_ts, now_ts)
    return round((0.5*cred + 0.3*conf + 0.2*rec), 3)

def _ensure_secids(text: str, rel: float):
    secids = extract_secids(text) or company_secids(text) or infer_targets(text)
    # last-resort: даже при низкой релевантности даём базовый прокси рынка
    if not secids:
        secids = ["USDRUB_TOM"]
    return secids

def _calc_impact(secids, hours, now):
    if not secids:
        return {"pct_move":None,"volume_ratio":None,"price_anomaly":None}
    pct, vr, pa = price_impact_metrics(secids[0], min(6, hours), now)
    return {"pct_move":pct,"volume_ratio":vr,"price_anomaly":pa}

def _features_base(ts_list, now, cred_list, groups, secids, rel):
    return {
        "recency":       recency_score(max(ts_list), now),
        "velocity":      velocity_score(ts_list, now),
        "credibility":   credibility_score(cred_list),
        "confirmations": confirmations_score(groups),
        "breadth":       breadth_score(secids),
        "relevance":     rel
    }

def _event_from_single(row, now, hours, rel_min):
    _id, source, url, title, ts, lang, summary, cred, group = row
    text=(title or '')+' '+(summary or '')
    rel = relevance_score(text)
    if rel < rel_min and group not in ('REG','EXCH'):
        return None
    secids = _ensure_secids(text, rel)
    imp = _calc_impact(secids, hours, now)
    feats=_features_base([ts], now, [cred], [group], secids, rel)
    feats["price_move"]    = norm_clip(abs(imp["pct_move"]) if imp["pct_move"] is not None else None, 0.5, 6.0)
    feats["volume_ratio"]  = norm_clip(imp["volume_ratio"], 0.8, 3.0)
    feats["price_anomaly"] = norm_clip(imp["price_anomaly"], 1.0, 4.0)
    hot = combine_logistic(HOTNESS_WEIGHTS, feats)
    return {
        'dedup_group': str(_id),
        'headline': (title or 'Событие')[:180],
        'hotness': hot,
        'why_now': f'Одиночный источник {group}.',
        'secids': secids,
        'sources': [{'url': url, 'source': source}],
        'timeline': [{'t': ts, 'source': source, 'url': url, 'title': title}],
        'articles': [{'id':_id,'source':source,'url':url,'title':title,'published_ts':ts,'summary':summary,'cred_weight':cred,'group':group}],
        'features': feats,
        'validity': round(0.6*min(1.0,cred)+0.4*(1.0 if group in ('REG','EXCH') else 0.5),3),
        'impact': imp,
        't0': ts, 't1': ts
    }

def _fallback(rows, now:int, hours:int, need:int):
    """Многоступенчатый фоллбек: REL_MIN → 0.25 → 0.0 (но только REG/EXCH/TIER1)."""
    prio={'REG':3,'EXCH':2,'TIER1':1}
    rows_sorted = sorted(rows, key=lambda r:(prio.get(r[8],0), r[7], r[4]), reverse=True)
    out=[]; seen_urls=set(); seen_titles=set()

    def try_level(rel_min):
        nonlocal out
        for r in rows_sorted:
            if len(out) >= need: break
            if not r[2] or r[2] in seen_urls: 
                continue
            ev = _event_from_single(r, now, hours, rel_min)
            if not ev: 
                continue
            title_key = ev['headline'].lower().strip()
            if title_key in seen_titles: 
                continue
            seen_titles.add(title_key)
            seen_urls.add(r[2]); out.append(ev)

    # уровень 1: базовый порог релевантности
    try_level(REL_MIN)
    # уровень 2: мягче порог
    if len(out) < need:
        try_level(0.25)
    # уровень 3: берём всё из REG/EXCH/TIER1 без порога (чтобы добить до MIN)
    if len(out) < need:
        for r in rows_sorted:
            if len(out) >= need: break
            if r[8] not in ('REG','EXCH','TIER1'): 
                continue
            if not r[2] or r[2] in seen_urls: 
                continue
            ev = _event_from_single(r, now, hours, 0.0)
            if not ev: 
                continue
            title_key = ev['headline'].lower().strip()
            if title_key in seen_titles: 
                continue
            seen_titles.add(title_key); seen_urls.add(r[2]); out.append(ev)
    return out

def build_events(hours:int=24, top_k:int=TOP_K_DEFAULT) -> List[Dict]:
    items = fetch_all(SOURCES)
    upsert_articles(items)

    now=int(time.time())
    window_ts=now - hours*3600

    with get_db() as conn:
        rows = conn.execute("""
         SELECT id, source, url, title, published_ts, lang, summary, cred_weight, source_group
         FROM articles WHERE published_ts>=? ORDER BY published_ts DESC
        """, (window_ts,)).fetchall()
    if not rows:
        return []

    texts=[(r[3] or "") + " " + (r[6] or "") for r in rows]
    embeds=embed_texts(texts)
    labels=cluster_texts(embeds)

    clusters=defaultdict(list)
    for lab, r in zip(labels, rows):
        clusters[int(lab)].append({
            "id":r[0],"source":r[1],"url":r[2],"title":r[3],
            "published_ts":r[4],"summary":r[6],
            "cred_weight":r[7],"group":r[8]
        })

    events=[]
    for _, arts in clusters.items():
        if not arts: 
            continue

        uniq_groups=set(a["group"] for a in arts)
        uniq_sources=set(a["source"] for a in arts)
        titles=[a["title"] for a in arts if a["title"]]
        if not titles:
            continue

        text_concat=" ".join([(a["title"] or "")+" "+(a["summary"] or "") for a in arts])
        rel = relevance_score(text_concat)

        # Отсечение шума (кроме REG/EXCH)
        if rel < REL_MIN and not (("REG" in uniq_groups) or ("EXCH" in uniq_groups)):
            continue
        # Требование подтверждений
        if len(uniq_sources)<2 and not (("REG" in uniq_groups) or ("EXCH" in uniq_groups)):
            continue

        secids = _ensure_secids(text_concat, rel)

        dedup_id=_hash_titles(titles)
        t0, t1 = min(a["published_ts"] for a in arts), max(a["published_ts"] for a in arts)
        timeline=sorted(
            [{"t":a["published_ts"],"source":a["source"],"url":a["url"],"title":a["title"]} for a in arts],
            key=lambda x:x["t"]
        )

        ts_list=[a["published_ts"] for a in arts]
        feats=_features_base(ts_list, now, [a["cred_weight"] for a in arts], [a["group"] for a in arts], secids, rel)
        imp=_calc_impact(secids, hours, now)
        feats["price_move"]    = norm_clip(abs(imp["pct_move"]) if imp["pct_move"] is not None else None, 0.5, 6.0)
        feats["volume_ratio"]  = norm_clip(imp["volume_ratio"], 0.8, 3.0)
        feats["price_anomaly"] = norm_clip(imp["price_anomaly"], 1.0, 4.0)

        hotness = combine_logistic(HOTNESS_WEIGHTS, feats)
        validity = _validity([a["cred_weight"] for a in arts], [a["group"] for a in arts], max(ts_list), now)
        headline = max(arts, key=lambda a:(a["cred_weight"], len(a["title"] or "")))["title"][:180]
        why = f"Публикации из {len(uniq_sources)} источников ({', '.join(sorted(uniq_groups))})."

        seen=set(); sources=[]
        for a in arts:
            if a["source"] in seen: continue
            seen.add(a["source"]); sources.append({"url":a["url"], "source":a["source"]})
            if len(sources)>=5: break

        events.append({
            "dedup_group": dedup_id,
            "headline": headline,
            "hotness": hotness,
            "why_now": why,
            "secids": secids,
            "sources": sources,
            "timeline": timeline,
            "articles": arts,
            "features": feats,
            "validity": validity,
            "impact": imp,
            "t0": t0, "t1": t1
        })

    # гарантированный минимум карточек
    need = max(top_k, MIN_RETURN)
    if len(events) < need:
        with get_db() as conn:
            rows_f = conn.execute(
                """
                SELECT id, source, url, title, published_ts, lang, summary, cred_weight, source_group
                FROM articles WHERE published_ts>=? ORDER BY published_ts DESC LIMIT 400
                """, (window_ts,)
            ).fetchall()
        events += _fallback(rows_f, now, hours, need - len(events))

    # сортировка и «умный» овершут
    events.sort(key=lambda e:(e["hotness"], e.get("validity",0)), reverse=True)
    base = events[:need]
    extra = [e for e in events[need:need+10] if e["hotness"]>=EXTRA_THRESHOLD]
    return base + extra
