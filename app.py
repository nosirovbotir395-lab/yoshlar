"""
Yoshlar Hub — veb versiya (Flask + SQLite).

Ishga tushirish (kompyuterda):   python app.py
Serverda:                        gunicorn app:app --workers 2 --bind 0.0.0.0:8000
"""
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import features
import synonyms
import sources
import telegram_bot

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "yoshlar.db"))
REFRESH_MINUTES = int(os.environ.get("REFRESH_MINUTES", "30"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
PER_PAGE = 20

CATEGORIES = ["Grantlar", "Ish va internship", "Tanlovlar",
              "Kurslar", "Volunteer", "Tadbirlar"]
# Saralash bo'limidagi tayyor so'z tugmalari.
#   terms   — natijada shu so'zlardan biri bo'lishi shart (mavzuga moslik tekshiruvi)
#   google  — Google News'ga yuboriladigan so'rovlar: (so'rov, til). {year} joriy yil bilan almashadi
#   default — kategoriya avtomatik aniqlanmasa qo'yiladigan (kategoriya, tur)
#   web     — SearXNG (ixtiyoriy) uchun inglizcha so'rov
def _topic(key, label, icon, terms, google, default, web):
    return {"key": key, "label": label, "icon": icon, "terms": terms,
            "google": google, "default": default, "web": web}


TOPICS = [
    _topic("startap", "Startap", "🚀",
           ["startup", "startap", "akselerator", "accelerator", "inkubator", "incubator", "venture", "pitch"],
           [("startap tanlov yoshlar {year}", "uz"), ("startap akselerator grant", "uz"),
            ("Uzbekistan startup competition {year}", "en"), ("Uzbekistan startup accelerator program", "en")],
           ("Tanlovlar", "Startap tanlovi"), "startup accelerator youth"),
    _topic("grant", "Grant", "🎓",
           ["grant", "stipend", "scholarship", "funding", "fellowship", "moliyalashtir"],
           [("yoshlar uchun grant {year}", "uz"), ("talabalar stipendiya {year}", "uz"),
            ("Uzbekistan grant youth {year}", "en"), ("scholarship Uzbekistan students {year}", "en")],
           ("Grantlar", "Grant"), "grant scholarship youth"),
    _topic("it", "IT", "💻",
           [" it ", "it-", "it park", "dasturlash", "dasturchi", "software", "programming", "developer",
            "digital", "raqamli", " ai ", "sun'iy intellekt", "artificial intelligence", "frontend", "backend", "kiber"],
           [("IT kurs yoshlar {year}", "uz"), ("IT Park tanlov {year}", "uz"), ("dasturchi vakansiya", "uz"),
            ("Uzbekistan IT Park program {year}", "en"), ("Uzbekistan IT courses youth", "en")],
           ("Kurslar", "IT"), "IT programming youth"),
    _topic("hackathon", "Hackathon", "🏆",
           ["hackathon", "hakaton", "xakaton", "challenge", "competition", "olimpiada"],
           [("hakaton {year}", "uz"), ("Uzbekistan hackathon {year}", "en"), ("Central Asia hackathon {year}", "en")],
           ("Tanlovlar", "Hackathon"), "hackathon youth"),
    _topic("internship", "Internship", "🧑‍💼",
           ["intern", "amaliyot", "stajirovka", "стажировк", "trainee"],
           [("talabalar amaliyot {year}", "uz"), ("stajirovka yoshlar {year}", "uz"),
            ("Uzbekistan internship students {year}", "en")],
           ("Ish va internship", "Internship"), "internship students"),
    _topic("ish", "Ish o‘rinlari", "💼",
           ["vacanc", "vakansiya", "вакансия", " job", "career", "ish o'rin", "bo'sh ish", "ishga qabul", " hiring", "ish bilan ta'min"],
           [("bo'sh ish o'rinlari yoshlar", "uz"), ("vakansiya Toshkent", "uz"), ("ishga qabul e'lon", "uz"),
            ("Uzbekistan jobs young specialists", "en")],
           ("Ish va internship", "Vakansiya"), "jobs vacancy young graduates"),
    _topic("biznes", "Biznes", "📈",
           ["business", "biznes", "tadbirkor", "entrepreneur", "kredit", "subsidiya"],
           [("yosh tadbirkorlar dastur {year}", "uz"), ("biznes grant yoshlar", "uz"),
            ("Uzbekistan young entrepreneurs program", "en")],
           ("Grantlar", "Biznes"), "business youth program"),
    _topic("marketing", "Marketing", "📣",
           ["marketing", " smm", "brand", "reklama"],
           [("marketing kurs {year}", "uz"), ("SMM kurs bepul", "uz"),
            ("Uzbekistan digital marketing training", "en")],
           ("Kurslar", "Marketing"), "marketing youth program"),
    _topic("logistika", "Logistika", "🚚",
           ["logistic", "logistika", "supply chain", "transport"],
           [("logistika kurs yoshlar", "uz"), ("logistika vakansiya", "uz"),
            ("Uzbekistan logistics training program", "en")],
           ("Kurslar", "Logistika"), "logistics youth program"),
    _topic("til", "Til / IELTS", "🗣️",
           ["ielts", "english", "ingliz", "language", "til kurs", "chet tili", "toefl", "cefr"],
           [("ingliz tili bepul kurs", "uz"), ("IELTS bepul yoshlar", "uz"),
            ("Uzbekistan free English course IELTS", "en")],
           ("Kurslar", "Til kursi"), "English language IELTS free course"),
    _topic("talaba", "Talabalar", "🎒",
           ["student", "talaba", "universit", "oliygoh", "magistr", "bakalavr"],
           [("talabalar uchun tanlov {year}", "uz"), ("talabalar grant {year}", "uz"),
            ("Uzbekistan students opportunities {year}", "en")],
           ("Tanlovlar", "Talabalar uchun"), "students program"),
    _topic("volunteer", "Volunteer", "🤝",
           ["volunteer", "volontyor", "volonter", "ko'ngilli", "волонт"],
           [("volontyorlik yoshlar {year}", "uz"), ("ko'ngillilar loyiha", "uz"),
            ("Uzbekistan youth volunteer", "en")],
           ("Volunteer", "Volunteer"), "volunteer youth"),
]
TOPIC_MAP = {t["key"]: t for t in TOPICS}

CATEGORY_CLASS = {
    "Grantlar": "grant", "Ish va internship": "job", "Tanlovlar": "contest",
    "Kurslar": "course", "Volunteer": "volunteer", "Tadbirlar": "event",
}
CATEGORY_ICON = {
    "Grantlar": "₲", "Ish va internship": "↗", "Tanlovlar": "★",
    "Kurslar": "▣", "Volunteer": "♥", "Tadbirlar": "◷",
}

CATEGORY_EMOJI = {
    "Grantlar": "🎓", "Ish va internship": "💼", "Tanlovlar": "🏆",
    "Kurslar": "📚", "Volunteer": "🤝", "Tadbirlar": "📅",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Foydalanuvchi topilmaganda ham vaqt sarflash uchun (login vaqtini tenglashtirish).
DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


# ============================================================
# MA'LUMOTLAR BAZASI
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    university TEXT NOT NULL DEFAULT '',
    major TEXT NOT NULL DEFAULT '',
    course TEXT NOT NULL DEFAULT '',
    region TEXT NOT NULL DEFAULT '',
    interest TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT '',
    deadline TEXT NOT NULL DEFAULT '',
    fields TEXT NOT NULL DEFAULT '[]',
    link TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT '',
    published TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_opp_published ON opportunities(published DESC);
CREATE INDEX IF NOT EXISTS idx_opp_category ON opportunities(category);
CREATE TABLE IF NOT EXISTS saved (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opp_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, opp_id)
);
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_db():
    if "db" not in g:
        g.db = db_connect()
    return g.db


def search_text_for(item):
    return sources._norm(" ".join([
        item.get("title", ""), item.get("description", ""),
        " ".join(item.get("fields", [])), item.get("category", ""),
        item.get("location", ""), item.get("type", ""),
    ]))


def insert_opportunity(conn, item, pinned=0):
    """Yangi yozuv qo'shadi. Havola yoki sarlavha takrorlansa qo'shmaydi. True/False qaytaradi."""
    link = item["link"].strip()
    if not link.startswith(("http://", "https://")):
        return False
    tkey = sources._title_key(item["title"])
    dup = conn.execute(
        "SELECT 1 FROM opportunities WHERE link = ? OR (title_key = ? AND title_key != '')",
        (link, tkey),
    ).fetchone()
    if dup:
        return False
    try:
        conn.execute(
            """INSERT INTO opportunities
               (id, title, title_key, category, location, type, deadline, fields,
                link, source, published, description, search_text, pinned, lang)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item.get("id") or sources._make_id(item["title"], link),
             item["title"][:180], tkey, item["category"], item.get("location", ""),
             item.get("type", ""), item.get("deadline", ""),
             json.dumps(item.get("fields", []), ensure_ascii=False),
             link, item.get("source", ""), item.get("published", ""),
             item.get("description", "")[:500], search_text_for(item), pinned,
             sources.lang_rank(item["title"] + " " + item.get("description", ""))),
        )
    except sqlite3.IntegrityError:
        return False  # ID yoki havola to'qnashuvi: bitta yozuv butun yangilashni buzmasin
    return True


def init_db():
    conn = db_connect()
    try:
        conn.executescript(SCHEMA)
        features.migrate(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(opportunities)")}
        if "lang" not in cols:
            conn.execute("ALTER TABLE opportunities ADD COLUMN lang INTEGER NOT NULL DEFAULT 1")
            for r in conn.execute("SELECT id, title, description FROM opportunities").fetchall():
                conn.execute("UPDATE opportunities SET lang=? WHERE id=?",
                             (sources.lang_rank(r["title"] + " " + r["description"]), r["id"]))
        # imkoniyat belgisi bo'lmagan oddiy yangiliklarni tozalash (saqlanganlar va rasmiylar qoladi)
        for r in conn.execute("""SELECT id, search_text FROM opportunities WHERE pinned=0
                                 AND id NOT IN (SELECT opp_id FROM saved)
                                 AND id NOT IN (SELECT opp_id FROM applications)""").fetchall():
            if sources.classify(r["search_text"]) is None:
                conn.execute("DELETE FROM opportunities WHERE id=?", (r["id"],))
        for src in sources.OFFICIAL_SOURCES:
            insert_opportunity(conn, src, pinned=1)
        conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('last_refresh', '0')")
        conn.commit()
    finally:
        conn.close()


# ============================================================
# AVTOMATIK YANGILASH (fon oqimida)
# ============================================================

_refresh_lock = threading.Lock()


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, str(value)))


def get_meta(conn, key, default=""):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def cleanup(conn):
    """Eskirgan va muddati o'tgan (saqlanmagan, pinned bo'lmagan) yozuvlarni o'chiradi."""
    cutoff = (sources.now_utc() - timedelta(days=sources.MAX_AGE_DAYS)).strftime("%Y-%m-%d %H:%M")
    today = sources.now_utc().strftime("%Y-%m-%d")
    conn.execute(
        """DELETE FROM opportunities WHERE pinned = 0
           AND id NOT IN (SELECT opp_id FROM saved)
           AND ((published != '' AND published < ?)
                OR (deadline GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND deadline < ?))""",
        (cutoff, today),
    )


def refresh_now(force=False):
    """
    Internetdan yangi imkoniyatlarni olib bazaga qo'shadi.
    Bir nechta worker bo'lsa ham, `meta.last_refresh` orqali faqat bittasi ishlaydi.
    """
    if not _refresh_lock.acquire(blocking=False):
        return None
    conn = db_connect()
    try:
        now = time.time()
        if force:
            set_meta(conn, "last_refresh", now)
            conn.commit()
        else:
            cur = conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'last_refresh' AND CAST(value AS REAL) < ?",
                (str(now), now - REFRESH_MINUTES * 60 + 5),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None  # boshqa worker yaqinda yangilagan

        sources.USER_FEEDS[:] = [(r["name"], r["url"])
                                 for r in conn.execute("SELECT name, url FROM feeds")]
        interests = [r["interest"] for r in conn.execute(
            """SELECT interest, COUNT(*) c FROM users WHERE interest != ''
               GROUP BY interest ORDER BY c DESC LIMIT 2""")]

        found, ok_total, total = [], 0, 0
        for interest in [""] + interests:
            items, ok, tot = sources.fetch_real_opportunities(interest)
            found += items
            ok_total += ok
            total += tot

        added = 0
        if ok_total:
            cutoff = (sources.now_utc() - timedelta(days=sources.MAX_AGE_DAYS)).strftime("%Y-%m-%d %H:%M")
            for item in found:
                if item.get("published", "") and item["published"] < cutoff:
                    continue  # allaqachon eskirgan natijani qo'shmaymiz
                if insert_opportunity(conn, item):
                    added += 1
            cleanup(conn)

        set_meta(conn, "last_ok", f"{ok_total}/{total}")
        set_meta(conn, "last_added", added)
        set_meta(conn, "last_status_time", sources.fmt_ts(sources.now_utc()))
        conn.commit()
        return added
    except Exception as exc:  # fon oqimi hech qachon serverni yiqitmasin
        try:
            set_meta(conn, "last_error", str(exc)[:200])
            conn.commit()
        except Exception:
            pass
        return None
    finally:
        conn.close()
        _refresh_lock.release()


def scheduler_loop():
    time.sleep(5)
    while True:
        refresh_now()
        time.sleep(60)  # har daqiqada tekshiradi; haqiqiy yangilash REFRESH_MINUTES da bir marta


# ============================================================
# ILOVA YARATISH
# ============================================================

def load_secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=load_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # HTTPS da ishlatganda: SESSION_COOKIE_SECURE=1
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,  # hujjat yuklash uchun 6 MB
    )
    init_db()
    register_hooks(app)
    register_routes(app)
    features.register(app, SimpleNamespace(
        get_db=get_db, login_required=login_required, clean=clean, safe_next=safe_next,
        row_to_item=row_to_item, user_saved_ids=user_saved_ids, TOPIC_MAP=TOPIC_MAP))
    if os.environ.get("DISABLE_SCHEDULER") != "1":
        threading.Thread(target=scheduler_loop, daemon=True).start()
        telegram_bot.start(db_connect)
    return app


# ============================================================
# YORDAMCHILAR
# ============================================================

_login_fails = {}  # (ip, email) -> [vaqtlar]  (oddiy brute-force himoyasi)
MAX_FAILS, FAIL_WINDOW = 5, 15 * 60


def too_many_fails(key):
    now = time.time()
    _login_fails[key] = [t for t in _login_fails.get(key, []) if now - t < FAIL_WINDOW]
    return len(_login_fails[key]) >= MAX_FAILS


def safe_next(target):
    """Faqat sayt ichidagi yo'lga qaytarishga ruxsat (open-redirect himoyasi)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("index")


def clean(value, limit):
    return (value or "").strip()[:limit]


def is_admin():
    return bool(g.user and ADMIN_EMAIL and g.user["email"] == ADMIN_EMAIL)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Avval tizimga kiring.", "info")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def row_to_item(row, saved_ids=frozenset()):
    item = dict(row)
    try:
        item["fields"] = json.loads(item.get("fields") or "[]")
    except ValueError:
        item["fields"] = []
    item["saved"] = item["id"] in saved_ids
    pub = sources.parse_ts(item.get("published", ""))
    item["is_new"] = bool(pub and len(item["published"]) > 10
                          and sources.now_utc() - pub < timedelta(hours=24))
    return item


def user_saved_ids():
    if not g.user:
        return frozenset()
    rows = get_db().execute("SELECT opp_id FROM saved WHERE user_id = ?", (g.user["id"],))
    return frozenset(r["opp_id"] for r in rows)


def pull_topic(t):
    """Mavzu bo'yicha Google News'dan yangi natijalarni olib bazaga qo'shadi (15 daqiqa kesh)."""
    items = sources.topic_search(t["key"], t["google"], t["terms"], t["default"])
    if not items:
        return 0
    db = get_db()
    added = sum(1 for it in items if insert_opportunity(db, it))
    if added:
        db.commit()
    return added


def query_words(query):
    return [w for w in re.findall(r"[\w']+", sources._norm(query)) if len(w) >= 2][:6]


def query_stems(query):
    """Qidiruv so'zlarining o'zagi va sinonimlari (tekis ro'yxat)."""
    out = []
    for w in query_words(query):
        out += synonyms.expand(w)
    return list(dict.fromkeys(out))


def pull_query(query):
    """Istalgan soha so'zi bo'yicha Google News'dan qidirib bazaga qo'shadi (uz/en/ru)."""
    words = query_words(query)
    if not words:
        return 0
    q = " ".join(query.split()[:6])
    en = " ".join(synonyms.english(w) for w in words)
    uz_alt = " ".join((synonyms.expand(w) + [w])[1] for w in words)  # masalan raqqoslik -> raqs
    pseudo = {
        "key": "q:" + sources._norm(q),
        "google": [(f"{q} yoshlar {{year}}", "uz"), (f"{q} tanlov", "uz"), (f"{q} kurs", "uz"),
                   (f"{q} vakansiya amaliyot", "uz"), (f"{uz_alt} tanlov festival yoshlar", "uz"),
                   (f"{q} grant stipendiya", "uz"), (f"{q} bepul kurs yoshlar", "uz"),
                   (f"{q} конкурс молодежь Узбекистан", "ru"),
                   (f"Uzbekistan {en} competition {{year}}", "en")],
        "terms": query_stems(query),
        "default": ("Tanlovlar", "Imkoniyat"),
    }
    return pull_topic(pseudo)


def like_escape(word):
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_filter(category, query, topic=""):
    where, params = [], []
    if category in CATEGORIES:
        where.append("category = ?")
        params.append(category)
    if topic in TOPIC_MAP:
        terms = TOPIC_MAP[topic]["terms"]
        # search_text atrofiga bo'sh joy qo'shamiz, shunda " it " kabi qisqa so'zlar ham topiladi
        where.append("(" + " OR ".join(["(' ' || search_text || ' ') LIKE ? ESCAPE '\\'"] * len(terms)) + ")")
        params.extend(f"%{like_escape(t)}%" for t in terms)
    for word in query_words(query):  # har bir so'z: o'zagi YOKI sinonimi bo'lsin
        alts = synonyms.expand(word)
        where.append("(" + " OR ".join(["search_text LIKE ? ESCAPE '\\'"] * len(alts)) + ")")
        params.extend(f"%{like_escape(a)}%" for a in alts)
    return (" WHERE " + " AND ".join(where)) if where else "", params


# ============================================================
# HOOKLAR (xavfsizlik)
# ============================================================

def register_hooks(app):
    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("user_id")
        if uid:
            g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if g.user is None:
                session.clear()
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            if not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Sessiya muddati tugagan. Sahifani yangilab qayta urinib ko‘ring.")

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return resp

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": session.get("csrf", ""),
            "current_user": g.get("user"),
            "is_admin": is_admin(),
            "categories": CATEGORIES,
            "topics": TOPICS,
            "cat_class": lambda c: CATEGORY_CLASS.get(c, "contest"),
            "cat_icon": lambda c: CATEGORY_ICON.get(c, "•"),
            "cat_emoji": lambda c: CATEGORY_EMOJI.get(c, "✨"),
            "short_source": lambda s: (s or "").split(" (")[0],
            "ago": sources.ago,
            "safe_link": lambda u: u if (u or "").startswith(("http://", "https://")) else "#",
        }

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(429)
    def http_error(err):
        return render_template("error.html", code=err.code,
                               message=getattr(err, "description", "")), err.code


