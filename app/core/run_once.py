import sys, json, time
from app.storage.db import init_db
from app.core.pipeline import build_events
from app.core.postplay import channel_draft, trader_actions

if __name__=="__main__":
    t0=time.time()
    init_db()
    hours=int(sys.argv[1]) if len(sys.argv)>1 else 24
    k=int(sys.argv[2]) if len(sys.argv)>2 else 7
    evs=build_events(hours,k)
    t1=time.time()
    print(json.dumps({
        "latency_s": round(t1-t0,2),
        "count": len(evs),
        "events":[{
            "headline":e["headline"], "hotness":e["hotness"],
            "validity":e["validity"], "impact":e["impact"],
            "draft": channel_draft(e),
            "action": trader_actions(e),
            "sources": e["sources"]
        } for e in evs]
    }, ensure_ascii=False, indent=2))
