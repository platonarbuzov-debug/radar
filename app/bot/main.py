import os, time, asyncio, logging, html
from urllib.parse import urlparse
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from dotenv import load_dotenv, find_dotenv

from app.storage.db import init_db
from app.core.pipeline import build_events
from app.core.postplay import channel_draft, trader_actions

load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)

TOKEN=os.getenv("TG_BOT_TOKEN")
if not TOKEN: raise RuntimeError("Нет TG_BOT_TOKEN в .env")

bot=Bot(token=TOKEN)
dp=Dispatcher()
user_semaphores = {}
user_params = {}  # uid -> {hours,k,last_cmd}

def kb_main():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Горячее (24ч)"), KeyboardButton(text="📰 Черновики 24ч")],
            [KeyboardButton(text="📈 Трейд"), KeyboardButton(text="⚙️ Окно/TopK")],
            [KeyboardButton(text="🔁 Обновить"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )

def get_params(uid):
    p=user_params.get(uid) or {"hours":24,"k":7,"last_cmd":"hot"}
    user_params[uid]=p
    return p

async def safe_build(hours,k):
    try: return build_events(hours, max(k,5))
    except Exception as e:
        logging.exception("Pipeline error: %s", e)
        return []

def links_kb(ev):
    # Дедуп по доменам, чтобы не было «Interfax/Интерфакс» дважды
    seen=set(); buttons=[]
    for s in ev['sources']:
        url=s['url']; dom=urlparse(url).netloc.lower()
        if dom in seen: 
            continue
        seen.add(dom)
        label=s['source'][:28]
        buttons.append([InlineKeyboardButton(text=label, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def split_msg(text:str, maxlen:int=3500):
    parts=[]; cur=""
    for line in text.splitlines(True):
        if len(cur)+len(line)>maxlen: parts.append(cur); cur=line
        else: cur+=line
    if cur: parts.append(cur)
    return parts

def fmt_tspan(ev):
    t0 = ev.get('t0') or ev['timeline'][0]['t']
    t1 = ev.get('t1') or ev['timeline'][-1]['t']
    if abs(t1 - t0) < 1800:
        return time.strftime('%d.%m %H:%M', time.localtime(t0))
    return f"{time.strftime('%d.%m %H:%M', time.localtime(t0))} → {time.strftime('%d.%m %H:%M', time.localtime(t1))}"

def fmt_imp(imp):
    pct=imp.get("pct_move"); vr=imp.get("volume_ratio"); pa=imp.get("price_anomaly")
    pct_str = f"{pct:+.2f}%" if isinstance(pct,(int,float)) else "n/a"
    vr_str  = f"{vr:.2f}x"  if isinstance(vr,(int,float))  else "n/a"
    pa_str  = f"{pa:.1f}σ"  if isinstance(pa,(int,float))  else "n/a"
    return pct_str, vr_str, pa_str

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "RADAR: горячие сюжеты по рынку, их влияние и быстрая выжимка действий.",
        reply_markup=kb_main()
    )

@dp.message(F.text == "❓ Помощь")
async def help_msg(m:Message):
    await m.answer(
        "• 🔥 Горячее (24ч) — подробные карточки (таймлайн, метрики, ссылки).\n"
        "• 📰 Черновики 24ч — строки для канала (цитата и действия).\n"
        "• 📈 Трейд — чёткие действия трейдера.\n"
        "• ⚙️ Окно/TopK — пресеты.\n"
        "• 🔁 Обновить — повтор последней команды.",
        reply_markup=kb_main()
    )

async def handle(m:Message, mode:str):
    uid=m.from_user.id
    sem=user_semaphores.setdefault(uid, asyncio.Semaphore(1))
    async with sem:
        p=get_params(uid); hours=p["hours"]; k=max(p["k"],5); p["last_cmd"]=mode
        wait=await m.answer("Ищу события…")
        evs=await safe_build(hours,k)
        await wait.delete()
        if not evs:
            await m.answer("В окне пусто или всё шум.")
            return

        if mode=="hot":
            for i,ev in enumerate(evs,1):
                pct_str, vr_str, pa_str = fmt_imp(ev.get("impact", {}))
                head=(f"<b>TOP {i} — {html.escape(ev['headline'])}</b>\n"
                      f"hotness: <b>{ev['hotness']:.3f}</b> · валидн.: <b>{ev.get('validity',0):.2f}</b>\n"
                      f"Δ {pct_str} · vol {vr_str} · σ {pa_str}\n"
                      f"<i>Почему сейчас:</i> {html.escape(ev['why_now'])}\n"
                      f"<i>Время:</i> {fmt_tspan(ev)}\n"
                      f"<i>Тикеры:</i> {html.escape(', '.join(ev['secids'] or ['—']))}")
                await m.answer(head, parse_mode="HTML", reply_markup=links_kb(ev))
        elif mode=="drafts":
            lines=[f"{i}. {html.escape(channel_draft(ev))}" for i,ev in enumerate(evs,1)]
            for part in split_msg("\n\n".join(lines)):
                await m.answer(part, parse_mode="HTML")
        elif mode=="bablo":
            out=[]; seen=set()
            for ev in evs:
                sec = (ev['secids'][0] if ev['secids'] else "—")
                imp = ev.get("impact",{})
                pct = imp.get("pct_move"); vr  = imp.get("volume_ratio")
                strong = (isinstance(pct,(int,float)) and abs(pct)>=1.0) and (isinstance(vr,(int,float)) and vr>=1.2)
                if not strong or sec in seen: 
                    continue
                seen.add(sec)
                out.append("• " + html.escape(trader_actions(ev)))
                if len(out)>=10: break
            if not out:
                out=["• " + html.escape(trader_actions(ev)) for ev in evs[:5]]
            await m.answer("\n".join(out), parse_mode="HTML")

@dp.message(F.text == "🔥 Горячее (24ч)")
async def hot(m:Message):
    p=get_params(m.from_user.id); p["hours"]=24; p["k"]=8
    await handle(m, "hot")

@dp.message(F.text == "📰 Черновики 24ч")
async def drafts(m:Message):
    p=get_params(m.from_user.id); p["hours"]=24; p["k"]=8
    await handle(m, "drafts")

@dp.message(F.text == "📈 Трейд")
async def trade(m:Message):
    await handle(m, "bablo")

@dp.message(F.text == "🔁 Обновить")
async def refresh(m:Message):
    p=get_params(m.from_user.id)
    await handle(m, p["last_cmd"])

@dp.message(F.text == "⚙️ Окно/TopK")
async def set_params(m:Message):
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="6ч / Top6", callback_data="set:6:6"),
         InlineKeyboardButton(text="24ч / Top8", callback_data="set:24:8"),
         InlineKeyboardButton(text="48ч / Top10", callback_data="set:48:10")]
    ])
    await m.answer("Выберите окно / TopK:", reply_markup=kb)

@dp.callback_query(F.data.startswith("set:"))
async def cb_set(cq):
    _,h,k=cq.data.split(":")
    p=get_params(cq.from_user.id)
    p["hours"]=int(h); p["k"]=int(k)
    await cq.message.edit_text(f"Параметры сохранены: {h}ч / Top{k}.")
    await cq.answer("Ок")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio
    asyncio.run(main())
