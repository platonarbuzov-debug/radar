import os, sys, time
import streamlit as st

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from app.core.pipeline import build_events

st.set_page_config(page_title="RADAR — горячие события", layout="wide")
st.title("RADAR — горячие события")

hours = st.sidebar.number_input("Окно, часов", 1, 72, 24)
k = st.sidebar.number_input("Top-K", 1, 20, 7)

if st.button("Обновить"):
    st.session_state["events"]=build_events(hours,k)

evs=st.session_state.get("events", [])
if not evs:
    st.info("Нажмите «Обновить».")
else:
    for ev in evs:
        with st.container(border=True):
            st.subheader(f"🔥 {ev['headline']} — hotness {ev['hotness']} (валидн. {ev['validity']:.2f})")
            c1,c2=st.columns([2,1])
            with c1:
                st.markdown(f"**Почему сейчас:** {ev['why_now']}")
                st.markdown("**Ссылки:**")
                for s in ev["sources"]:
                    st.markdown(f"- [{s['source']}]({s['url']})")
                st.markdown("**Черновик (для канала):**")
                t0=time.strftime('%d.%m %H:%M', time.localtime(ev['timeline'][0]['t']))
                st.code(f"[{ev['secids'][0] if ev['secids'] else '—'}] {ev['headline']} | "
                        f"Δ {ev['impact']['pct_move'] if ev['impact']['pct_move'] is not None else 'n/a'}%, "
                        f"vol {ev['impact']['volume_ratio'] if ev['impact']['volume_ratio'] is not None else 'n/a'}x, "
                        f"σ {ev['impact']['price_anomaly'] if ev['impact']['price_anomaly'] is not None else 'n/a'} | "
                        f"hotness {ev['hotness']} | валидн. {ev['validity']:.2f} | с {t0}")
            with c2:
                t0=time.strftime('%d.%m %H:%M', time.localtime(ev['timeline'][0]['t']))
                t1=time.strftime('%d.%m %H:%M', time.localtime(ev['timeline'][-1]['t']))
                st.markdown(f"**Таймлайн:** {t0} → {t1}")
                st.markdown(f"**Тикеры:** {', '.join(ev['secids'] or ['—'])}")
                imp=ev["impact"]
                st.metric("Δ%", f"{(imp['pct_move'] or 0):+.2f}%")
                st.metric("Объём", f"{(imp['volume_ratio'] or 0):.2f}x")
                st.metric("Аномалия", f"{(imp['price_anomaly'] or 0):.1f}σ")
