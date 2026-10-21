"""
Yoshlar Hub — talaba kabineti va hamjamiyat funksiyalari.

  * Ariza doskasi (Saqlangan → Tayyorlanyapman → Topshirdim → Natija)
  * Muddatlar taqvimi va Telegram eslatmalari
  * Hujjatlar sumkasi + har e'lon uchun kerakli hujjatlar ro'yxati
  * Motivatsion xat qoralamasi (shablon asosida)
  * Moslik foizi
  * Jamoa topish, reyting, ball va nishonlar
  * Hamjamiyat (savol-javob), g'oliblar tajribasi
  * Portfolio (ommaviy havola) va "Yo'lingni top" testi

app.py dagi yordamchilar `register(app, h)` orqali beriladi (h — oddiy obyekt).
"""
import calendar
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (abort, flash, g, redirect, render_template, request,
                   send_from_directory, url_for)

import sources

SITE_NAME = os.environ.get("SITE_NAME", "Yoshlar Hub")
TELEGRAM_GROUP_LINK = os.environ.get("TELEGRAM_GROUP_LINK", "").strip()
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(__file__).resolve().parent / "uploads"))
ALLOWED_EXT = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}
MAX_DOCS = 30

# ------------------------------------------------------------------ jadvallar
SCHEMA_EXTRA = """
CREATE TABLE IF NOT EXISTS applications (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opp_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'saved',
    deadline TEXT NOT NULL DEFAULT '',
    letter TEXT NOT NULL DEFAULT '',
    reminded TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, opp_id)
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    stored TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'team',
    event TEXT NOT NULL DEFAULT '',
    opp_id INTEGER,
    body TEXT NOT NULL,
    needs TEXT NOT NULL DEFAULT '',
    members INTEGER NOT NULL DEFAULT 1,
    size INTEGER NOT NULL DEFAULT 4,
    is_open INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    helpful INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS votes (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, question_id)
);
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    achievement TEXT NOT NULL,
    tip TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    hours INTEGER NOT NULL DEFAULT 0,
    year TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    ref TEXT NOT NULL DEFAULT '',
    amount INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, action, ref)
);
CREATE INDEX IF NOT EXISTS idx_points_user ON points(user_id);
CREATE INDEX IF NOT EXISTS idx_q_channel ON questions(channel);
"""

USER_COLUMNS = {
    "telegram": "TEXT NOT NULL DEFAULT ''",        # @username — jamoa uchun "Yozish"
    "tg_chat_id": "TEXT NOT NULL DEFAULT ''",      # bot ulanganda to'ladi
    "tg_code": "TEXT NOT NULL DEFAULT ''",         # botni ulash kodi
    "reminders_on": "INTEGER NOT NULL DEFAULT 1",
    "digest_on": "INTEGER NOT NULL DEFAULT 1",
    "lang_level": "TEXT NOT NULL DEFAULT ''",
    "bio": "TEXT NOT NULL DEFAULT ''",
    "slug": "TEXT NOT NULL DEFAULT ''",
    "portfolio_public": "INTEGER NOT NULL DEFAULT 0",
    "direction": "TEXT NOT NULL DEFAULT ''",
    "avatar": "TEXT NOT NULL DEFAULT '🙂'",
}


