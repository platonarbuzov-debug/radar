from dataclasses import dataclass

# ---- Источники (группы: REG – регуляторы, EXCH – биржа, TIER1 – топ-СМИ) ----
@dataclass
class Source:
    name: str
    url: str
    kind: str = "rss"
    group: str = "TIER1"
    lang: str = "ru"
    weight: float = 0.8  # доверие источнику (0..1), идёт в cred_weight

# Под MOEX и российский рынок
SOURCES = [
    # Регулятор/биржа
    Source(name="CBR Press",   url="https://www.cbr.ru/rss/RssPress",   group="REG",  weight=1.00),
    Source(name="CBR Events",  url="https://www.cbr.ru/rss/eventrss",   group="REG",  weight=1.00),
    Source(name="MOEX News",   url="https://www.moex.com/export/news.aspx?cat=100", group="EXCH", weight=0.90),
    # Топ-СМИ
    Source(name="Interfax",    url="https://www.interfax.ru/rss.asp",   group="TIER1", weight=0.85),
    Source(name="RBC Finance", url="https://rssexport.rbc.ru/rbcnews/finance/20/full.rss", group="TIER1", weight=0.82),
    Source(name="RBC Companies", url="https://rssexport.rbc.ru/rbcnews/companies/20/full.rss", group="TIER1", weight=0.82),
    Source(name="Kommersant Finance", url="https://www.kommersant.ru/RSS/section-finance.xml", group="TIER1", weight=0.82),
]

TOP_K_DEFAULT = 7

# ---- Веса факторов горячести (используются в combine_logistic) ----
HOTNESS_WEIGHTS = {
    "recency":       0.80,   # свежесть
    "velocity":      0.75,   # скорость публикаций
    "credibility":   0.70,   # качество источников
    "confirmations": 0.60,   # разнородность подтверждений
    "breadth":       0.35,   # широта затронутых тикеров/секторов
    "price_move":    0.55,   # % ход цены
    "volume_ratio":  0.45,   # объём к среднему
    "price_anomaly": 0.50,   # z-score последнего бара
    "relevance":     0.40,   # рыночная релевантность текста (ключевые слова)
}
