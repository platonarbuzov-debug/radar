import datetime as dt
import statistics as st
import httpx
from httpx import HTTPError, RemoteProtocolError

HEADERS = {"User-Agent": "RadarBot/1.0 (+moex-iss; httpx)"}

# Алиасы «читаемых» кодов к реальным SECID на ISS для валют TOM
FX_ALIASES = {
    "USDRUB_TOM": "USD000UTSTOM",
    "EURRUB_TOM": "EUR_RUB__TOM",
    "CNYRUB_TOM": "CNY000UTSTOM",
}

def _fetch_json(url: str):
    # 3 попытки с экспоненциальной паузой; любые сетевые ошибки -> None
    delay = 0.6
    for _ in range(3):
        try:
            with httpx.Client(http2=True, headers=HEADERS, timeout=15) as c:
                r = c.get(url)
                r.raise_for_status()
                return r.json()
        except (HTTPError, RemoteProtocolError, Exception):
            import time
            time.sleep(delay)
            delay = min(delay * 2, 4.0)
    return None

def _candles(engine: str, market: str, secid: str, start_iso: str):
    url = f"https://iss.moex.com/iss/engines/{engine}/markets/{market}/securities/{secid}/candles.json?from={start_iso}&interval=60"
    js = _fetch_json(url)
    if not js or "candles" not in js or not js["candles"]["data"]:
        return [], []
    cols = js["candles"]["columns"]; data = js["candles"]["data"]
    i_close = cols.index("close"); i_vol = cols.index("volume")
    closes = [r[i_close] for r in data if r[i_close] is not None]
    vols   = [r[i_vol]   for r in data if r[i_vol]   is not None]
    return closes, vols

def _detect_engine_market(secid: str):
    """
    Возвращает ((engine, market), real_secid).
    Для валют подменяем читаемые алиасы на реальные SECID ISS.
    """
    s = (secid or "").upper()
    # Подменяем алиасы на реальные SECID для валют
    if s in FX_ALIASES:
        return ("currency", "selt"), FX_ALIASES[s]
    # Валютные инструменты на MOEX ISS обычно имеют '...TOM' или '000...'
    if s.endswith("_TOM") or s.endswith("TOM") or "000" in s:
        return ("currency", "selt"), s
    # По умолчанию — акции
    return ("stock", "shares"), s

def price_impact_metrics(secid: str, window_hours: int, now_ts: int):
    """
    Возвращает (pct_move, volume_ratio, price_anomaly) или (None, None, None) при недоступности данных.
    """
    try:
        if not secid:
            return None, None, None
        (engine, market), secid_real = _detect_engine_market(secid)
        start   = dt.datetime.utcfromtimestamp(now_ts - window_hours*3600).date().isoformat()
        start30 = (dt.datetime.utcfromtimestamp(now_ts) - dt.timedelta(days=30)).date().isoformat()

        closes30, vols30 = _candles(engine, market, secid_real, start30)
        closesW,  volsW  = _candles(engine, market, secid_real, start)
        if len(closes30) < 3 or len(closesW) < 2:
            return None, None, None

        # % изменение цены за окно
        pct_move = (closesW[-1]-closesW[0]) / closesW[0] * 100.0

        # Отношение объёма за окно к среднему почасовому за ~30д
        vol_window = sum(volsW) if volsW else 0
        vol_mean30 = (sum(vols30)/len(vols30)) if vols30 else 0
        volume_ratio = (vol_window / vol_mean30) if vol_mean30 else None

        # Аномалия последнего часового шага (z-score по 30д)
        rets30 = [((b-a)/a*100.0) for a,b in zip(closes30[:-1], closes30[1:]) if a]
        last_ret = ((closesW[-1]-closesW[-2])/closesW[-2]*100.0) if closesW[-2] else 0
        if len(rets30) >= 10:
            mu = st.mean(rets30); sd = st.pstdev(rets30) or 1e-6
            price_anomaly = abs((last_ret - mu)/sd)
        else:
            price_anomaly = None

        return pct_move, volume_ratio, price_anomaly
    except Exception:
        return None, None, None
