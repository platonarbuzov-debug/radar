from typing import Dict, Any, List
import math

# --- утилиты ---
def _num(x, nd=2, suffix=""):
    return (f"{x:.{nd}f}{suffix}" if isinstance(x, (int,float)) else "n/a")

def _impact(ev: Dict[str, Any]):
    imp = ev.get("impact") or {}
    return imp.get("pct_move"), imp.get("volume_ratio"), imp.get("price_anomaly")

def _is_fx(secid: str) -> bool:
    s = (secid or "").upper()
    return "RUB" in s or s.endswith("_TOM") or s.endswith("TOM")

def _conf(pct, vr, pa, hot):
    # 0..1 сила сигнала: метрики и общая "горячесть"
    sc = 0.0
    if isinstance(pct,(int,float)): sc += min(abs(pct)/2.0, 1.0)*0.35  # 2% -> 0.35
    if isinstance(vr,(int,float)):  sc += min((vr-1.0)/1.5, 1.0)*0.30  # 2.5x -> 0.30
    if isinstance(pa,(int,float)):  sc += min(pa/4.0, 1.0)*0.15        # 4σ -> 0.15
    if isinstance(hot,(int,float)): sc += min(hot,1.0)*0.20            # hotness ~ 0..1
    return max(0.0, min(sc, 1.0))

def _dir_from_pct(pct):
    if isinstance(pct,(int,float)):
        return 1 if pct>0 else (-1 if pct<0 else 0)
    return 0

# --- генераторы действий ---
def _fx_play(secid: str, pct, vr, pa, hot) -> str:
    # Базовый инструмент: USDRUB_TOM (доллар-рубль)
    long_name = "лонг USD/RUB" if "USD" in secid else ("лонг EUR/RUB" if "EUR" in secid else "лонг CNY/RUB")
    short_name = long_name.replace("лонг","шорт")
    conf = _conf(pct, vr, pa, hot)
    d = _dir_from_pct(pct)

    # Правила входа
    if conf >= 0.65:
        bias = long_name if d>=0 else short_name
        size = "до 1.0R"
        entry = "вход 30/30/40 по рынку и на откате 0.15–0.25%"
        stop  = "стоп 0.5–0.7% от цены входа, трейлинг 0.4%"
        take  = "тейк 1.0–1.5%"
        alt   = "альтернатива: набор по сетке каждые 0.15% ещё 2 шага"
    elif conf >= 0.40:
        bias = (long_name if d>=0 else short_name) + " (умеренно)"
        size = "до 0.6R"
        entry = "вход частями на пробой +0.25% от текущего хай/лоу окна"
        stop  = "стоп 0.6%"
        take  = "тейк 0.8–1.0%"
        alt   = "альтернатива: пара USD/RUB против корзины (1/2 USD + 1/2 EUR)"
    else:
        # Слабый сигнал — всё равно даём план: пробой/коридор
        bias = "торговля пробоя диапазона"
        size = "до 0.3R"
        entry = "алерты ±0.30% от текущей цены; вход по направлению пробоя одним кликом"
        stop  = "стоп 0.45%, перезаход разрешён 1 раз"
        take  = "тейк 0.6–0.8%"
        alt   = "если ложный пробой — разворот после возврата в диапазон, половинный размер"
    return f"Идея: {bias} | размер: {size} | вход: {entry} | стоп: {stop} | тейк: {take} | {alt}."

def _equity_play(secid: str, pct, vr, pa, hot) -> str:
    conf = _conf(pct, vr, pa, hot)
    d = _dir_from_pct(pct)
    bias_name = ("лонг " + secid) if d>=0 else ("шорт " + secid)

    if conf >= 0.70 and isinstance(vr,(int,float)) and vr>=1.4:
        size = "до 1.0R"
        entry = "вход 30/30/40: рынок + отбитый откат −0.3%"
        stop  = "стоп 1.0% (или за локальным минимумом/максимумом)"
        take  = "тейк 2.0–3.0% или до закрытия импульса"
        alt   = "пара против сектора/индекса (если доступно)"
        bias  = f"моментум-продолжение: {bias_name}"
    elif conf >= 0.45:
        size = "до 0.6R"
        entry = "вход на пробой хай/лоу окна; подтверждение объёмом >1.2x"
        stop  = "стоп 0.9%"
        take  = "тейк 1.5–2.0%"
        alt   = "если нет объёма — работать от откатов по тренду 0.3–0.5%"
        bias  = f"тренд/пробой: {bias_name}"
    else:
        # Слабый — даём mean-reversion или свинг от уровней
        size = "до 0.35R"
        entry = "сеткой: лимитки через 0.3% x3 к среднему цены за окно"
        stop  = "стоп 0.8%"
        take  = "тейк 0.9–1.2%"
        alt   = "если breakout с объёмом >1.2x — переключиться на пробой по рынку"
        bias  = f"свинг/коридор: {secid} (двунаправленно)"
    return f"Идея: {bias} | размер: {size} | вход: {entry} | стоп: {stop} | тейк: {take} | {alt}."

def trader_actions(ev: Dict[str, Any]) -> str:
    """
    Возвращает строку с чётким планом действий трейдера по событию:
    направление/идея, размер позиции, правила входа, стоп/тейк, альтернатива.
    Гарантировано не пусто (даже при слабом сигнале).
    """
    secids: List[str] = ev.get("secids") or []
    base = secids[0] if secids else "USDRUB_TOM"
    pct, vr, pa = _impact(ev)
    hot = ev.get("hotness", 0.0)

    play = _fx_play(base, pct, vr, pa, hot) if _is_fx(base) else _equity_play(base, pct, vr, pa, hot)

    # Добавим краткую подпись метрик и обоснование
    pct_s, vr_s, pa_s = _num(pct,2,"%"), _num(vr,2,"x"), _num(pa,1,"σ")
    why = ev.get("why_now") or ""
    return f"{play}\nМетрики: Δ {pct_s} · vol {vr_s} · σ {pa_s}. Основание: {why}"

def channel_draft(ev: Dict[str, Any]) -> str:
    """
    Черновик для поста: заголовок + краткое «почему» + метрики + идея.
    """
    head = ev.get("headline") or "Сюжет"
    secids: List[str] = ev.get("secids") or ["—"]
    pct, vr, pa = _impact(ev)
    hot = ev.get("hotness", 0.0)

    # Короткая идея в одну строку
    base = secids[0]
    if "RUB" in base or base.endswith("_TOM") or base.endswith("TOM"):
        idea = "USD/RUB: импульс/пробой — сыграть по направлению."
    else:
        idea = f"{base}: тренд/пробой, объём >1.2x — в работу; иначе — от откатов."

    return (
        f"{head}\n"
        f"Почему сейчас: {ev.get('why_now','')}\n"
        f"Тикеры: {', '.join(secids)} | hotness {hot:.3f}\n"
        f"Влияние: Δ {_num(pct,2,'%')} · vol {_num(vr,2,'x')} · σ {_num(pa,1,'σ')}\n"
        f"Идея: {idea}"
    )
