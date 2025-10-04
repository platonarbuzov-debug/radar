import re

# ----------------------------- Компании (RU) -----------------------------
COMPANY_MAP = {
    # Банки
    r"\bсбер\b|\bсбербанк\b|sber": ["SBER"],
    r"\bвтб\b|vtb": ["VTBR"],
    r"\bтинькофф\b|tinkoff|tcs": ["TCSG"],
    # Нефтегаз
    r"\bгазпром\b|gazprom": ["GAZP"],
    r"\bлукойл\b|lukoil": ["LKOH"],
    r"\bроснефть\b|rosneft": ["ROSN"],
    r"\bноватэк\b|novatek": ["NVTK"],
    r"\bсургутнефтегаз\b|сургут\b|surgut": ["SNGS"],
    # Металлы/ГМК
    r"\bнорникел\b|норильск\b|nornickel|norilsk": ["GMKN"],
    r"\bрусал\b|rusal": ["RUAL"],
    r"\bсевера?сталь\b|severstal": ["CHMF"],
    r"\bммк\b|magnitogorsk|mmk|magnitka": ["MAGN"],
    r"\bполюс\b|polyus": ["PLZL"],
    r"\bфосагро\b|phosagro": ["PHOR"],
    # Ритейл/потребители
    r"\bx5\b|х5|пятёроч|перекрёсток|x5 retail": ["FIVE"],
    r"\bмагнит\b|magnit": ["MGNT"],
    r"\bozon\b": ["OZON"],   # если в ленте есть
    r"\bwildberries\b|вб\b": [],  # нет тикера на MOEX — без метрик
    # Энергетика/сети
    r"\bинтер\s*рао\b|ir?ao": ["IRAO"],
    r"\bроссети\b|rosseti": ["RSTI"],
    r"\bмосэнерго\b|mosenergo": ["MSNG"],
    # Транспорт/аэро
    r"\bаэрофлот\b|aeroflot": ["AFLT"],
    r"\bсовкомфлот\b|совком\b|sovcomflot|scf": ["FLOT"],
    # IT/интернет
    r"\bяндекс\b|yandex": ["YNDX"],
    # Биржа
    r"\bмосбирж[аы]\b|\bмоex\b|moex|moex pjsc": ["MOEX"],
}

# ----------------------------- Макро/темы -----------------------------
TOPIC_MAP = [
    # ЦБ, ключевая ставка, инфляция — особенно влияет на FX и банки
    (["ключев", "ставк", "цб", "банк россии", "инфляц", "монетар", "рсо", "офтз", "офз"],
     ["USDRUB_TOM", "SBER"]),
    # Санкции/ограничения/SDN
    (["санкц", "sdn", "ofac", "запрет", "ограничен", "замороз", "эмбарго", "cap", "price cap"],
     ["USDRUB_TOM", "GAZP", "ROSN"]),
    # Нефть/газ/ОПЕК/трубопроводы
    (["нефть", "brent", "урал", "opec", "опек", "газ", "добыч", "квоты", "газопровод", "северный поток"],
     ["GAZP", "ROSN", "LKOH"]),
    # Валюта/курс/интервенции/платёжный баланс
    (["курс", "рубл", "доллар", "валют", "интервенц", "платежн", "платёжн", "счёт текущих операций"],
     ["USDRUB_TOM"]),
    # Дивиденды/байбэк/оферта/сплит/делистинг
    (["дивиден", "байбэк", "оферт", "выкуп", "split", "делист", "листинг", "реестр"],
     []),
    # Отчётность/guidance
    (["отчет", "отчёт", "выруч", "прибыл", "ebitda", "guidance", "prognoz", "прогноз"],
     []),
    # Геополитика → прокси через FX+нефтегаз только если явно затронуты море/транзит/санкции
    (["черномор", "балтик", "пролив", "танкер", "фрахт", "страхов", "транзит"], ["USDRUB_TOM", "GAZP"]),
]

# ----------------------------- Релевантность текста -----------------------------
MARKET_WORDS = [
    "акци", "облигац", "дивиден", "отчет", "отчёт", "прибыл", "выруч", "ставк",
    "курс", "рубл", "доллар", "санкц", "сделк", "оферт", "buyback", "guidance",
    "capex", "ipo", "листинг", "делист", "выкуп", "раскрыт", "квоты", "добыч", "нефть", "газ"
]

REL_MIN = 0.35  # порог отсечения «политшума» (кроме REG/EXCH)

def _find_by_regex(text: str, table: dict):
    t=(text or "").lower()
    secids=[]
    for pat, lst in table.items():
        if re.search(pat, t, flags=re.I):
            secids.extend(lst)
    # уникализировать, сохранить порядок
    seen=set(); out=[]
    for s in secids:
        if s and s not in seen:
            out.append(s); seen.add(s)
    return out

def company_secids(text: str):
    return _find_by_regex(text, COMPANY_MAP)

def infer_targets(text: str):
    t = (text or "").lower()
    for keys, secids in TOPIC_MAP:
        if any(k in t for k in keys):
            seen=set(); out=[]
            for s in secids:
                if s not in seen:
                    out.append(s); seen.add(s)
            return out
    return []

def relevance_score(text: str) -> float:
    t = (text or "").lower()
    hits = sum(1 for k in MARKET_WORDS if k in t)
    return min(1.0, hits/3.0)