def migrate(conn):
    conn.executescript(SCHEMA_EXTRA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    for col, ddl in USER_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    conn.commit()


# ------------------------------------------------------------------ lug'atlar
STATUSES = [
    ("saved", "⭐", "Saqlangan"),
    ("preparing", "🛠", "Tayyorlanyapman"),
    ("submitted", "📨", "Topshirdim"),
    ("accepted", "✅", "Qabul qilindi"),
    ("rejected", "❌", "Rad etildi"),
]
STATUS_LABEL = {k: f"{i} {t}" for k, i, t in STATUSES}
BOARD_COLUMNS = [("saved", "⭐ Saqlangan"), ("preparing", "🛠 Tayyorlanyapman"),
                 ("submitted", "📨 Topshirdim"), ("result", "🏁 Natija")]

DOC_KINDS = [
    ("cv", "📄", "Rezyume (CV)"),
    ("motivation", "✉️", "Motivatsion xat"),
    ("student_id", "🎓", "Talabalik guvohnomasi"),
    ("passport", "🪪", "Pasport nusxasi"),
    ("language", "🗣️", "Til sertifikati (IELTS va b.)"),
    ("certificate", "🏅", "Kurs sertifikati"),
    ("diploma", "📜", "Diplom / transkript"),
    ("recommendation", "🤝", "Tavsiyanoma"),
    ("idea", "💡", "G‘oya taqdimoti / biznes-reja"),
    ("other", "📎", "Boshqa hujjat"),
]
DOC_LABEL = {k: (i, t) for k, i, t in DOC_KINDS}
REQUIRED_DOCS = {
    "Grantlar": ["cv", "motivation", "idea", "student_id"],
    "Ish va internship": ["cv", "motivation", "diploma"],
    "Tanlovlar": ["cv", "idea", "student_id"],
    "Kurslar": ["passport", "student_id"],
    "Volunteer": ["passport"],
    "Tadbirlar": ["passport"],
}
SCHOLARSHIP_WORDS = ("stipend", "scholarship", "magistr", "xorij")

CHANNELS = [
    ("umumiy", "Umumiy"), ("ish", "Ish va amaliyot"), ("grantlar", "Grantlar"),
    ("stipendiyalar", "Stipendiyalar"), ("hakatonlar", "Hakatonlar"),
    ("jamoa-topish", "Jamoa topish"), ("ielts", "IELTS va tillar"),
    ("loyihalar", "O‘z loyiham"), ("volontyorlik", "Volontyorlik"),
]
CHANNEL_LABEL = dict(CHANNELS)

STORY_CATS = [("stipendiya", "🎓", "Stipendiya"), ("hakaton", "🏆", "Hakaton"),
              ("grant", "💰", "Grant"), ("ish", "💼", "Ish va amaliyot"),
              ("volontyor", "🤝", "Volontyorlik"), ("loyiha", "🚀", "O‘z loyiham")]
STORY_LABEL = {k: (i, t) for k, i, t in STORY_CATS}

PORTFOLIO_KINDS = [("project", "🚀", "Loyiha"), ("volunteer", "🤝", "Volontyorlik"),
                   ("certificate", "🏅", "Sertifikat"), ("award", "🏆", "Yutuq"),
                   ("work", "💼", "Ish tajribasi")]
PORTFOLIO_LABEL = {k: (i, t) for k, i, t in PORTFOLIO_KINDS}

AVATARS = ["🙂", "😎", "🧑‍💻", "👩‍💻", "👨‍🎓", "👩‍🎓", "🧑‍🚀", "👩‍🎨", "👨‍💼", "👩‍🏫", "🦊", "🐼"]

# Ballar: (harakat) -> miqdor. Har bir (harakat, ref) faqat bir marta beriladi.
POINTS = {
    "profile": 20, "test": 20, "track": 5, "submitted": 20, "accepted": 100,
    "doc": 5, "team": 30, "question": 5, "answer": 10, "helpful": 15,
    "story": 40, "portfolio": 10, "telegram": 20,
}
ACTION_LABEL = {
    "profile": "Profil to‘ldirildi", "test": "Yo‘nalish testi", "track": "Imkoniyat saqlandi",
    "submitted": "Ariza topshirildi", "accepted": "Qabul qilindi", "doc": "Hujjat yuklandi",
    "team": "Jamoa e’loni", "question": "Savol berildi", "answer": "Savolga javob",
    "helpful": "Foydali javob", "story": "G‘alaba tajribasi", "portfolio": "Portfolioga qo‘shildi",
    "telegram": "Telegram ulandi",
}
LEVELS = [(0, "Yangi boshlovchi"), (100, "Izlanuvchi"), (250, "Harakatchan"),
          (500, "Faol yosh"), (1000, "Yetakchi"), (2000, "Ilhom manbai")]

BADGES = [
    ("first", "🥇", "Birinchi ariza", "1 ta ariza topshiring"),
    ("five", "🔥", "5 ta ariza", "5 ta ariza topshiring"),
    ("docs", "🎒", "Hujjatlar tayyor", "3 ta hujjat yuklang"),
    ("team", "👥", "Jamoa a’zosi", "Jamoa e’lonini bering"),
    ("winner", "🏆", "G‘olib", "1 ta qabul / g‘alaba"),
    ("mentor", "💬", "Maslahatchi", "5 ta javob yozing"),
    ("volunteer", "🤝", "Ko‘ngilli", "20 soat volontyorlik"),
    ("builder", "🚀", "Loyiha egasi", "Portfolioga loyiha qo‘shing"),
    ("compass", "🧭", "Yo‘lini topgan", "Yo‘nalish testini yeching"),
]

# ------------------------------------------------------------------ "Yo'lingni top" testi
DIRECTIONS = {
    "it": {"icon": "💻", "title": "IT va dasturlash", "topic": "it",
           "text": "Mantiq, texnologiya va narsalarni yaratish sizga yoqadi. Dasturchi, data analyst, QA yoki IT-loyiha menejeri bo‘lishingiz mumkin.",
           "steps": [("📚", "Bepul asosiy kurs", "Python yoki Frontend bo‘yicha bepul kursni boshlang", "it"),
                     ("🚀", "Birinchi loyiha", "Oddiy sayt yoki bot yasab, portfolioga qo‘shing", None),
                     ("🏆", "Hakatonda qatnashing", "Jamoa toping va 48 soatlik hakatonga yoziling", "hackathon"),
                     ("💼", "Amaliyot va ish", "Junior / intern vakansiyalarga ariza bering", "internship")]},
    "design": {"icon": "🎨", "title": "Dizayn va kontent", "topic": "marketing",
               "text": "Chiroyli, tushunarli narsalar yaratish va ijod sizniki. UI/UX dizayner, grafik dizayner yoki kontent-meyker yo‘nalishi mos.",
               "steps": [("📚", "Figma / grafik dizayn kursi", "Bepul dizayn kursidan boshlang", "marketing"),
                         ("🚀", "3 ta ish namunasi", "Do‘stingiz yoki NNT uchun logo, banner, sayt maketi qiling", None),
                         ("🤝", "Volontyor dizayner", "Tadbir va aksiyalarga dizayn bo‘yicha yordam bering", "volunteer"),
                         ("💼", "Frilans va amaliyot", "Dizayn bo‘yicha amaliyot va buyurtmalar izlang", "internship")]},
    "business": {"icon": "📈", "title": "Biznes va startap", "topic": "startap",
                 "text": "G‘oya topish, odamlarni yig‘ish va natijaga erishish sizga yoqadi. Tadbirkor, startap asoschisi yoki loyiha menejeri bo‘lishingiz mumkin.",
                 "steps": [("💡", "G‘oyani yozing", "Muammo, yechim va mijozni bir sahifada tasvirlang", None),
                           ("👥", "Jamoa yig‘ing", "Jamoa topish bo‘limida sherik izlang", None),
                           ("🏆", "Startap tanlovi", "Startap tanlovlari va akseleratorlarga ariza bering", "startap"),
                           ("💰", "Grant oling", "Yosh tadbirkorlar uchun grant va subsidiyalarga topshiring", "biznes")]},
    "marketing": {"icon": "📣", "title": "Marketing va SMM", "topic": "marketing",
                  "text": "Odamlar bilan muloqot, ijtimoiy tarmoqlar va g‘oyani “sotish” sizga oson. SMM mutaxassis, marketolog yoki PR menejeri yo‘nalishi mos.",
                  "steps": [("📚", "SMM kursi", "Bepul SMM / raqamli marketing kursini o‘ting", "marketing"),
                            ("🚀", "Sahifa yuriting", "Bitta loyiha yoki NNT sahifasini 1 oy yuriting, natijani yozing", None),
                            ("🤝", "Tadbirlarda PR", "Volontyor sifatida tadbir PR’iga yordam bering", "volunteer"),
                            ("💼", "Amaliyot", "Marketing bo‘limlarida amaliyot izlang", "ish")]},
    "social": {"icon": "🤝", "title": "Ijtimoiy faollik va ta’lim", "topic": "volunteer",
               "text": "Odamlarga yordam berish va jamiyatni o‘zgartirish sizni ilhomlantiradi. NNT, ta’lim, ijtimoiy loyihalar va davlat dasturlari mos.",
               "steps": [("🤝", "Volontyorlik", "Har oy kamida bitta aksiyada qatnashing", "volunteer"),
                         ("💡", "O‘z ijtimoiy loyihangiz", "Mahallangiz muammosini hal qiluvchi loyiha boshlang", None),
                         ("💰", "Ijtimoiy grantlar", "Yoshlar loyihalari uchun grantlarga topshiring", "grant"),
                         ("🎓", "Almashinuv dasturlari", "Xorijiy almashinuv va stipendiyalarni kuzating", "talaba")]},
    "language": {"icon": "🗣️", "title": "Tillar va xalqaro imkoniyatlar", "topic": "til",
                 "text": "Tillar, madaniyatlar va chet elda o‘qish sizni qiziqtiradi. Tarjimon, o‘qituvchi yoki xalqaro tashkilotlarda ishlash yo‘lini tanlang.",
                 "steps": [("🗣️", "IELTS / CEFR", "Bepul til kurslari bilan darajangizni oshiring", "til"),
                           ("🎓", "Stipendiyalar", "Xorijiy stipendiya va almashinuv dasturlariga tayyorlaning", "grant"),
                           ("🤝", "Xalqaro volontyorlik", "Xalqaro tadbirlarda tarjimon-volontyor bo‘ling", "volunteer"),
                           ("💼", "Ish", "Til talab qilinadigan vakansiyalarga topshiring", "ish")]},
}

TEST_QUESTIONS = [
    ("Bo‘sh vaqtingizda ko‘proq nima qilasiz?",
     [("Kompyuterda biror narsani sozlayman yoki o‘rganaman", "it"), ("Rasm chizaman, video yoki dizayn qilaman", "design"),
      ("Pul topish g‘oyalarini o‘ylayman", "business"), ("Ijtimoiy tarmoqlarda kontent ko‘raman/qilaman", "marketing"),
      ("Do‘stlarga yordam beraman, tadbirlarda qatnashaman", "social"), ("Chet tilida film ko‘raman, kitob o‘qiyman", "language")]),
    ("Maktabda qaysi fan sizga eng oson edi?",
     [("Matematika, informatika", "it"), ("Tasviriy san’at, chizmachilik", "design"), ("Iqtisod", "business"),
      ("Adabiyot, ona tili", "marketing"), ("Tarix, huquq", "social"), ("Ingliz yoki boshqa chet tili", "language")]),
    ("Jamoada qaysi rolni tanlaysiz?",
     [("Texnik qismni qilaman", "it"), ("Ko‘rinishi va dizaynini qilaman", "design"), ("Rejani tuzib, hammani boshqaraman", "business"),
      ("Taqdimot qilib, odamlarga gapiraman", "marketing"), ("Jamoadagilarni qo‘llab-quvvatlayman", "social"), ("Chet ellik hamkorlar bilan gaplashaman", "language")]),
    ("Qaysi ish sizni ko‘proq quvontiradi?",
     [("Muammoni mantiqan yechish", "it"), ("Chiroyli natijani ko‘rish", "design"), ("Birinchi daromadni topish", "business"),
      ("Postim ko‘p odamga yetib borishi", "marketing"), ("Kimgadir yordam bergan bo‘lish", "social"), ("Yangi madaniyat bilan tanishish", "language")]),
    ("5 yildan keyin o‘zingizni qayerda ko‘rasiz?",
     [("Katta IT kompaniyada", "it"), ("O‘z dizayn studiyamda", "design"), ("O‘z kompaniyamda", "business"),
      ("Mashhur brend jamoasida", "marketing"), ("NNT yoki davlat dasturida", "social"), ("Xorijda o‘qiyotgan / ishlayotgan", "language")]),
    ("Qaysi tanlovda qatnashardingiz?",
     [("Hakaton", "it"), ("Dizayn konkursi", "design"), ("Startap tanlovi", "business"),
      ("Reklama / video tanlovi", "marketing"), ("Ijtimoiy loyihalar tanlovi", "social"), ("Til olimpiadasi / esse tanlovi", "language")]),
    ("Sizga qaysi so‘z yaqinroq?",
     [("Kod", "it"), ("Ranglar", "design"), ("Natija", "business"), ("Auditoriya", "marketing"), ("Mehr", "social"), ("Dunyo", "language")]),
    ("Yangi narsani qanday o‘rganasiz?",
     [("O‘zim sinab, xato qilib", "it"), ("Ko‘rib, namunalarga qarab", "design"), ("Tajribali odamdan so‘rab", "business"),
      ("Video va bloglardan", "marketing"), ("Guruhda, birga o‘rganib", "social"), ("Kitob va kurslardan", "language")]),
    ("Do‘stlaringiz sizni qanday ta’riflaydi?",
     [("Aqlli, texnikaga usta", "it"), ("Ijodkor", "design"), ("Tashabbuskor", "business"),
      ("Gapga chechan", "marketing"), ("Mehribon, ishonchli", "social"), ("Qiziquvchan, sayohatchi", "language")]),
    ("Qaysi muammoni hal qilgan bo‘lardingiz?",
     [("Davlat xizmatlarini onlayn qilish", "it"), ("Shaharni chiroyli qilish", "design"), ("Yoshlar ishsizligini kamaytirish", "business"),
      ("Mahalliy brendlarni mashhur qilish", "marketing"), ("Ekologiya va ehtiyojmandlarga yordam", "social"), ("Ta’limni xalqaro darajaga chiqarish", "language")]),
    ("Ishda nima eng muhim?",
     [("Qiziq texnik vazifalar", "it"), ("Ijodiy erkinlik", "design"), ("Yuqori daromad", "business"),
      ("Odamlar bilan ishlash", "marketing"), ("Foydali ish qilish", "social"), ("Xalqaro muhit", "language")]),
    ("Hozir qaysi imkoniyat sizni ko‘proq qiziqtiradi?",
     [("Bepul IT kurs", "it"), ("Dizayn bo‘yicha amaliyot", "design"), ("Startap granti", "business"),
      ("SMM intensiv", "marketing"), ("Volontyorlik aksiyasi", "social"), ("Xorijiy stipendiya", "language")]),
]

LETTER_TEMPLATES = {
    "Grantlar": ("Hurmatli grant tanlov komissiyasi!\n\n"
                 "Men, {name}, {uni_part}. {interest_part}\n\n"
                 "“{title}” dasturi menga g‘oyamni amalga oshirish uchun zarur imkoniyat beradi. "
                 "Grant mablag‘ini loyihaning dastlabki natijalariga erishish, sinov va kengaytirishga yo‘naltirishni rejalashtiryapman.\n\n"
                 "Men mas’uliyatli va natijaga yo‘naltirilgan insonman. Har bir bosqich bo‘yicha hisobot berishga tayyorman.\n\n"
                 "Hurmat bilan,\n{name}"),
    "Ish va internship": ("Hurmatli ishga qabul qilish bo‘limi!\n\n"
                          "Men, {name}, {uni_part}. “{title}” bo‘yicha e’loningiz bilan tanishib, ushbu lavozimga o‘z nomzodimni taklif qilmoqchiman.\n\n"
                          "{interest_part} O‘qish davomida mustaqil ishlash, jamoada ishlash va yangi narsalarni tez o‘rganishni o‘rgandim.\n\n"
                          "Jamoangizga foyda keltirishga va tajriba orttirishga tayyorman. Suhbatga taklif qilsangiz, xursand bo‘laman.\n\n"
                          "Hurmat bilan,\n{name}"),
    "Tanlovlar": ("Hurmatli tashkilotchilar!\n\n"
                  "Men, {name}, {uni_part}. “{title}” tanlovi haqida bilib, unda qatnashishga qaror qildim.\n\n"
                  "{interest_part} Bu tanlov bilimlarimni amalda sinash, kuchli jamoalar bilan tanishish va o‘z g‘oyamni ko‘rsatish uchun ajoyib imkoniyat.\n\n"
                  "Tanlovning barcha shartlariga rioya qilishga va oxirigacha qatnashishga tayyorman.\n\n"
                  "Hurmat bilan,\n{name}"),
    "Kurslar": ("Assalomu alaykum!\n\n"
                "Men, {name}, {uni_part}. “{title}” kursida o‘qishni juda xohlayman.\n\n"
                "{interest_part} Kurs menga yangi ko‘nikmalar beradi va kelajakdagi kasbimga mustahkam poydevor bo‘ladi.\n\n"
                "Darslarga muntazam qatnashish va barcha topshiriqlarni bajarishga va’da beraman.\n\n"
                "Hurmat bilan,\n{name}"),
    "Volunteer": ("Assalomu alaykum!\n\n"
                  "Men, {name}, {uni_part}. “{title}” loyihasida ko‘ngilli bo‘lib ishtirok etmoqchiman.\n\n"
                  "{interest_part} Jamiyatga foydali ish qilish va yangi odamlar bilan birga ishlash men uchun muhim.\n\n"
                  "Belgilangan vaqtda qatnashishga va topshiriqlarni mas’uliyat bilan bajarishga tayyorman.\n\n"
                  "Hurmat bilan,\n{name}"),
}
LETTER_TEMPLATES["Tadbirlar"] = LETTER_TEMPLATES["Volunteer"]


# ------------------------------------------------------------------ yordamchi hisoblar
def now_ts():
    return sources.fmt_ts(sources.now_utc())


def today():
    return (sources.now_utc() + timedelta(hours=5)).date()  # Toshkent vaqti


def parse_day(value):
    try:
        return datetime.strptime((value or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def app_deadline(app_row, opp_row):
    """Foydalanuvchi kiritgan muddat, bo'lmasa e'londagi ISO sana."""
    return parse_day(app_row["deadline"] if app_row else "") or parse_day(opp_row["deadline"])


def days_left(d):
    return (d - today()).days if d else None


def award(db, user_id, action, ref=""):
    """Ball qo'shadi (bir harakat+ref faqat bir marta). Yangi ball bo'lsa True."""
    amount = POINTS.get(action)
    if not amount or not user_id:
        return False
    try:
        db.execute("INSERT INTO points(user_id, action, ref, amount, created_at) VALUES (?,?,?,?,?)",
                   (user_id, action, str(ref), amount, now_ts()))
        return True
    except sqlite3.IntegrityError:
        return False


def user_points(db, user_id):
    return db.execute("SELECT COALESCE(SUM(amount),0) FROM points WHERE user_id=?", (user_id,)).fetchone()[0]


def level_info(pts):
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if pts >= need:
            idx = i
    cur_need, name = LEVELS[idx]
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    if nxt:
        pct = int((pts - cur_need) * 100 / (nxt[0] - cur_need))
        return {"level": idx + 1, "name": name, "next_name": nxt[1], "next_need": nxt[0],
                "left": nxt[0] - pts, "pct": max(0, min(100, pct - pct % 5))}
    return {"level": idx + 1, "name": name, "next_name": None, "next_need": None, "left": 0, "pct": 100}


def user_stats(db, user_id):
    q = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    return {
        "tracked": q("SELECT COUNT(*) FROM applications WHERE user_id=?", user_id),
        "submitted": q("SELECT COUNT(*) FROM applications WHERE user_id=? AND status IN ('submitted','accepted','rejected')", user_id),
        "accepted": q("SELECT COUNT(*) FROM applications WHERE user_id=? AND status='accepted'", user_id),
        "docs": q("SELECT COUNT(*) FROM documents WHERE user_id=?", user_id),
        "teams": q("SELECT COUNT(*) FROM team_posts WHERE user_id=?", user_id),
        "answers": q("SELECT COUNT(*) FROM answers WHERE user_id=?", user_id),
        "hours": q("SELECT COALESCE(SUM(hours),0) FROM portfolio_items WHERE user_id=? AND kind='volunteer'", user_id),
        "projects": q("SELECT COUNT(*) FROM portfolio_items WHERE user_id=? AND kind='project'", user_id),
        "awards": q("SELECT COUNT(*) FROM portfolio_items WHERE user_id=? AND kind='award'", user_id),
    }


def user_badges(db, user):
    s = user_stats(db, user["id"])
    got = {
        "first": s["submitted"] >= 1, "five": s["submitted"] >= 5, "docs": s["docs"] >= 3,
        "team": s["teams"] >= 1, "winner": s["accepted"] + s["awards"] >= 1, "mentor": s["answers"] >= 5,
        "volunteer": s["hours"] >= 20, "builder": s["projects"] >= 1, "compass": bool(user["direction"]),
    }
    return [{"key": k, "icon": i, "title": t, "hint": h, "got": got[k]} for k, i, t, h in BADGES]


def profile_complete(user):
    return all(user[k] for k in ("name", "university", "major", "interest"))


def match_score(user, opp):
    """(foiz, sabablar) — profil va e'lon qanchalik mos."""
    if not user:
        return None, []
    text = " " + (opp["search_text"] or "") + " "
    score, reasons = 35, []
    interest = [w for w in re.findall(r"[\w']+", sources._norm(user["interest"])) if len(w) > 2]
    if interest and any(w[:5] in text for w in interest):
        score += 25
        reasons.append(("ok", f"Qiziqishingiz: {user['interest'][:30]}"))
    elif interest:
        reasons.append(("x", "Qiziqishingizga to‘liq mos emas"))
    major = [w for w in re.findall(r"[\w']+", sources._norm(user["major"])) if len(w) > 3]
    if major and any(w[:5] in text for w in major):
        score += 12
        reasons.append(("ok", f"Yo‘nalishingiz: {user['major'][:30]}"))
    if user["direction"] and user["direction"] in DIRECTIONS:
        d = DIRECTIONS[user["direction"]]
        terms = _TOPIC_MAP.get(d["topic"], {}).get("terms", [])
        if any(t in text for t in terms):
            score += 13
            reasons.append(("ok", f"Yo‘nalish testi: {d['title']}"))
    loc = sources._norm(opp["location"])
    region = sources._norm(user["region"])
    if "online" in loc or "o'zbekiston" in loc or (region and region[:5] in loc):
        score += 10
        reasons.append(("ok", "Joylashuv mos"))
    if any(w in text for w in ("student", "talaba", "yosh", "youth", "young")):
        score += 5
        reasons.append(("ok", "Talaba va yoshlar uchun"))
    if not (user["interest"] or user["major"]):
        reasons.append(("x", "Profilni to‘ldirsangiz, moslik aniqroq bo‘ladi"))
    score = max(10, min(98, score))
    return score - score % 1, reasons[:4]


def required_docs(opp):
    kinds = list(REQUIRED_DOCS.get(opp["category"], ["cv"]))
    text = opp["search_text"] or ""
    if any(w in text for w in SCHOLARSHIP_WORDS) and "language" not in kinds:
        kinds += ["language", "recommendation"]
    if "ielts" in text and "language" not in kinds:
        kinds.append("language")
    return kinds


def doc_checklist(db, user_id, opp):
    have = {r["kind"] for r in db.execute("SELECT DISTINCT kind FROM documents WHERE user_id=?", (user_id,))}
    app_row = db.execute("SELECT letter FROM applications WHERE user_id=? AND opp_id=?", (user_id, opp["id"])).fetchone()
    if app_row and app_row["letter"].strip():
        have.add("motivation")
    return [{"kind": k, "icon": DOC_LABEL[k][0], "title": DOC_LABEL[k][1], "have": k in have}
            for k in required_docs(opp)]


def make_letter(user, opp):
    name = user["name"] or "[Ismingiz]"
    bits = []
    if user["university"]:
        bits.append(f"{user['university']}")
    if user["course"]:
        bits.append(f"{user['course']}")
    if user["major"]:
        bits.append(f"“{user['major']}” yo‘nalishi")
    uni_part = (" ".join(bits) + " talabasiman") if bits else "talabaman"
    if user["interest"]:
        interest_part = f"Meni ayniqsa {user['interest']} sohasi qiziqtiradi va shu yo‘nalishda rivojlanmoqchiman."
    else:
        interest_part = "Men doimiy ravishda o‘z ustimda ishlayman va yangi bilimlarni o‘rganishga intilaman."
    tpl = LETTER_TEMPLATES.get(opp["category"], LETTER_TEMPLATES["Tanlovlar"])
    return tpl.format(name=name, uni_part=uni_part, interest_part=interest_part, title=opp["title"][:120])


def make_slug(db, user):
    base = re.sub(r"[^a-z0-9]+", "-", sources._norm(user["name"] or user["email"].split("@")[0])
                  .replace("'", "")).strip("-")[:24] or "talaba"
    slug, n = base, 1
    while db.execute("SELECT 1 FROM users WHERE slug=? AND id!=?", (slug, user["id"])).fetchone():
        n += 1
        slug = f"{base}-{n}"
    db.execute("UPDATE users SET slug=? WHERE id=?", (slug, user["id"]))
    return slug


def tg_username(value):
    v = (value or "").strip().lstrip("@")
    return v if re.fullmatch(r"[A-Za-z0-9_]{4,32}", v) else ""


def month_grid(year, month):
    cal = calendar.Calendar(firstweekday=0)
    return [list(week) for week in cal.monthdatescalendar(year, month)]


_TOPIC_MAP = {}  # register() da app.py dagi TOPIC_MAP bilan to'ldiriladi

UZ_MONTHS = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul",
             "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def fmt_day(d):
    return f"{d.day}-{UZ_MONTHS[d.month].lower()}" if d else ""


# ------------------------------------------------------------------ marshrutlar
def register(app, h):
    """h: get_db, login_required, clean, safe_next, row_to_item, user_saved_ids, CATEGORY_CLASS, TOPIC_MAP"""
    get_db, login_required, clean = h.get_db, h.login_required, h.clean
    _TOPIC_MAP.update(h.TOPIC_MAP)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @app.context_processor
    def inject_feature_globals():
        ctx = {"site_name": SITE_NAME, "tg_group": TELEGRAM_GROUP_LINK,
               "status_label": STATUS_LABEL, "fmt_day": fmt_day, "my_points": 0, "my_level": None,
               "nav_alerts": 0}
        if g.get("user"):
            db = get_db()
            pts = user_points(db, g.user["id"])
            ctx["my_points"] = pts
            ctx["my_level"] = level_info(pts)
            soon = 0
            for r in db.execute("""SELECT a.deadline adl, o.deadline odl FROM applications a
                                   JOIN opportunities o ON o.id=a.opp_id
                                   WHERE a.user_id=? AND a.status IN ('saved','preparing')""", (g.user["id"],)):
                d = parse_day(r["adl"]) or parse_day(r["odl"])
                if d is not None and 0 <= days_left(d) <= 3:
                    soon += 1
            ctx["nav_alerts"] = soon
        return ctx

    def opp_or_404(oid):
        row = get_db().execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone()
        if row is None:
            abort(404)
        return row

    # ---------- e'lon sahifasi (kengaytirilgan) ----------
    @app.route("/opportunity/<int:oid>")
    def opportunity(oid):
        db = get_db()
        opp = opp_or_404(oid)
        item = h.row_to_item(opp, h.user_saved_ids())
        ctx = {"item": item, "app": None, "match": None, "reasons": [], "docs": [], "letter": "",
               "teams": [], "stories": [], "deadline": None, "left": None}
        story_cat = {"Grantlar": "grant", "Ish va internship": "ish", "Tanlovlar": "hakaton",
                     "Volunteer": "volontyor"}.get(opp["category"], "loyiha")
        ctx["stories"] = db.execute("""SELECT s.*, u.name, u.avatar, u.university FROM stories s JOIN users u ON u.id=s.user_id
                                       WHERE s.category=? ORDER BY s.id DESC LIMIT 2""", (story_cat,)).fetchall()
        ctx["teams"] = db.execute("""SELECT t.*, u.name, u.avatar, u.telegram, u.major FROM team_posts t JOIN users u ON u.id=t.user_id
                                     WHERE t.is_open=1 AND (t.opp_id=? OR t.opp_id IS NULL) ORDER BY (t.opp_id IS NULL), t.id DESC LIMIT 3""",
                                  (oid,)).fetchall()
        app_row = None
        if g.user:
            app_row = db.execute("SELECT * FROM applications WHERE user_id=? AND opp_id=?", (g.user["id"], oid)).fetchone()
            ctx["app"] = app_row
            ctx["match"], ctx["reasons"] = match_score(g.user, opp)
            ctx["docs"] = doc_checklist(db, g.user["id"], opp)
            ctx["letter"] = app_row["letter"] if app_row and app_row["letter"] else make_letter(g.user, opp)
        d = app_deadline(app_row, opp)
        ctx["deadline"], ctx["left"] = d, days_left(d)
        return render_template("detail.html", statuses=STATUSES, **ctx)

    def upsert_app(db, user_id, oid, **fields):
        exists = db.execute("SELECT 1 FROM applications WHERE user_id=? AND opp_id=?", (user_id, oid)).fetchone()
        if not exists:
            db.execute("INSERT INTO applications(user_id, opp_id, updated_at) VALUES (?,?,?)", (user_id, oid, now_ts()))
            award(db, user_id, "track", oid)
            db.execute("INSERT OR IGNORE INTO saved(user_id, opp_id, created_at) VALUES (?,?,?)", (user_id, oid, now_ts()))
        for k, v in fields.items():
            db.execute(f"UPDATE applications SET {k}=?, updated_at=? WHERE user_id=? AND opp_id=?", (v, now_ts(), user_id, oid))

    @app.route("/opportunity/<int:oid>/status", methods=["POST"])
    @login_required
    def app_status(oid):
        opp_or_404(oid)
        status = request.form.get("status")
        db = get_db()
        if status == "remove":
            db.execute("DELETE FROM applications WHERE user_id=? AND opp_id=?", (g.user["id"], oid))
            db.execute("DELETE FROM saved WHERE user_id=? AND opp_id=?", (g.user["id"], oid))
            flash("Doskadan olib tashlandi.", "info")
        elif status in STATUS_LABEL:
            upsert_app(db, g.user["id"], oid, status=status)
            if status in ("submitted", "accepted", "rejected"):
                award(db, g.user["id"], "submitted", oid)
            if status == "accepted":
                award(db, g.user["id"], "accepted", oid)
                flash("Tabriklaymiz! 🎉 +100 ball. Tajribangizni “G‘oliblar” bo‘limida ulashing.", "success")
            else:
                flash(f"Holat: {STATUS_LABEL[status]}", "success")
        db.commit()
        return redirect(h.safe_next(request.form.get("next")) if request.form.get("next") else url_for("opportunity", oid=oid))

    @app.route("/opportunity/<int:oid>/deadline", methods=["POST"])
    @login_required
    def app_deadline_set(oid):
        opp_or_404(oid)
        d = parse_day(request.form.get("deadline"))
        db = get_db()
        upsert_app(db, g.user["id"], oid, deadline=d.isoformat() if d else "", reminded="")
        db.commit()
        flash("Muddat saqlandi. Telegram ulangan bo‘lsa, eslatma keladi." if d else "Muddat o‘chirildi.", "success")
        return redirect(url_for("opportunity", oid=oid))

    @app.route("/opportunity/<int:oid>/letter", methods=["POST"])
    @login_required
    def app_letter(oid):
        opp = opp_or_404(oid)
        db = get_db()
        text = clean(request.form.get("letter"), 6000)
        if request.form.get("action") == "reset":
            text = make_letter(g.user, opp)
        upsert_app(db, g.user["id"], oid, letter=text)
        db.commit()
        flash("Xat saqlandi.", "success")
        return redirect(url_for("opportunity", oid=oid) + "#xat")

    # ---------- ariza doskasi ----------
    @app.route("/my")
    @login_required
    def board():
        db = get_db()
        rows = db.execute("""SELECT a.status, a.deadline adl, a.updated_at, o.* FROM applications a
                             JOIN opportunities o ON o.id=a.opp_id WHERE a.user_id=? ORDER BY a.updated_at DESC""",
                          (g.user["id"],)).fetchall()
        # eski "saqlanganlar" ham doskaga tushsin
        old = db.execute("""SELECT s.opp_id FROM saved s WHERE s.user_id=? AND s.opp_id NOT IN
                            (SELECT opp_id FROM applications WHERE user_id=?)""", (g.user["id"], g.user["id"])).fetchall()
        if old:
            for r in old:
                db.execute("INSERT OR IGNORE INTO applications(user_id, opp_id, updated_at) VALUES (?,?,?)",
                           (g.user["id"], r["opp_id"], now_ts()))
            db.commit()
            return redirect(url_for("board"))
        cols = {k: [] for k, _ in BOARD_COLUMNS}
        soon = []
        for r in rows:
            d = parse_day(r["adl"]) or parse_day(r["deadline"])
            left = days_left(d)
            m, _ = match_score(g.user, r)
            card = {"id": r["id"], "title": r["title"], "category": r["category"], "status": r["status"],
                    "deadline": d, "left": left, "match": m,
                    "docs": doc_checklist(db, g.user["id"], r) if r["status"] == "preparing" else None}
            if card["docs"] is not None:
                card["docs_have"] = sum(1 for x in card["docs"] if x["have"])
                card["docs_pct"] = int(card["docs_have"] * 100 / max(1, len(card["docs"]))) // 5 * 5
            cols["result" if r["status"] in ("accepted", "rejected") else r["status"]].append(card)
            if left is not None and left >= 0 and r["status"] in ("saved", "preparing"):
                soon.append(card)
        soon.sort(key=lambda c: c["left"])
        stats = user_stats(db, g.user["id"])
        stats["soon"] = sum(1 for c in soon if c["left"] <= 7)
        return render_template("board.html", cols=cols, columns=BOARD_COLUMNS, soon=soon[:4], stats=stats,
                               statuses=STATUSES, tab="board")

    # ---------- taqvim ----------
    @app.route("/my/calendar")
    @login_required
    def calendar_view():
        t = today()
        try:
            y, m = int(request.args.get("y", t.year)), int(request.args.get("m", t.month))
            first = date(y, m, 1)
        except ValueError:
            first = date(t.year, t.month, 1)
        db = get_db()
        events = {}
        for r in db.execute("""SELECT a.status, a.deadline adl, o.id, o.title, o.category, o.deadline FROM applications a
                               JOIN opportunities o ON o.id=a.opp_id WHERE a.user_id=?""", (g.user["id"],)):
            d = parse_day(r["adl"]) or parse_day(r["deadline"])
            if d:
                urgent = r["status"] in ("saved", "preparing") and 0 <= (d - t).days <= 3
                events.setdefault(d, []).append({"id": r["id"], "title": r["title"], "category": r["category"],
                                                 "urgent": urgent, "status": r["status"]})
        prev_m = (first - timedelta(days=1)).replace(day=1)
        next_m = (first + timedelta(days=32)).replace(day=1)
        upcoming = sorted([(d, e) for d, evs in events.items() for e in evs if d >= t], key=lambda x: x[0])[:5]
        return render_template("calendar.html", weeks=month_grid(first.year, first.month), first=first,
                               month_name=f"{UZ_MONTHS[first.month]} {first.year}", events=events, today=t,
                               prev_m=prev_m, next_m=next_m, upcoming=upcoming, tab="calendar")

    # ---------- hujjatlar ----------
    @app.route("/my/documents", methods=["GET", "POST"])
    @login_required
    def documents():
        db = get_db()
        if request.method == "POST":
            f = request.files.get("file")
            kind = request.form.get("kind")
            title = clean(request.form.get("title"), 80)
            count = db.execute("SELECT COUNT(*) FROM documents WHERE user_id=?", (g.user["id"],)).fetchone()[0]
            ext = (f.filename.rsplit(".", 1)[-1].lower() if f and "." in f.filename else "")
            if kind not in DOC_LABEL:
                flash("Hujjat turini tanlang.", "error")
            elif not f or not f.filename:
                flash("Faylni tanlang.", "error")
            elif ext not in ALLOWED_EXT:
                flash("Faqat PDF, JPG, PNG, DOC, DOCX fayllar qabul qilinadi.", "error")
            elif count >= MAX_DOCS:
                flash(f"Ko‘pi bilan {MAX_DOCS} ta hujjat saqlash mumkin.", "error")
            else:
                folder = UPLOAD_DIR / str(g.user["id"])
                folder.mkdir(parents=True, exist_ok=True)
                stored = f"{secrets.token_hex(12)}.{ext}"
                f.save(folder / stored)
                size = (folder / stored).stat().st_size
                cur = db.execute("INSERT INTO documents(user_id, kind, title, stored, size, created_at) VALUES (?,?,?,?,?,?)",
                                 (g.user["id"], kind, title or DOC_LABEL[kind][1], stored, size, now_ts()))
                award(db, g.user["id"], "doc", cur.lastrowid)
                db.commit()
                flash("Hujjat yuklandi. +5 ball", "success")
            return redirect(url_for("documents"))
        docs = db.execute("SELECT * FROM documents WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
        have = {d["kind"] for d in docs}
        return render_template("documents.html", docs=docs, kinds=DOC_KINDS, doc_label=DOC_LABEL, have=have, tab="docs")

    @app.route("/my/documents/<int:did>")
    @login_required
    def document_file(did):
        d = get_db().execute("SELECT * FROM documents WHERE id=? AND user_id=?", (did, g.user["id"])).fetchone()
        if d is None:
            abort(404)
        ext = d["stored"].rsplit(".", 1)[-1]
        safe_title = re.sub(r"[^\w.-]+", "_", d["title"])[:60]
        return send_from_directory(UPLOAD_DIR / str(g.user["id"]), d["stored"], as_attachment=True,
                                   download_name=f"{safe_title}.{ext}")

    @app.route("/my/documents/<int:did>/delete", methods=["POST"])
    @login_required
    def document_delete(did):
        db = get_db()
        d = db.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (did, g.user["id"])).fetchone()
        if d:
            try:
                (UPLOAD_DIR / str(g.user["id"]) / d["stored"]).unlink()
            except OSError:
                pass
            db.execute("DELETE FROM documents WHERE id=?", (did,))
            db.commit()
            flash("Hujjat o‘chirildi.", "info")
        return redirect(url_for("documents"))

    # ---------- yutuqlar ----------
    @app.route("/my/achievements")
    @login_required
    def achievements():
        db = get_db()
        history = db.execute("SELECT * FROM points WHERE user_id=? ORDER BY id DESC LIMIT 15", (g.user["id"],)).fetchall()
        return render_template("achievements.html", badges=user_badges(db, g.user), history=history,
                               points_table=POINTS, action_label=ACTION_LABEL, tab="achievements")

    # ---------- jamoa topish ----------
    @app.route("/teams", methods=["GET", "POST"])
    def teams():
        db = get_db()
        if request.method == "POST":
            if not g.user:
                return redirect(url_for("login", next=url_for("teams")))
            body = clean(request.form.get("body"), 600)
            kind = "seek" if request.form.get("kind") == "seek" else "team"
            if len(body) < 15:
                flash("E’lonni batafsilroq yozing (kamida 15 belgi).", "error")
                return redirect(url_for("teams"))
            try:
                members = max(1, min(10, int(request.form.get("members", 1))))
                size = max(members, min(12, int(request.form.get("size", 4))))
            except ValueError:
                members, size = 1, 4
            opp_id = request.form.get("opp_id", type=int)
            if opp_id and not db.execute("SELECT 1 FROM opportunities WHERE id=?", (opp_id,)).fetchone():
                opp_id = None
            needs = ", ".join(x.strip() for x in clean(request.form.get("needs"), 150).split(",") if x.strip())
            cur = db.execute("""INSERT INTO team_posts(user_id, kind, event, opp_id, body, needs, members, size, created_at)
                                VALUES (?,?,?,?,?,?,?,?,?)""",
                             (g.user["id"], kind, clean(request.form.get("event"), 100), opp_id, body, needs, members, size, now_ts()))
            if not g.user["telegram"]:
                flash("E’lon joylandi. Sizga yozishlari uchun profilda Telegram username’ingizni kiriting.", "info")
            else:
                flash("E’lon joylandi! +30 ball", "success")
            award(db, g.user["id"], "team", "first")
            db.commit()
            return redirect(url_for("teams"))
        kind = request.args.get("kind", "")
        sql = """SELECT t.*, u.name, u.avatar, u.telegram, u.major, u.university FROM team_posts t JOIN users u ON u.id=t.user_id
                 WHERE t.is_open=1"""
        args = []
        if kind in ("team", "seek"):
            sql += " AND t.kind=?"
            args.append(kind)
        posts = db.execute(sql + " ORDER BY t.id DESC LIMIT 60", args).fetchall()
        badges = user_badges(db, g.user) if g.user else []
        prefill_opp = None
        if request.args.get("opp", type=int):
            prefill_opp = db.execute("SELECT id, title FROM opportunities WHERE id=?", (request.args.get("opp", type=int),)).fetchone()
        return render_template("teams.html", posts=posts, kind=kind, badges=badges, prefill_opp=prefill_opp,
                               show_form=bool(request.args.get("new")))

    @app.route("/teams/<int:pid>/close", methods=["POST"])
    @login_required
    def team_close(pid):
        db = get_db()
        db.execute("UPDATE team_posts SET is_open=0 WHERE id=? AND user_id=?", (pid, g.user["id"]))
        db.commit()
        flash("E’lon yopildi.", "info")
        return redirect(url_for("teams"))

    # ---------- reyting ----------
    @app.route("/rating")
    def rating():
        db = get_db()
        period = request.args.get("p", "week")
        scope = request.args.get("s", "all")
        since = {"week": 7, "month": 30}.get(period)
        where, args = [], []
        if since:
            where.append("p.created_at >= ?")
            args.append(sources.fmt_ts(sources.now_utc() - timedelta(days=since)))
        if scope == "uni" and g.user and g.user["university"]:
            where.append("u.university = ?")
            args.append(g.user["university"])
        if scope == "region" and g.user and g.user["region"]:
            where.append("u.region = ?")
            args.append(g.user["region"])
        sql = f"""SELECT u.id, u.name, u.avatar, u.university, u.slug, u.portfolio_public, SUM(p.amount) pts
                  FROM points p JOIN users u ON u.id=p.user_id {('WHERE ' + ' AND '.join(where)) if where else ''}
                  GROUP BY u.id ORDER BY pts DESC, u.id LIMIT 50"""
        rows = db.execute(sql, args).fetchall()
        me = None
        if g.user:
            for i, r in enumerate(rows):
                if r["id"] == g.user["id"]:
                    me = {"rank": i + 1, "pts": r["pts"]}
        return render_template("rating.html", rows=rows, period=period, scope=scope, me=me, points_table=POINTS)

    # ---------- hamjamiyat ----------
    @app.route("/community", methods=["GET", "POST"])
    def community():
        db = get_db()
        if request.method == "POST":
            if not g.user:
                return redirect(url_for("login", next=url_for("community")))
            title = clean(request.form.get("title"), 160)
            channel = request.form.get("channel") if request.form.get("channel") in CHANNEL_LABEL else "umumiy"
            if len(title) < 10:
                flash("Savolni to‘liqroq yozing (kamida 10 belgi).", "error")
                return redirect(url_for("community", c=channel))
            cur = db.execute("INSERT INTO questions(user_id, channel, title, body, created_at) VALUES (?,?,?,?,?)",
                             (g.user["id"], channel, title, clean(request.form.get("body"), 2000), now_ts()))
            award(db, g.user["id"], "question", cur.lastrowid)
            db.commit()
            try:
                import telegram_bot
                telegram_bot.post_question_to_group(title, channel, url_for("question", qid=cur.lastrowid, _external=True))
            except Exception:
                pass
            flash("Savolingiz joylandi.", "success")
            return redirect(url_for("question", qid=cur.lastrowid))
        channel = request.args.get("c", "")
        sort = request.args.get("sort", "top")
        sql = """SELECT q.*, u.name, u.avatar,
                    (SELECT COUNT(*) FROM votes v WHERE v.question_id=q.id) score,
                    (SELECT COUNT(*) FROM answers a WHERE a.question_id=q.id) n_ans,
                    (SELECT COUNT(*) FROM answers a WHERE a.question_id=q.id AND a.helpful=1) n_help
                 FROM questions q JOIN users u ON u.id=q.user_id"""
        args = []
        if channel in CHANNEL_LABEL:
            sql += " WHERE q.channel=?"
            args.append(channel)
        sql += " ORDER BY score DESC, q.id DESC" if sort == "top" else " ORDER BY q.id DESC"
        qs = db.execute(sql + " LIMIT 50", args).fetchall()
        counts = dict(db.execute("SELECT channel, COUNT(*) FROM questions GROUP BY channel").fetchall())
        helpers = db.execute("""SELECT u.name, u.avatar, COUNT(*) n FROM answers a JOIN users u ON u.id=a.user_id
                                WHERE a.helpful=1 GROUP BY u.id ORDER BY n DESC LIMIT 3""").fetchall()
        voted = set()
        if g.user:
            voted = {r[0] for r in db.execute("SELECT question_id FROM votes WHERE user_id=?", (g.user["id"],))}
        return render_template("community.html", qs=qs, channels=CHANNELS, channel=channel, counts=counts,
                               helpers=helpers, voted=voted, sort=sort, channel_label=CHANNEL_LABEL)

    @app.route("/community/<int:qid>", methods=["GET", "POST"])
    def question(qid):
        db = get_db()
        q = db.execute("""SELECT q.*, u.name, u.avatar, (SELECT COUNT(*) FROM votes v WHERE v.question_id=q.id) score
                          FROM questions q JOIN users u ON u.id=q.user_id WHERE q.id=?""", (qid,)).fetchone()
        if q is None:
            abort(404)
        if request.method == "POST":
            if not g.user:
                return redirect(url_for("login", next=url_for("question", qid=qid)))
            body = clean(request.form.get("body"), 3000)
            if len(body) < 5:
                flash("Javob juda qisqa.", "error")
            else:
                cur = db.execute("INSERT INTO answers(question_id, user_id, body, created_at) VALUES (?,?,?,?)",
                                 (qid, g.user["id"], body, now_ts()))
                if g.user["id"] != q["user_id"]:
                    award(db, g.user["id"], "answer", cur.lastrowid)
                db.commit()
                flash("Javobingiz uchun rahmat!", "success")
            return redirect(url_for("question", qid=qid))
        answers = db.execute("""SELECT a.*, u.name, u.avatar, u.university FROM answers a JOIN users u ON u.id=a.user_id
                                WHERE a.question_id=? ORDER BY a.helpful DESC, a.id""", (qid,)).fetchall()
        voted = bool(g.user and db.execute("SELECT 1 FROM votes WHERE user_id=? AND question_id=?", (g.user["id"], qid)).fetchone())
        return render_template("question.html", q=q, answers=answers, voted=voted, channel_label=CHANNEL_LABEL)

    @app.route("/community/<int:qid>/vote", methods=["POST"])
    @login_required
    def question_vote(qid):
        db = get_db()
        if db.execute("SELECT 1 FROM votes WHERE user_id=? AND question_id=?", (g.user["id"], qid)).fetchone():
            db.execute("DELETE FROM votes WHERE user_id=? AND question_id=?", (g.user["id"], qid))
        elif db.execute("SELECT 1 FROM questions WHERE id=?", (qid,)).fetchone():
            db.execute("INSERT INTO votes(user_id, question_id) VALUES (?,?)", (g.user["id"], qid))
        db.commit()
        return redirect(h.safe_next(request.form.get("next")))

    @app.route("/community/answer/<int:aid>/helpful", methods=["POST"])
    @login_required
    def answer_helpful(aid):
        db = get_db()
        a = db.execute("""SELECT a.*, q.user_id owner FROM answers a JOIN questions q ON q.id=a.question_id
                          WHERE a.id=?""", (aid,)).fetchone()
        if a is None or a["owner"] != g.user["id"]:
            abort(403)
        db.execute("UPDATE answers SET helpful = 1 - helpful WHERE id=?", (aid,))
        if not a["helpful"] and a["user_id"] != g.user["id"]:
            award(db, a["user_id"], "helpful", aid)
        db.commit()
        return redirect(url_for("question", qid=a["question_id"]))

    # ---------- g'oliblar ----------
    @app.route("/winners", methods=["GET", "POST"])
    def winners():
        db = get_db()
        if request.method == "POST":
            if not g.user:
                return redirect(url_for("login", next=url_for("winners")))
            cat = request.form.get("category")
            ach = clean(request.form.get("achievement"), 120)
            tip = clean(request.form.get("tip"), 400)
            if cat not in STORY_LABEL or len(ach) < 5 or len(tip) < 15:
                flash("Turini tanlang, nimani yutganingizni va kamida bitta maslahat yozing.", "error")
            else:
                cur = db.execute("INSERT INTO stories(user_id, category, achievement, tip, created_at) VALUES (?,?,?,?,?)",
                                 (g.user["id"], cat, ach, tip, now_ts()))
                award(db, g.user["id"], "story", cur.lastrowid)
                db.execute("""INSERT INTO portfolio_items(user_id, kind, title, description, year, created_at)
                              VALUES (?,?,?,?,?,?)""", (g.user["id"], "award", ach, tip, str(today().year), now_ts()))
                db.commit()
                flash("Tajribangiz uchun rahmat! +40 ball. Yutuq portfoliongizga ham qo‘shildi.", "success")
            return redirect(url_for("winners"))
        cat = request.args.get("c", "")
        sql = """SELECT s.*, u.name, u.avatar, u.university, u.slug, u.portfolio_public,
                    (SELECT COUNT(*) FROM answers a WHERE a.user_id=s.user_id) n_ans
                 FROM stories s JOIN users u ON u.id=s.user_id"""
        args = []
        if cat in STORY_LABEL:
            sql += " WHERE s.category=?"
            args.append(cat)
        stories = db.execute(sql + " ORDER BY s.id DESC LIMIT 30", args).fetchall()
        return render_template("winners.html", stories=stories, cats=STORY_CATS, story_label=STORY_LABEL, cat=cat,
                               show_form=bool(request.args.get("new")))

    # ---------- portfolio ----------
    @app.route("/portfolio", methods=["GET", "POST"])
    @login_required
    def portfolio_edit():
        db = get_db()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "settings":
                db.execute("UPDATE users SET bio=?, portfolio_public=?, avatar=? WHERE id=?",
                           (clean(request.form.get("bio"), 300), 1 if request.form.get("public") else 0,
                            request.form.get("avatar") if request.form.get("avatar") in AVATARS else g.user["avatar"],
                            g.user["id"]))
                if not g.user["slug"]:
                    make_slug(db, g.user)
                flash("Portfolio sozlamalari saqlandi.", "success")
            elif action == "add":
                kind = request.form.get("kind")
                title = clean(request.form.get("title"), 120)
                link = clean(request.form.get("link"), 300)
                if link and not link.startswith(("http://", "https://")):
                    link = "https://" + link
                try:
                    hours = max(0, min(2000, int(request.form.get("hours") or 0)))
                except ValueError:
                    hours = 0
                if kind not in PORTFOLIO_LABEL or len(title) < 3:
                    flash("Turini tanlang va nomini yozing.", "error")
                else:
                    cur = db.execute("""INSERT INTO portfolio_items(user_id, kind, title, description, link, hours, year, created_at)
                                        VALUES (?,?,?,?,?,?,?,?)""",
                                     (g.user["id"], kind, title, clean(request.form.get("description"), 500), link,
                                      hours, clean(request.form.get("year"), 9), now_ts()))
                    award(db, g.user["id"], "portfolio", cur.lastrowid)
                    flash("Portfolioga qo‘shildi! +10 ball", "success")
            elif action == "delete":
                db.execute("DELETE FROM portfolio_items WHERE id=? AND user_id=?",
                           (request.form.get("id", type=int), g.user["id"]))
                flash("O‘chirildi.", "info")
            db.commit()
            return redirect(url_for("portfolio_edit"))
        if not g.user["slug"]:
            make_slug(db, g.user)
            db.commit()
            return redirect(url_for("portfolio_edit"))
        items = db.execute("SELECT * FROM portfolio_items WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
        return render_template("portfolio_edit.html", items=items, kinds=PORTFOLIO_KINDS, plabel=PORTFOLIO_LABEL,
                               avatars=AVATARS)

    @app.route("/p/<slug>")
    def portfolio_public(slug):
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE slug=?", (slug,)).fetchone()
        if u is None or (not u["portfolio_public"] and not (g.user and g.user["id"] == u["id"])):
            abort(404)
        items = db.execute("SELECT * FROM portfolio_items WHERE user_id=? ORDER BY kind, id DESC", (u["id"],)).fetchall()
        accepted = db.execute("""SELECT o.title, o.category, a.updated_at FROM applications a JOIN opportunities o ON o.id=a.opp_id
                                 WHERE a.user_id=? AND a.status='accepted' ORDER BY a.updated_at DESC""", (u["id"],)).fetchall()
        pts = user_points(db, u["id"])
        grouped = {}
        for it in items:
            grouped.setdefault(it["kind"], []).append(it)
        return render_template("portfolio.html", u=u, grouped=grouped, kinds=PORTFOLIO_KINDS, accepted=accepted,
                               stats=user_stats(db, u["id"]), badges=user_badges(db, u), pts=pts, lvl=level_info(pts),
                               direction=DIRECTIONS.get(u["direction"]), own=bool(g.user and g.user["id"] == u["id"]))

    # ---------- yo'lingni top ----------
    @app.route("/path", methods=["GET", "POST"])
    def path_test():
        if request.method == "POST":
            scores = {k: 0 for k in DIRECTIONS}
            answered = 0
            for i in range(len(TEST_QUESTIONS)):
                v = request.form.get(f"q{i}")
                if v in scores:
                    scores[v] += 1
                    answered += 1
            if answered < len(TEST_QUESTIONS) - 2:
                flash("Iltimos, deyarli barcha savollarga javob bering.", "error")
                return redirect(url_for("path_test"))
            best = sorted(scores.items(), key=lambda x: -x[1])
            top, second = best[0][0], best[1][0]
            if g.user:
                db = get_db()
                db.execute("UPDATE users SET direction=? WHERE id=?", (top, g.user["id"]))
                award(db, g.user["id"], "test", "first")
                db.commit()
            return redirect(url_for("path_result", d=top, d2=second))
        return render_template("path_test.html", questions=TEST_QUESTIONS)

    @app.route("/path/result")
    def path_result():
        d = request.args.get("d") or (g.user["direction"] if g.user else "")
        if d not in DIRECTIONS:
            return redirect(url_for("path_test"))
        d2 = request.args.get("d2")
        return render_template("path_result.html", key=d, d=DIRECTIONS[d],
                               second=DIRECTIONS.get(d2) if d2 in DIRECTIONS and d2 != d else None,
                               second_key=d2, topic_map=h.TOPIC_MAP)

    # ---------- Telegram ulash ----------
    @app.route("/telegram", methods=["GET", "POST"])
    @login_required
    def telegram_link():
        import telegram_bot
        db = get_db()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "settings":
                db.execute("UPDATE users SET reminders_on=?, digest_on=? WHERE id=?",
                           (1 if request.form.get("reminders") else 0, 1 if request.form.get("digest") else 0, g.user["id"]))
                flash("Sozlamalar saqlandi.", "success")
            elif action == "unlink":
                db.execute("UPDATE users SET tg_chat_id='' WHERE id=?", (g.user["id"],))
                flash("Telegram uzildi.", "info")
            db.commit()
            return redirect(url_for("telegram_link"))
        code = g.user["tg_code"]
        if not code:
            code = secrets.token_hex(6)
            db.execute("UPDATE users SET tg_code=? WHERE id=?", (code, g.user["id"]))
            db.commit()
        return render_template("telegram.html", code=code, bot=telegram_bot.bot_username(),
                               enabled=telegram_bot.enabled())