# ============================================================
# MARSHRUTLAR
# ============================================================

def register_routes(app):

    @app.route("/")
    def index():
        db = get_db()
        saved_ids = user_saved_ids()
        rows = db.execute(
            "SELECT * FROM opportunities WHERE published != '' "
            "ORDER BY published DESC, id DESC LIMIT 6").fetchall()
        day_ago = sources.fmt_ts(sources.now_utc() - timedelta(hours=24))
        stats = {
            "total": db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
            "new": db.execute("SELECT COUNT(*) FROM opportunities WHERE published >= ?",
                              (day_ago,)).fetchone()[0],
            "grants": db.execute("SELECT COUNT(*) FROM opportunities WHERE category = 'Grantlar'").fetchone()[0],
            "saved": len(saved_ids),
        }
        status = {
            "time": get_meta(db, "last_status_time"),
            "ok": get_meta(db, "last_ok"),
        }
        return render_template("index.html", items=[row_to_item(r, saved_ids) for r in rows],
                               stats=stats, status=status)

    @app.route("/opportunities")
    def opportunities():
        category = request.args.get("category", "")
        query = clean(request.args.get("q"), 100)
        try:
            page = max(1, int(request.args.get("page", "1")))
        except ValueError:
            page = 1
        topic = request.args.get("t", "")
        if topic not in TOPIC_MAP:
            topic = ""
        if page == 1:
            if topic:
                pull_topic(TOPIC_MAP[topic])
            if query:
                pull_query(query)
        where, params = build_filter(category, query, topic)
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM opportunities" + where, params).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM opportunities" + where +
            " ORDER BY lang, published DESC, id DESC LIMIT ? OFFSET ?",
            params + [PER_PAGE, (page - 1) * PER_PAGE]).fetchall()
        saved_ids = user_saved_ids()
        pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        web_query = " ".join(x for x in (query, TOPIC_MAP[topic]["web"] if topic else "") if x)
        web_label = " · ".join(x for x in (TOPIC_MAP[topic]["label"] if topic else "", query) if x)
        web_results = sources.web_search_opps(web_query) if web_query and page == 1 else []
        return render_template("opportunities.html",
                               items=[row_to_item(r, saved_ids) for r in rows],
                               total=total, page=page, pages=pages,
                               category=category, q=query, topic=topic,
                               topic_obj=TOPIC_MAP.get(topic),
                               web_label=web_label, web_results=web_results)

    @app.route("/save/<int:oid>", methods=["POST"])
    @login_required
    def toggle_save(oid):
        db = get_db()
        if db.execute("SELECT 1 FROM opportunities WHERE id = ?", (oid,)).fetchone() is None:
            abort(404)
        existing = db.execute("SELECT 1 FROM saved WHERE user_id = ? AND opp_id = ?",
                              (g.user["id"], oid)).fetchone()
        if existing:
            db.execute("DELETE FROM saved WHERE user_id = ? AND opp_id = ?", (g.user["id"], oid))
            db.execute("DELETE FROM applications WHERE user_id = ? AND opp_id = ? AND status = 'saved'", (g.user["id"], oid))
            flash("Saqlanganlardan olib tashlandi.", "info")
        else:
            db.execute("INSERT INTO saved(user_id, opp_id, created_at) VALUES (?,?,?)",
                       (g.user["id"], oid, sources.fmt_ts(sources.now_utc())))
            if not db.execute("SELECT 1 FROM applications WHERE user_id=? AND opp_id=?", (g.user["id"], oid)).fetchone():
                db.execute("INSERT INTO applications(user_id, opp_id, updated_at) VALUES (?,?,?)",
                           (g.user["id"], oid, sources.fmt_ts(sources.now_utc())))
                features.award(db, g.user["id"], "track", oid)
            flash("Ariza doskangizga qo‘shildi ⭐", "success")
        db.commit()
        return redirect(safe_next(request.form.get("next")))

    @app.route("/saved")
    @login_required
    def saved():
        return redirect(url_for("board"))

    @app.route("/recommended")
    @login_required
    def recommended():
        interest = g.user["interest"]
        items = []
        if interest:
            words = [w for w in sources._norm(interest).replace(",", " ").split() if len(w) > 1][:6]
            rows = get_db().execute(
                "SELECT * FROM opportunities ORDER BY published DESC, id DESC LIMIT 500").fetchall()
            scored = []
            for r in rows:
                score = sum(2 for w in words if w in r["search_text"])
                if score:
                    scored.append((score, r))
            scored.sort(key=lambda x: x[0], reverse=True)
            saved_ids = user_saved_ids()
            items = [row_to_item(r, saved_ids) for _, r in scored[:50]]
        return render_template("recommended.html", items=items, interest=interest)

    # ---------------------- AUTH ----------------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("index"))
        form = {"email": "", "name": ""}
        if request.method == "POST":
            email = clean(request.form.get("email"), 120).lower()
            name = clean(request.form.get("name"), 80)
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            form = {"email": email, "name": name}
            error = None
            if not EMAIL_RE.match(email):
                error = "Email manzil noto‘g‘ri."
            elif len(password) < 8:
                error = "Parol kamida 8 ta belgidan iborat bo‘lishi kerak."
            elif len(password) > 200:
                error = "Parol juda uzun."
            elif password != confirm:
                error = "Parollar bir xil emas."
            elif not request.form.get("agree"):
                error = "Davom etish uchun maxfiylik siyosatiga rozilik bering."
            if not error:
                db = get_db()
                try:
                    cur = db.execute(
                        "INSERT INTO users(email, password_hash, name, created_at) VALUES (?,?,?,?)",
                        (email, generate_password_hash(password), name,
                         sources.fmt_ts(sources.now_utc())))
                    db.commit()
                except sqlite3.IntegrityError:
                    error = "Bu email bilan hisob allaqachon mavjud."
                else:
                    session.clear()  # sessiya fiksatsiyasidan himoya
                    session["user_id"] = cur.lastrowid
                    session["csrf"] = secrets.token_hex(16)
                    session.permanent = True
                    flash("Xush kelibsiz! Profilingizni to‘ldiring.", "success")
                    return redirect(url_for("profile"))
            flash(error, "error")
        return render_template("register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("index"))
        nxt = request.args.get("next") or request.form.get("next") or ""
        if request.method == "POST":
            email = clean(request.form.get("email"), 120).lower()
            password = request.form.get("password", "")
            key = (request.remote_addr, email)
            if too_many_fails(key):
                abort(429, "Juda ko‘p urinish. 15 daqiqadan keyin qayta urinib ko‘ring.")
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
            if user and ok:
                _login_fails.pop(key, None)
                session.clear()
                session["user_id"] = user["id"]
                session["csrf"] = secrets.token_hex(16)
                session.permanent = True
                return redirect(safe_next(nxt))
            _login_fails.setdefault(key, []).append(time.time())
            flash("Email yoki parol noto‘g‘ri.", "error")
        return render_template("login.html", next=nxt)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Tizimdan chiqdingiz.", "info")
        return redirect(url_for("index"))

    # ---------------------- PROFIL ----------------------

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            db = get_db()
            db.execute(
                """UPDATE users SET name=?, university=?, major=?, course=?, region=?, interest=?,
                   telegram=?, lang_level=? WHERE id=?""",
                (clean(request.form.get("name"), 80), clean(request.form.get("university"), 120),
                 clean(request.form.get("major"), 120), clean(request.form.get("course"), 40),
                 clean(request.form.get("region"), 80), clean(request.form.get("interest"), 100),
                 features.tg_username(request.form.get("telegram")), clean(request.form.get("lang_level"), 40),
                 g.user["id"]))
            user = db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone()
            if features.profile_complete(user) and features.award(db, g.user["id"], "profile", "first"):
                flash("Profil to‘liq! +20 ball", "success")
            db.commit()
            flash("Profil saqlandi.", "success")
            return redirect(url_for("profile"))
        return render_template("profile.html")

    @app.route("/account/delete", methods=["POST"])
    @login_required
    def delete_account():
        if not check_password_hash(g.user["password_hash"], request.form.get("password", "")):
            flash("Parol noto‘g‘ri. Hisob o‘chirilmadi.", "error")
            return redirect(url_for("profile"))
        db = get_db()
        db.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))  # saved ham CASCADE bilan o'chadi
        db.commit()
        session.clear()
        flash("Hisobingiz va barcha ma’lumotlaringiz o‘chirildi.", "info")
        return redirect(url_for("index"))

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    # ---------------------- ADMIN ----------------------

    @app.route("/admin")
    @admin_required
    def admin():
        db = get_db()
        return render_template(
            "admin.html",
            feeds=db.execute("SELECT * FROM feeds ORDER BY id").fetchall(),
            users_count=db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            total=db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
            meta={k: get_meta(db, k) for k in
                  ("last_status_time", "last_ok", "last_added", "last_error")},
            refresh_minutes=REFRESH_MINUTES)

    @app.route("/admin/refresh", methods=["POST"])
    @admin_required
    def admin_refresh():
        threading.Thread(target=refresh_now, kwargs={"force": True}, daemon=True).start()
        flash("Yangilash fon rejimida boshlandi. 20–30 soniyadan keyin sahifani yangilang.", "info")
        return redirect(url_for("admin"))

    @app.route("/admin/feeds/add", methods=["POST"])
    @admin_required
    def admin_feed_add():
        name = clean(request.form.get("name"), 80)
        url = clean(request.form.get("url"), 400)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            flash("Havola http:// yoki https:// bilan boshlanishi kerak.", "error")
            return redirect(url_for("admin"))
        try:
            count = len(sources.parse_feed(sources._http_get(url)))
        except Exception as exc:
            flash(f"Havolaga ulanib bo‘lmadi: {str(exc)[:100]}", "error")
            return redirect(url_for("admin"))
        if count == 0:
            flash("Havola ochildi, lekin RSS/Atom yozuvlari topilmadi.", "error")
            return redirect(url_for("admin"))
        db = get_db()
        try:
            db.execute("INSERT INTO feeds(name, url) VALUES (?,?)", (name or parsed.netloc, url))
            db.commit()
            flash(f"Manba qo‘shildi ({count} ta yozuv topildi).", "success")
        except sqlite3.IntegrityError:
            flash("Bu manba allaqachon qo‘shilgan.", "error")
        return redirect(url_for("admin"))

    @app.route("/admin/feeds/<int:fid>/delete", methods=["POST"])
    @admin_required
    def admin_feed_delete(fid):
        db = get_db()
        db.execute("DELETE FROM feeds WHERE id = ?", (fid,))
        db.commit()
        flash("Manba o‘chirildi.", "info")
        return redirect(url_for("admin"))

    @app.route("/admin/opportunity/add", methods=["POST"])
    @admin_required
    def admin_opportunity_add():
        title = clean(request.form.get("title"), 180)
        link = clean(request.form.get("link"), 400)
        category = request.form.get("category")
        if not title or category not in CATEGORIES or not link.startswith(("http://", "https://")):
            flash("Nomi, kategoriya va to‘g‘ri havola (http/https) kerak.", "error")
            return redirect(url_for("admin"))
        fields = [x.strip() for x in clean(request.form.get("fields"), 200).replace(";", ",").split(",")
                  if x.strip()] or ["Yoshlar"]
        item = {
            "title": title, "category": category,
            "location": clean(request.form.get("location"), 80) or "O‘zbekiston",
            "type": clean(request.form.get("type"), 60) or "Umumiy",
            "deadline": clean(request.form.get("deadline"), 40) or "Ko‘rsatilmagan",
            "fields": fields, "link": link, "source": sources.SRC_MANUAL,
            "published": sources.fmt_ts(sources.now_utc()),
            "description": clean(request.form.get("description"), 500) or "Tavsif kiritilmagan.",
        }
        db = get_db()
        if insert_opportunity(db, item, pinned=1):
            db.commit()
            flash("Imkoniyat qo‘shildi.", "success")
        else:
            flash("Bunday havola yoki sarlavha allaqachon mavjud.", "error")
        return redirect(url_for("admin"))

    @app.route("/admin/opportunity/<int:oid>/delete", methods=["POST"])
    @admin_required
    def admin_opportunity_delete(oid):
        db = get_db()
        db.execute("DELETE FROM opportunities WHERE id = ?", (oid,))
        db.commit()
        flash("Imkoniyat o‘chirildi.", "info")
        return redirect(safe_next(request.form.get("next")))


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
