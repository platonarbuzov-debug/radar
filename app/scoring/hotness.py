import math, time

def recency_score(max_ts, now=None, half_life_h=6.0):
    now = now or time.time()
    age_h = max(0.0, (now - max_ts)/3600.0)
    return math.exp(-math.log(2)*age_h/half_life_h)  # 1.0 → 0.5 каждые half_life_h

def velocity_score(timestamps, now=None):
    now=now or time.time()
    per_hour={}
    for t in timestamps:
        h=int((now-t)//3600)
        per_hour[h]=per_hour.get(h,0)+1
    latest=sum(per_hour.get(h,0) for h in [0,1,2])  # последние 3 часа
    return min(1.0, latest/6.0)

def credibility_score(weights):
    top3=sorted(weights, reverse=True)[:3]
    return min(1.0, sum(top3)/3.0)

def confirmations_score(groups):
    kinds=set(groups)  # REG/EXCH/TIER1/MEDIA
    return min(1.0, len(kinds)/3.0)

def breadth_score(secids):
    return min(1.0, len(set(secids))/4.0)

def norm_clip(x, lo, hi):
    if x is None: return 0.0
    return max(0.0, min(1.0, (x-lo)/(hi-lo)))

def logistic(z):  # стабильный 0..1
    return 1.0/(1.0+math.exp(-z))

def combine_logistic(weights, feats):
    # линейная модель → логистическая калибровка
    z=0.0
    for k,w in weights.items():
        z += w * feats.get(k,0.0)
    # масштабируем (эмпирически): делим на 2.5 для мягкости
    return round(logistic(z/2.5), 3)
