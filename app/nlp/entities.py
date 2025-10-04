import re
from typing import List
from app.nlp.topics import COMPANY_MAP  # используем те же синонимы, что и в topics

# Белый список ликвидных тикеров MOEX (для фильтра UPPERCASE-слов)
KNOWN_TICKERS = {
    # Банки
    "SBER","VTBR","TCSG",
    # Нефтегаз
    "GAZP","LKOH","ROSN","NVTK","SNGS",
    # Металлы/химия
    "GMKN","RUAL","CHMF","MAGN","PLZL","PHOR","POLY",
    # Потребители/ритейл
    "FIVE","MGNT","OZON","DSKY","ALRS",
    # Энергетика/сети
    "IRAO","RSTI","MSNG","FEES","HYDR",
    # Транспорт/логистика
    "AFLT","FLOT","NMTP","RASP",
    # Телеком/IT
    "MTSS","YNDX","MAIL","MOEX",
}

UPPER_RE = re.compile(r"\b[A-Z]{3,6}\b")

def _uniq_keep_order(items: List[str]) -> List[str]:
    seen=set(); out=[]
    for x in items:
        if x and x not in seen:
            out.append(x); seen.add(x)
    return out

def extract_secids(text: str) -> List[str]:
    """
    Возвращает список SECID для карточки события:
    1) по синонимам компаний (COMPANY_MAP из topics),
    2) по UPPERCASE-тикерам, встреченным в тексте (пересечение с KNOWN_TICKERS).
    """
    t = (text or "")
    low = t.lower()

    # 1) По синонимам компаний
    secids = []
    for pat, lst in COMPANY_MAP.items():
        if re.search(pat, low, flags=re.I):
            secids.extend(lst)

    # 2) Явные UPPERCASE-тикеры
    for token in UPPER_RE.findall(t):
        if token in KNOWN_TICKERS and token not in secids:
            secids.append(token)

    # Оставляем максимум 4 тикера для читабельности
    return _uniq_keep_order(secids)[:4]
