"""
Telegram bot: hisobni ulash, muddat eslatmalari, haftalik dayjest, savollarni guruhga yuborish.

Sozlash (muhit o'zgaruvchilari):
  TELEGRAM_BOT_TOKEN   — @BotFather bergan token (bo'lmasa bot o'chiq turadi)
  TELEGRAM_GROUP_ID    — (ixtiyoriy) yangi savollar yuboriladigan guruh chat ID si, masalan -1001234567890
  TELEGRAM_GROUP_LINK  — (ixtiyoriy) saytda ko'rsatiladigan guruh havolasi, masalan https://t.me/yoshlarhub_chat
  SITE_URL             — (ixtiyoriy) xabarlardagi havolalar uchun sayt manzili
"""
import json
import os
import threading
import time
from datetime import timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "").strip()
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
_username = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
_started = False


def enabled():
    return bool(TOKEN)


def _api(method, payload=None, timeout=35):
    data = json.dumps(payload or {}).encode()
    req = Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def send(chat_id, text):
    if not TOKEN or not chat_id:
        return False
    try:
        _api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                             "disable_web_page_preview": True}, timeout=15)
        return True
    except Exception:
        return False


def bot_username():
    global _username
    if _username or not TOKEN:
        return _username
    try:
        _username = _api("getMe", timeout=10)["result"]["username"]
    except Exception:
        pass
    return _username


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _link(path):
    return f"{SITE_URL}{path}" if SITE_URL else ""


def post_question_to_group(title, channel, url):
    if GROUP_ID:
        send(GROUP_ID, f"❓ <b>Yangi savol</b> #{channel.replace('-', '_')}\n{_esc(title)}\n{url}")


# ------------------------------------------------------------------ fon oqimlari
def _poll_updates(db_connect):
    """/start <kod> — foydalanuvchini sayt hisobiga bog'laydi."""
    offset = 0
    while True:
        try:
            res = _api("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message"]})
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                text = (msg.get("text") or "").strip()
                chat = msg.get("chat", {})
                if chat.get("type") != "private":
                    continue
                if text.startswith("/start"):
                    code = text.split(maxsplit=1)[1] if " " in text else ""
                    conn = db_connect()
                    try:
                        u = conn.execute("SELECT id, name FROM users WHERE tg_code=? AND tg_code!=''", (code,)).fetchone()
                        if u:
                            conn.execute("UPDATE users SET tg_chat_id=?, tg_code='' WHERE id=?", (str(chat["id"]), u["id"]))
                            try:
                                import features
                                features.award(conn, u["id"], "telegram", "first")
                            except Exception:
                                pass
                            conn.commit()
                            send(chat["id"], f"✅ Salom, {_esc(u['name'] or 'do‘stim')}! Hisobingiz ulandi.\n\n"
                                             "Endi muddat yaqinlashganda eslatma va har dushanba sizga mos yangi imkoniyatlarni yuboraman.")
                        else:
                            send(chat["id"], "👋 Salom! Hisobingizni ulash uchun saytda <b>Profil → Telegram</b> bo‘limidagi tugmani bosing.")
                    finally:
                        conn.close()
        except Exception:
            time.sleep(10)


def _reminders_and_digest(db_connect):
    import features
    import sources
    while True:
        try:
            conn = db_connect()
            try:
                today = features.today()
                rows = conn.execute("""SELECT a.user_id, a.opp_id, a.deadline adl, a.reminded, o.deadline odl, o.title, u.tg_chat_id
                                       FROM applications a JOIN opportunities o ON o.id=a.opp_id JOIN users u ON u.id=a.user_id
                                       WHERE a.status IN ('saved','preparing') AND u.tg_chat_id!='' AND u.reminders_on=1""").fetchall()
                for r in rows:
                    d = features.parse_day(r["adl"]) or features.parse_day(r["odl"])
                    if not d:
                        continue
                    left = (d - today).days
                    for mark, when in (("3", 3), ("1", 1)):
                        if left == when and mark not in r["reminded"]:
                            word = "3 kun" if when == 3 else "ertaga"
                            ok = send(r["tg_chat_id"],
                                      f"⏳ <b>{_esc(r['title'][:120])}</b>\nMuddat {word} tugaydi ({features.fmt_day(d)}).\n"
                                      f"Hujjatlaringizni tekshiring va arizani topshiring!\n{_link(f'/opportunity/{r[1]}')}")
                            if ok:
                                conn.execute("UPDATE applications SET reminded=reminded||? WHERE user_id=? AND opp_id=?",
                                             (mark, r["user_id"], r["opp_id"]))
                conn.commit()

                # Haftalik dayjest: dushanba, Toshkent vaqti bilan 9:00 dan keyin, haftada bir marta
                now_tk = sources.now_utc() + timedelta(hours=5)
                week_key = now_tk.strftime("%G-W%V")
                last = conn.execute("SELECT value FROM meta WHERE key='digest_week'").fetchone()
                if now_tk.weekday() == 0 and now_tk.hour >= 9 and (not last or last["value"] != week_key):
                    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('digest_week', ?)", (week_key,))
                    conn.commit()
                    week_ago = sources.fmt_ts(sources.now_utc() - timedelta(days=7))
                    opps = conn.execute("SELECT * FROM opportunities WHERE published >= ? ORDER BY published DESC LIMIT 300",
                                        (week_ago,)).fetchall()
                    for u in conn.execute("SELECT * FROM users WHERE tg_chat_id!='' AND digest_on=1").fetchall():
                        scored = sorted(((features.match_score(u, o)[0] or 0, o) for o in opps), key=lambda x: -x[0])[:5]
                        if not scored:
                            continue
                        lines = [f"{i+1}. {_esc(o['title'][:90])} — <b>{m}% mos</b>\n{_link(f'/opportunity/{o[0]}')}"
                                 for i, (m, o) in enumerate(scored)]
                        send(u["tg_chat_id"], "📬 <b>Bu haftaning sizga mos 5 ta imkoniyati</b>\n\n" + "\n\n".join(lines))
            finally:
                conn.close()
        except Exception:
            pass
        time.sleep(30 * 60)


def start(db_connect):
    global _started
    if _started or not TOKEN:
        return
    _started = True
    threading.Thread(target=_poll_updates, args=(db_connect,), daemon=True).start()
    threading.Thread(target=_reminders_and_digest, args=(db_connect,), daemon=True).start()
