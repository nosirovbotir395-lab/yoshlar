import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import webbrowser
import threading
import html
import re
import hashlib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse, parse_qs, unquote
import xml.etree.ElementTree as ET

# ============================================================
# YOSHLAR HUB — Live Edition
# Yoshlar uchun grant, kurs, tanlov, ish va volunteer imkoniyatlari
#
# Real vaqt rejimi:
#   * Dastur ochilganda va keyin har AUTO_REFRESH_MINUTES daqiqada
#     RSS manbalardan (Google News, Bing News, o'zingiz qo'shgan feedlar)
#     yangi imkoniyatlarni avtomatik oladi.
#   * Yangi topilganlar "YANGI" belgisi bilan chiqadi.
#   * Muddati o'tgan va eskirgan natijalar avtomatik tozalanadi.
# ============================================================

DATA_FILE = Path(__file__).with_name("yoshlar_hub_data.json")

# ----------------------- SOZLAMALAR -----------------------
AUTO_REFRESH_MINUTES = 15     # avtomatik yangilash oralig'i
MAX_ITEMS = 200               # ro'yxatda saqlanadigan maksimal imkoniyat
MAX_AGE_DAYS = 60             # bundan eski web natijalar o'chiriladi
REQUEST_TIMEOUT = 10          # soniya

# O'zingizning RSS/Atom manbalaringiz. Ularni dastur ichidagi "Manbalar" bo'limidan
# qo'shish yoki o'chirish mumkin (fayl yoshlar_hub_data.json ga saqlanadi).
# Xohlasangiz bu yerga ham yozishingiz mumkin:
# USER_FEEDS = [("Sayt nomi", "https://example.uz/rss.xml")]
# Bu manbalardan kelgan hamma yozuv ko'rsatiladi (kalit so'z filtri qo'llanmaydi).
USER_FEEDS = []

SRC_SEARCH = "Web qidiruv"
SRC_MANUAL = "Qo‘lda qo‘shilgan"
SRC_OFFICIAL = "Rasmiy manba (gov.uz)"

# ----------------------- RANGLAR -----------------------
BG = "#F5F7FA"
WHITE = "#FFFFFF"
TEXT = "#172B4D"
MUTED = "#667085"
PRIMARY = "#155EEF"
PRIMARY_DARK = "#1248C0"
GREEN = "#12B76A"
ORANGE = "#F79009"
PURPLE = "#7F56D9"
BORDER = "#E4E7EC"
SOFT_BLUE = "#EEF4FF"
SOFT_GREEN = "#ECFDF3"
SOFT_ORANGE = "#FFFAEB"
SOFT_PURPLE = "#F9F5FF"

CATEGORIES = [
    "Barchasi", "Grantlar", "Ish va internship",
    "Tanlovlar", "Kurslar", "Volunteer", "Tadbirlar"
]

# Internet bo'lmasa ham dastur ishlashi uchun boshlang'ich havolalar.
OFFICIAL_SOURCES = [
    {
        "id": 1,
        "title": "Yoshlar uchun grant va tanlovlar",
        "category": "Grantlar",
        "location": "O‘zbekiston",
        "type": "Grant / tanlov",
        "deadline": "Manbada tekshiriladi",
        "fields": ["Yoshlar", "Loyiha", "Innovatsiya"],
        "link": "https://www.google.com/search?q=O%27zbekiston+yoshlar+grant+tanlov",
        "source": SRC_SEARCH,
        "published": "",
        "description": "O‘zbekiston yoshlari uchun grant, loyiha va tanlov imkoniyatlarini web orqali topish uchun boshlang‘ich manba."
    },
    {
        "id": 2,
        "title": "Talabalar uchun internship imkoniyatlari",
        "category": "Ish va internship",
        "location": "O‘zbekiston / Online",
        "type": "Internship",
        "deadline": "Manbada tekshiriladi",
        "fields": ["Talabalar", "Internship", "Ish"],
        "link": "https://www.google.com/search?q=Uzbekistan+students+internship",
        "source": SRC_SEARCH,
        "published": "",
        "description": "Talabalar va yoshlar uchun amaliyot hamda boshlang‘ich ish imkoniyatlarini topish uchun qidiruv manbasi."
    },
    {
        "id": 3,
        "title": "IT va raqamli ko‘nikmalar kurslari",
        "category": "Kurslar",
        "location": "Online",
        "type": "Kurs",
        "deadline": "Doimiy",
        "fields": ["IT", "Dasturlash", "Raqamli ko‘nikmalar"],
        "link": "https://www.google.com/search?q=Uzbekistan+free+IT+courses+youth",
        "source": SRC_SEARCH,
        "published": "",
        "description": "IT, dasturlash va raqamli ko‘nikmalar bo‘yicha bepul yoki ochiq kurslarni topish uchun qidiruv manbasi."
    },
    {
        "id": 4,
        "title": "Yoshlar uchun volunteer imkoniyatlari",
        "category": "Volunteer",
        "location": "O‘zbekiston / Online",
        "type": "Volunteer",
        "deadline": "Manbada tekshiriladi",
        "fields": ["Volunteer", "Ijtimoiy loyiha", "Yoshlar"],
        "link": "https://www.google.com/search?q=Uzbekistan+youth+volunteer+opportunities",
        "source": SRC_SEARCH,
        "published": "",
        "description": "Yoshlar uchun ko‘ngillilik va ijtimoiy loyihalardagi imkoniyatlarni topish uchun qidiruv manbasi."
    },
    {
        "id": 5,
        "title": "Yoshlar tanlovlari va hackathonlar",
        "category": "Tanlovlar",
        "location": "O‘zbekiston / Online",
        "type": "Tanlov",
        "deadline": "Manbada tekshiriladi",
        "fields": ["Hackathon", "Startap", "Innovatsiya"],
        "link": "https://www.google.com/search?q=Uzbekistan+youth+hackathon+competition",
        "source": SRC_SEARCH,
        "published": "",
        "description": "Hackathon, startap, innovatsion va yoshlar tanlovlarini topish uchun qidiruv manbasi."
    },
    {
        "id": 6,
        "title": "Yoshlar ishlari agentligi — Imkoniyatlar",
        "category": "Tanlovlar",
        "location": "O‘zbekiston",
        "type": "Rasmiy bo‘lim",
        "deadline": "Sahifada tekshiriladi",
        "fields": ["Yoshlar", "Imkoniyatlar"],
        "link": "https://gov.uz/oz/yoshlar/sections/imkoniyatlar",
        "source": SRC_OFFICIAL,
        "published": "",
        "description": "Yoshlar ishlari agentligining rasmiy “Imkoniyatlar” bo‘limi. Yangi e’lonlarni shu sahifada tekshiring."
    },
    {
        "id": 7,
        "title": "Yoshlar ishlari agentligi — Tanlovlar",
        "category": "Tanlovlar",
        "location": "O‘zbekiston",
        "type": "Rasmiy bo‘lim",
        "deadline": "Sahifada tekshiriladi",
        "fields": ["Yoshlar", "Tanlov"],
        "link": "https://gov.uz/oz/yoshlar/contest",
        "source": SRC_OFFICIAL,
        "published": "",
        "description": "Agentlik e’lon qilgan tanlovlar ro‘yxati (rasmiy sahifa)."
    },
    {
        "id": 8,
        "title": "Yoshlar ishlari agentligi — Bo‘sh ish o‘rinlari",
        "category": "Ish va internship",
        "location": "O‘zbekiston",
        "type": "Rasmiy bo‘lim",
        "deadline": "Sahifada tekshiriladi",
        "fields": ["Ish", "Yoshlar"],
        "link": "https://gov.uz/oz/yoshlar/sections/vakansiya",
        "source": SRC_OFFICIAL,
        "published": "",
        "description": "Agentlik va uning tizimidagi tashkilotlarning rasmiy vakansiyalar sahifasi."
    },
    {
        "id": 9,
        "title": "Yoshlar ishlari agentligi — Voqealar taqvimi",
        "category": "Tadbirlar",
        "location": "O‘zbekiston",
        "type": "Rasmiy bo‘lim",
        "deadline": "Sahifada tekshiriladi",
        "fields": ["Yoshlar", "Tadbir"],
        "link": "https://gov.uz/oz/yoshlar/news/events",
        "source": SRC_OFFICIAL,
        "published": "",
        "description": "Yaqinlashayotgan yoshlar tadbirlari taqvimi (rasmiy sahifa)."
    }
]

DEFAULT_OPPORTUNITIES = [dict(x) for x in OFFICIAL_SOURCES]


# ============================================================
# MA'LUMOTLARNI SAQLASH
# ============================================================

def _load_feeds(data):
    """JSON dagi foydalanuvchi manbalarini USER_FEEDS ga qo'shadi (takrorsiz)."""
    known = {u for _, u in USER_FEEDS}
    for entry in data.get("feeds") or []:
        if (isinstance(entry, (list, tuple)) and len(entry) == 2
                and all(isinstance(x, str) for x in entry)
                and entry[1].startswith(("http://", "https://"))
                and entry[1] not in known):
            USER_FEEDS.append((entry[0], entry[1]))
            known.add(entry[1])


def _ensure_official(opportunities):
    """Rasmiy sahifalar eski saqlangan ma'lumotlarda ham doim bo'lsin."""
    links = {x.get("link", "").lower() for x in opportunities}
    for src in OFFICIAL_SOURCES:
        if src["link"].lower() not in links:
            opportunities.append(dict(src))


def load_data():
    if not DATA_FILE.exists():
        return [dict(x) for x in DEFAULT_OPPORTUNITIES], {}, []

    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        opportunities = data.get("opportunities") or [dict(x) for x in DEFAULT_OPPORTUNITIES]
        profile = data.get("profile") or {}
        saved = data.get("saved_ids") or []

        # Eski demo ma'lumotlar bo'lsa, rasmiy manbalar bilan almashtiriladi.
        demo_titles = {
            "Yoshlar innovatsion grant dasturi",
            "IT bo‘yicha bepul kurs",
            "Talabalar uchun logistika internshipi",
            "Yosh muhandislar loyihalar tanlovi",
            "Yosh tadbirkorlar granti",
            "Volunteerlar jamoasi",
            "Raqamli marketing bo‘yicha amaliy kurs",
            "Talabalar startaplar tanlovi"
        }
        if any(x.get("title") in demo_titles for x in opportunities):
            opportunities = [dict(x) for x in DEFAULT_OPPORTUNITIES]
            saved = []
        _load_feeds(data)
        _ensure_official(opportunities)
        return opportunities, profile, saved
    except Exception:
        return [dict(x) for x in DEFAULT_OPPORTUNITIES], {}, []


def save_data(opportunities, profile, saved_ids):
    data = {
        "opportunities": opportunities,
        "profile": profile,
        "saved_ids": list(saved_ids),
        "feeds": [list(f) for f in USER_FEEDS],
    }
    tmp = DATA_FILE.with_suffix(".tmp")
    # Avval vaqtinchalik faylga yozamiz: dastur o'chib qolsa ham fayl buzilmaydi.
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


# ============================================================
# MATN VA SANA YORDAMCHILARI
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_ts(value):
    """'YYYY-MM-DD HH:MM' yoki 'YYYY-MM-DD' ni UTC datetime ga aylantiradi."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime((value or "").strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ago(value):
    """Nashr vaqtini 'qancha oldin' ko'rinishida qaytaradi."""
    dt = parse_ts(value)
    if dt is None:
        return "manbada tekshiriladi"
    if len((value or "").strip()) <= 10:
        return value.strip()
    minutes = int((now_utc() - dt).total_seconds() // 60)
    if minutes < 1:
        return "hozirgina"
    if minutes < 60:
        return f"{minutes} daqiqa oldin"
    if minutes < 60 * 24:
        return f"{minutes // 60} soat oldin"
    days = minutes // (60 * 24)
    return f"{days} kun oldin" if days < 30 else value[:10]


def _clean_text(value):
    """HTML/XML matnini oddiy ko'rinishga keltiradi."""
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _norm(text):
    """Qidiruv uchun: kichik harf, har xil apostroflar bitta shaklga."""
    text = (text or "").lower()
    for ch in ("‘", "’", "ʻ", "ʼ", "`", "´"):
        text = text.replace(ch, "'")
    return text


def _title_key(title):
    return re.sub(r"\W+", "", _norm(title))[:140]


def _make_id(title, link):
    raw = f"{title}|{link}".encode("utf-8", errors="ignore")
    # Barqaror va JSON uchun qulay musbat ID.
    return int(hashlib.sha1(raw).hexdigest()[:12], 16)


def parse_feed_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ----------------------- Kategoriya / soha aniqlash -----------------------

CATEGORY_RULES = [
    ("Grantlar", "Grant",
     [r"\bgrants?\b", r"stipend", r"scholarship", r"fellowship", r"funding"]),
    ("Ish va internship", "Ish / internship",
     [r"internship", r"\bintern\b", r"vacanc", r"\bjobs?\b", r"\bcareers?\b",
      r"amaliyot", r"vakansiya", r"stajirovka", r"ish o'rin"]),
    ("Kurslar", "Kurs",
     [r"\bcourses?\b", r"\bkurs", r"training", r"academy", r"bootcamp",
      r"workshop", r"o'quv"]),
    ("Volunteer", "Volunteer",
     [r"volunteer", r"volontyor", r"ko'ngilli"]),
    ("Tadbirlar", "Tadbir",
     [r"\bevents?\b", r"tadbir", r"\bforum", r"summit", r"conference",
      r"konferensiya"]),
    ("Tanlovlar", "Tanlov",
     [r"competition", r"contest", r"hackathon", r"challenge", r"tanlov",
      r"konkurs", r"\bawards?\b", r"startup", r"startap"]),
]

FIELD_RULES = {
    "IT": [r"\bit\b", r"dasturlash", r"software", r"digital", r"raqamli",
           r"programming", r"\bai\b"],
    "Biznes": [r"business", r"biznes", r"entrepreneur", r"tadbirkor", r"startup", r"startap"],
    "Grant": [r"\bgrants?\b", r"funding", r"stipend"],
    "Talabalar": [r"student", r"talaba", r"universit"],
    "Yoshlar": [r"youth", r"yoshlar", r"young"],
    "Logistika": [r"logistic", r"logistika", r"supply chain"],
    "Marketing": [r"marketing", r"\bsmm\b"],
}


def classify(text):
    """(kategoriya, tur) yoki mos kelmasa None."""
    for category, typ, patterns in CATEGORY_RULES:
        if any(re.search(p, text) for p in patterns):
            return category, typ
    return None


def detect_fields(text):
    fields = [f for f, pats in FIELD_RULES.items()
              if any(re.search(p, text) for p in pats)]
    return fields or ["Yoshlar"]


# ----------------------- Deadline aniqlash -----------------------

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_DATE_PART = (
    r"(?:(20\d\d)-(\d{1,2})-(\d{1,2})"
    r"|(\d{1,2})\s+([a-z]{3,9})\.?,?\s+(20\d\d)"
    r"|([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d))"
)
_DEADLINE_RE = re.compile(
    r"(?:deadline|apply by|applications? (?:close|due)|closes?|closing|until|due|muddat\w*)"
    r"\W{0,20}" + _DATE_PART,
    re.I,
)


def extract_deadline(text):
    """Matn ichidan 'deadline: 15 October 2026' kabi sanani topadi -> 'YYYY-MM-DD' yoki None."""
    for m in _DEADLINE_RE.finditer(text or ""):
        g = m.groups()
        try:
            if g[0]:
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
            elif g[3]:
                d, mo, y = int(g[3]), _MONTHS.get(g[4].lower()), int(g[5])
            else:
                mo, d, y = _MONTHS.get(g[6].lower()), int(g[7]), int(g[8])
            if mo:
                return datetime(y, mo, d).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return None


# ============================================================
# WEB MANBALAR (RSS / Atom)
# ============================================================

def _http_get(url, timeout=REQUEST_TIMEOUT, limit=1_500_000):
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            "Accept-Language": "uz,en;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read(limit).decode("utf-8", errors="ignore")


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def parse_feed(xml_text):
    """RSS 2.0 va Atom feedni [{'title','link','description','published'}] ga aylantiradi."""
    if not xml_text or "<!DOCTYPE" in xml_text or "<!ENTITY" in xml_text:
        return []  # begona XML dagi entity hujumlaridan himoya
    try:
        root = ET.fromstring(xml_text.strip())
    except ET.ParseError:
        return []

    out = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        row = {"title": "", "link": "", "description": "", "published": None}
        for child in node:
            name = _local(child.tag)
            if name == "title":
                row["title"] = _clean_text(child.text)
            elif name == "link":
                row["link"] = (child.get("href") or child.text or "").strip()
            elif name in ("description", "summary", "content"):
                if not row["description"]:
                    row["description"] = _clean_text(child.text)
            elif name in ("pubDate", "published", "updated", "date"):
                if row["published"] is None:
                    row["published"] = parse_feed_date(child.text)
        if row["title"] and row["link"]:
            out.append(row)
    return out


def _unwrap_link(link):
    """Bing News havolasi ichidagi haqiqiy URL ni ajratib oladi."""
    try:
        parsed = urlparse(link)
        if "bing.com" in parsed.netloc:
            real = parse_qs(parsed.query).get("url")
            if real:
                return unquote(real[0])
    except Exception:
        pass
    return link


def _split_source(title):
    """Google News sarlavhasi 'Sarlavha - Nashr' ko'rinishida bo'ladi."""
    if " - " in title:
        head, tail = title.rsplit(" - ", 1)
        if 2 <= len(tail) <= 40:
            return head.strip(), tail.strip()
    return title, ""


def build_item(row, source_label, strict=True):
    """Feed yozuvini ilova formatiga o'tkazadi; mos kelmasa None."""
    title, publisher = _split_source(row["title"])
    desc = row["description"]
    if desc.strip().lower().startswith(title.strip().lower()[:40]):
        desc = ""  # Google News tavsifi ko'pincha sarlavhaning o'zi
    text = _norm(f"{title} {desc}")

    cls = classify(text)
    if cls is None:
        if strict:
            return None
        cls = ("Tanlovlar", "Imkoniyat")
    category, typ = cls

    deadline = extract_deadline(text)
    if deadline and deadline < now_utc().strftime("%Y-%m-%d"):
        return None  # muddati o'tgan

    link = _unwrap_link(row["link"])
    if not link.startswith(("http://", "https://")):
        return None

    published = row["published"] or now_utc()
    src = f"{publisher} ({source_label})" if publisher else source_label

    return {
        "id": _make_id(title, link),
        "title": title[:180],
        "category": category,
        "location": "O‘zbekiston / Online",
        "type": typ,
        "deadline": deadline or "Manbada tekshiriladi",
        "fields": detect_fields(text),
        "link": link,
        "source": src,
        "published": fmt_ts(published),
        "description": (desc or "Manba sahifasida batafsil o‘qing.")[:500],
        "seen": False,
    }


def _search_queries(interest=""):
    year = now_utc().year
    queries = [
        f"O'zbekiston yoshlar grant tanlov {year}",
        f"Uzbekistan youth grant opportunities {year}",
        f"Uzbekistan students internship {year}",
        f"Uzbekistan youth competition hackathon {year}",
        f"O'zbekiston bepul kurslar yoshlar {year}",
        f"Uzbekistan youth volunteer opportunities {year}",
    ]
    if interest:
        queries.insert(0, f"{interest} youth opportunities Uzbekistan {year}")
    return queries[:7]


def _feed_jobs(interest=""):
    """[(url, manba_nomi, strict)] — barcha so'rovlar ro'yxati."""
    jobs = []
    for q in _search_queries(interest):
        jobs.append((
            "https://news.google.com/rss/search?q=" + quote(q + " when:30d")
            + "&hl=en-US&gl=US&ceid=US:en",
            "Google News", True))
        jobs.append((
            "https://www.bing.com/news/search?q=" + quote(q) + "&format=rss",
            "Bing News", True))
    # Rasmiy gov.uz saytidan chiqqan yangiliklarni ham qidiramiz.
    jobs.append((
        "https://news.google.com/rss/search?q="
        + quote("site:gov.uz yoshlar tanlov grant stipendiya when:30d")
        + "&hl=en-US&gl=US&ceid=US:en",
        "gov.uz qidiruvi", True))
    for name, url in USER_FEEDS:
        jobs.append((url, name, False))
    return jobs


def _fetch_one(job):
    url, label, strict = job
    try:
        rows = parse_feed(_http_get(url))
    except Exception:
        return None, []
    items = []
    for row in rows[:25]:
        item = build_item(row, label, strict)
        if item:
            items.append(item)
    return True, items


def _ddg_fallback(query):
    """Zaxira: DuckDuckGo HTML. Bloklansa jimgina [] qaytaradi."""
    try:
        raw = _http_get("https://html.duckduckgo.com/html/?q=" + quote(query), timeout=8, limit=900_000)
    except Exception:
        return []
    items = []
    blocks = re.findall(r'<div class="result[^>]*>(.*?)(?=<div class="result|</body>)',
                        raw, flags=re.I | re.S)
    for block in blocks[:8]:
        href = re.search(r'class="result__a"[^>]+href="([^"]+)"', block, flags=re.I)
        ttl = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, flags=re.I | re.S)
        if not href or not ttl:
            continue
        link = html.unescape(href.group(1))
        if "uddg=" in link:
            qv = parse_qs(urlparse(link).query).get("uddg")
            if qv:
                link = unquote(qv[0])
        row = {
            "title": _clean_text(ttl.group(1)),
            "link": link,
            "description": _clean_text(snip.group(1) if snip else ""),
            "published": None,
        }
        item = build_item(row, "DuckDuckGo", strict=True)
        if item:
            items.append(item)
    return items


def fetch_real_opportunities(interest=""):
    """
    Barcha manbalarni parallel so'raydi.
    Qaytaradi: (natijalar, javob bergan_manbalar, jami_manbalar)
    """
    jobs = _feed_jobs(interest)
    results, seen_links, seen_titles = [], set(), set()
    ok = 0

    with ThreadPoolExecutor(max_workers=6) as pool:
        for status, items in pool.map(_fetch_one, jobs):
            if status:
                ok += 1
            for item in items:
                lk = item["link"].lower()
                tk_ = _title_key(item["title"])
                if lk in seen_links or tk_ in seen_titles:
                    continue
                seen_links.add(lk)
                seen_titles.add(tk_)
                results.append(item)

    # RSS umuman ishlamasa, zaxira usul
    if not results and ok == 0:
        for item in _ddg_fallback(_search_queries(interest)[0]):
            lk = item["link"].lower()
            if lk not in seen_links:
                seen_links.add(lk)
                results.append(item)

    results.sort(key=lambda x: x.get("published", ""), reverse=True)
    return results[:80], ok, len(jobs)


def merge_opportunities(existing, fresh, saved_ids):
    """
    Yangi natijalarni mavjud ro'yxatga qo'shadi. Qaytaradi: (yangi_ro'yxat, qo'shilgan_soni).
    * Saqlanganlar, qo'lda qo'shilganlar va qidiruv havolalari hech qachon o'chmaydi.
    * Eskirgan (MAX_AGE_DAYS) va muddati o'tgan web natijalar tozalanadi.
    * ID lar o'zgarmaydi, shuning uchun "Saqlanganlar" buzilmaydi.
    """
    today = now_utc().strftime("%Y-%m-%d")
    cutoff = now_utc() - timedelta(days=MAX_AGE_DAYS)

    def pinned(x):
        return x.get("id") in saved_ids or x.get("source") in (SRC_SEARCH, SRC_MANUAL, SRC_OFFICIAL, "Manual")

    kept = []
    for x in existing:
        if not pinned(x):
            dt = parse_ts(x.get("published", ""))
            if dt and dt < cutoff:
                continue
            dl = x.get("deadline", "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl or "") and dl < today:
                continue
        kept.append(x)

    known_links = {x.get("link", "").lower() for x in kept if x.get("link")}
    known_titles = {_title_key(x.get("title", "")) for x in kept}

    added = 0
    for item in fresh:
        if item["link"].lower() in known_links or _title_key(item["title"]) in known_titles:
            continue
        kept.append(item)
        known_links.add(item["link"].lower())
        known_titles.add(_title_key(item["title"]))
        added += 1

    kept.sort(key=lambda x: x.get("published", ""), reverse=True)

    if len(kept) > MAX_ITEMS:
        keep_pinned = [x for x in kept if pinned(x)]
        others = [x for x in kept if not pinned(x)][:max(0, MAX_ITEMS - len(keep_pinned))]
        kept = sorted(keep_pinned + others, key=lambda x: x.get("published", ""), reverse=True)
    return kept, added


# ============================================================
# ILOVA
# ============================================================

class YoshlarHub(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Yoshlar Hub")
        self.geometry("1180x760")
        self.minsize(1000, 650)
        self.configure(bg=BG)

        self.opportunities, self.profile, saved = load_data()
        self.saved_ids = set(saved)
        self.current_category = "Barchasi"
        self.current_page = "home"
        self.current_search = None
        self.refreshing = False
        self.status_label = None

        self.setup_style()
        self.build_shell()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_home()

    def on_close(self):
        try:
            save_data(self.opportunities, self.profile, self.saved_ids)
        except Exception:
            pass
        self.destroy()

    # ---------------------- HOLAT (STATUS) ----------------------

    def set_status(self, text, color=MUTED):
        """Chap paneldagi doimiy status. Sahifa almashsa ham xato bermaydi."""
        try:
            if self.status_label is not None:
                self.status_label.configure(text=text, fg=color)
        except tk.TclError:
            pass

    # ---------------------- UI CORE ----------------------

    def setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Hub.TCombobox",
            fieldbackground=WHITE,
            background=WHITE,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=7,
            font=("Segoe UI", 10)
        )

        style.map(
            "Hub.TCombobox",
            fieldbackground=[("readonly", WHITE)],
            foreground=[("readonly", TEXT)]
        )

    def build_shell(self):
        header = tk.Frame(self, bg=WHITE, height=70,
                          highlightbackground=BORDER, highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=WHITE)
        brand.pack(side="left", padx=25)

        logo = tk.Canvas(brand, width=38, height=38,
                         bg=WHITE, highlightthickness=0)
        logo.pack(side="left", padx=(0, 10))
        logo.create_oval(3, 3, 35, 35, fill=PRIMARY, outline="")
        logo.create_text(19, 19, text="Y", fill=WHITE,
                         font=("Segoe UI", 16, "bold"))

        tk.Label(
            brand, text="Yoshlar Hub",
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 17, "bold")
        ).pack(side="left")

        tk.Label(
            header,
            text="Imkoniyatlarni toping. O‘zingizni rivojlantiring.",
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=25)

        profile_name = self.profile.get("Ism", "").strip()
        user_text = profile_name if profile_name else "Profil"

        user = tk.Frame(header, bg=WHITE)
        user.pack(side="right", padx=25)

        tk.Label(
            user, text=user_text[:1].upper(),
            bg=SOFT_BLUE, fg=PRIMARY,
            width=3, height=1,
            font=("Segoe UI", 11, "bold")
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            user, text=user_text,
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 10, "bold")
        ).pack(side="left")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)

        sidebar = tk.Frame(main, bg=WHITE, width=230,
                           highlightbackground=BORDER,
                           highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="ASOSIY",
            bg=WHITE, fg="#98A2B3",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=20, pady=(25, 10))

        self.nav_buttons = {}

        nav = [
            ("home", "⌂", "Bosh sahifa", self.show_home),
            ("opportunities", "◈", "Imkoniyatlar", self.show_opportunities),
            ("recommended", "✦", "Menga mos", self.show_recommended),
            ("saved", "☆", "Saqlanganlar", self.show_saved),
        ]

        for key, icon, text, command in nav:
            self.add_nav_button(sidebar, key, icon, text, command)

        tk.Label(
            sidebar, text="SHAXSIY",
            bg=WHITE, fg="#98A2B3",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=20, pady=(25, 10))

        self.add_nav_button(
            sidebar, "profile", "○", "Mening profilim",
            self.show_profile
        )
        self.add_nav_button(
            sidebar, "add", "+", "Imkoniyat qo‘shish",
            self.add_opportunity
        )
        self.add_nav_button(
            sidebar, "sources", "⚙", "Manbalar",
            self.show_sources
        )

        # Doimiy "jonli" status
        tk.Frame(sidebar, bg=BORDER, height=1).pack(
            fill="x", padx=20, pady=(25, 12)
        )
        self.status_label = tk.Label(
            sidebar,
            text="● Internet manbalari ulanmoqda...",
            bg=WHITE, fg=MUTED,
            justify="left", anchor="w",
            wraplength=190,
            font=("Segoe UI", 8)
        )
        self.status_label.pack(anchor="w", padx=20, pady=(0, 8), fill="x")

        tk.Label(
            sidebar,
            text="Yoshlar Hub\nImkoniyatlar sizga yaqinroq.",
            bg=WHITE, fg=MUTED,
            justify="left",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=20)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

    def add_nav_button(self, parent, key, icon, text, command):
        btn = tk.Button(
            parent,
            text=f"  {icon}   {text}",
            command=command,
            anchor="w",
            bg=WHITE,
            fg="#475467",
            activebackground=SOFT_BLUE,
            activeforeground=PRIMARY,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            padx=14,
            pady=11,
            cursor="hand2"
        )
        btn.pack(fill="x", padx=10, pady=2)
        self.nav_buttons[key] = btn

    def set_active(self, key):
        for name, btn in self.nav_buttons.items():
            if name == key:
                btn.configure(bg=SOFT_BLUE, fg=PRIMARY,
                              font=("Segoe UI", 10, "bold"))
            else:
                btn.configure(bg=WHITE, fg="#475467",
                              font=("Segoe UI", 10))

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def heading(self, title, subtitle=""):
        wrap = tk.Frame(self.content, bg=BG)
        wrap.pack(fill="x", padx=35, pady=(30, 20))

        tk.Label(
            wrap, text=title,
            bg=BG, fg=TEXT,
            font=("Segoe UI", 24, "bold")
        ).pack(anchor="w")

        if subtitle:
            tk.Label(
                wrap, text=subtitle,
                bg=BG, fg=MUTED,
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=(5, 0))

    def button(self, parent, text, command,
               bg=PRIMARY, fg=WHITE, width=None):
        kwargs = dict(
            text=text, command=command,
            bg=bg, fg=fg,
            activebackground=PRIMARY_DARK if bg == PRIMARY else bg,
            activeforeground=fg,
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=14, pady=8,
            cursor="hand2"
        )
        if width:
            kwargs["width"] = width
        return tk.Button(parent, **kwargs)

    def new_badge(self, parent):
        tk.Label(
            parent, text="YANGI",
            bg=GREEN, fg=WHITE,
            font=("Segoe UI", 7, "bold"),
            padx=6, pady=2
        ).pack(side="left", padx=(6, 0))

    # ---------------------- HOME ----------------------

    def show_home(self):
        self.current_page = "home"
        self.current_search = None
        self.set_active("home")
        self.clear_content()

        self.heading(
            "Yangi imkoniyatlar shu yerdan boshlanadi",
            "Grantlar, kurslar, tanlovlar, internship va boshqa imkoniyatlarni bir joydan toping."
        )

        online_bar = tk.Frame(self.content, bg=BG)
        online_bar.pack(fill="x", padx=35, pady=(0, 12))

        tk.Label(
            online_bar,
            text=f"🌐 Avtomatik yangilanish: har {AUTO_REFRESH_MINUTES} daqiqada",
            bg=BG, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(side="left")

        self.button(
            online_bar, "↻ Hozir yangilash",
            lambda: self.refresh_online(manual=True),
            bg=GREEN
        ).pack(side="right")

        search_box = tk.Frame(
            self.content, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        search_box.pack(fill="x", padx=35, pady=(0, 22))

        tk.Label(
            search_box, text="⌕",
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 18)
        ).pack(side="left", padx=(16, 5))

        self.home_search = tk.Entry(
            search_box, bg=WHITE, fg=TEXT,
            relief="flat", bd=0,
            font=("Segoe UI", 11)
        )
        self.home_search.pack(
            side="left", fill="x", expand=True, pady=13
        )
        self.home_search.insert(
            0, "Nima izlayapsiz? Masalan: grant, logistika, IT..."
        )
        self.home_search.bind("<FocusIn>", self.clear_search_placeholder)
        self.home_search.bind("<Return>", lambda e: self.home_search_action())

        self.button(
            search_box, "Qidirish",
            self.home_search_action
        ).pack(side="right", padx=7, pady=6)

        stats = tk.Frame(self.content, bg=BG)
        stats.pack(fill="x", padx=35, pady=(0, 22))

        new_count = sum(1 for x in self.opportunities if not x.get("seen", True))
        stats_data = [
            ("Imkoniyatlar", len(self.opportunities), PRIMARY, SOFT_BLUE),
            ("Yangi", new_count, GREEN, SOFT_GREEN),
            ("Grantlar", self.count_category("Grantlar"), PURPLE, SOFT_PURPLE),
            ("Saqlangan", len(self.saved_ids), ORANGE, SOFT_ORANGE),
        ]

        for i, (label, value, color, soft) in enumerate(stats_data):
            card = tk.Frame(
                stats, bg=WHITE,
                highlightbackground=BORDER,
                highlightthickness=1
            )
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            stats.grid_columnconfigure(i, weight=1)

            tk.Label(
                card, text=str(value),
                bg=WHITE, fg=color,
                font=("Segoe UI", 21, "bold")
            ).pack(anchor="w", padx=17, pady=(13, 0))

            tk.Label(
                card, text=label,
                bg=WHITE, fg=MUTED,
                font=("Segoe UI", 9)
            ).pack(anchor="w", padx=17, pady=(0, 13))

        banner = tk.Frame(self.content, bg=PRIMARY)
        banner.pack(fill="x", padx=35, pady=(0, 22))

        left = tk.Frame(banner, bg=PRIMARY)
        left.pack(side="left", fill="both", expand=True, padx=24, pady=20)

        interest = self.profile.get("Qiziqish", "").strip()

        tk.Label(
            left,
            text="SIZ UCHUN TAVSIYA",
            bg=PRIMARY, fg="#BFD5FF",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w")

        if interest:
            banner_title = f"{interest} sohasiga mos imkoniyatlarni toping"
            banner_desc = "Profilingizdagi qiziqish asosida mos imkoniyatlar ajratib ko‘rsatiladi."
        else:
            banner_title = "Sohangizni kiriting va mos imkoniyatlarni toping"
            banner_desc = "Masalan: Logistika, IT, Marketing yoki Iqtisodiyot."

        tk.Label(
            left, text=banner_title,
            bg=PRIMARY, fg=WHITE,
            font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", pady=(5, 3))

        tk.Label(
            left, text=banner_desc,
            bg=PRIMARY, fg="#E1EAFF",
            font=("Segoe UI", 9)
        ).pack(anchor="w")

        self.button(
            banner, "Menga moslarini ko‘rsatish",
            self.show_recommended,
            bg=WHITE, fg=PRIMARY
        ).pack(side="right", padx=24, pady=28)

        self.section_title(
            self.content, "Yangi imkoniyatlar",
            "Eng so‘nggi topilgan imkoniyatlar"
        )

        latest = [x for x in self.opportunities if x.get("published")][:4] \
            or self.opportunities[:4]
        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="x", padx=35)

        for i, item in enumerate(latest):
            self.compact_card(grid, item, i)

    def clear_search_placeholder(self, event=None):
        if self.home_search.get().startswith("Nima izlayapsiz?"):
            self.home_search.delete(0, "end")

    def home_search_action(self):
        query = self.home_search.get().strip()
        if not query or query.startswith("Nima izlayapsiz?"):
            self.show_opportunities()
            return
        self.search_results(query)

    def section_title(self, parent, title, subtitle=""):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", padx=35, pady=(3, 12))

        tk.Label(
            wrap, text=title,
            bg=BG, fg=TEXT,
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        if subtitle:
            tk.Label(
                wrap, text=subtitle,
                bg=BG, fg=MUTED,
                font=("Segoe UI", 9)
            ).pack(anchor="w", pady=(2, 0))

    def compact_card(self, parent, item, index):
        card = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1,
            width=300, height=155
        )
        card.grid(row=index // 2, column=index % 2,
                  sticky="nsew", padx=(0, 10), pady=(0, 10))
        card.grid_propagate(False)
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        color, soft = self.category_colors(item["category"])

        top = tk.Frame(card, bg=WHITE)
        top.pack(fill="x", padx=15, pady=(14, 7))

        tk.Label(
            top, text=item["category"],
            bg=soft, fg=color,
            font=("Segoe UI", 8, "bold"),
            padx=8, pady=4
        ).pack(side="left")

        if not item.get("seen", True):
            self.new_badge(top)

        tk.Label(
            top, text=f"⌛ {item.get('deadline', '—')}",
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 8)
        ).pack(side="right")

        tk.Label(
            card, text=item["title"],
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 11, "bold"),
            wraplength=390,
            justify="left"
        ).pack(anchor="w", padx=15)

        tk.Label(
            card, text=item["description"][:140],
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 8),
            wraplength=390,
            justify="left"
        ).pack(anchor="w", padx=15, pady=(5, 8))

        tk.Button(
            card, text="Batafsil  →",
            command=lambda x=item: self.show_detail(x),
            bg=WHITE, fg=PRIMARY,
            activebackground=WHITE,
            activeforeground=PRIMARY_DARK,
            relief="flat", bd=0,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2"
        ).pack(anchor="w", padx=12)

    # ---------------------- OPPORTUNITIES ----------------------

    def show_opportunities(self):
        self.current_page = "opportunities"
        self.current_search = None
        self.set_active("opportunities")
        self.clear_content()

        self.heading(
            "Imkoniyatlar",
            "O‘zingizga kerakli yo‘nalishni tanlang yoki qidiruvdan foydalaning."
        )

        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", padx=35, pady=(0, 15))

        combo = ttk.Combobox(
            toolbar,
            values=CATEGORIES,
            state="readonly",
            width=23,
            style="Hub.TCombobox"
        )
        combo.set(self.current_category)
        combo.pack(side="left")
        combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.change_category(combo.get())
        )

        search = tk.Entry(
            toolbar, bg=WHITE, fg=TEXT,
            relief="flat", bd=0,
            font=("Segoe UI", 10),
            highlightbackground=BORDER,
            highlightthickness=1
        )
        search.pack(side="left", fill="x", expand=True, padx=10, ipady=8)
        search.insert(0, "Qidirish...")
        search.bind(
            "<FocusIn>",
            lambda e: search.delete(0, "end") if search.get() == "Qidirish..." else None
        )

        def run_search():
            q = search.get().strip()
            if q and q != "Qidirish...":
                self.search_results(q)
            else:
                self.show_opportunities()

        search.bind("<Return>", lambda e: run_search())
        self.button(toolbar, "Qidirish", run_search).pack(side="left")
        self.button(
            toolbar, "↻ Yangilash",
            lambda: self.refresh_online(manual=True),
            bg=GREEN
        ).pack(side="left", padx=(8, 0))

        container_outer = tk.Frame(self.content, bg=BG)
        container_outer.pack(fill="both", expand=True, padx=35)
        container = self.make_scrollable(container_outer)

        self.render_list(container, self.filtered_items())

    def filtered_items(self):
        if self.current_category == "Barchasi":
            return self.opportunities
        return [
            x for x in self.opportunities
            if x.get("category") == self.current_category
        ]

    def change_category(self, category):
        self.current_category = category
        self.show_opportunities()

    def make_scrollable(self, parent):
        """Vertikal scrollga ega konteyner."""
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)

        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_width)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def wheel(event):
            # Windows (120 ga karrali), macOS (kichik qiymatlar) uchun ham ishlaydi.
            if event.delta:
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return inner

    def render_list(self, parent, items):
        if not items:
            self.empty_state(
                parent,
                "Mos imkoniyat topilmadi",
                "Boshqa kategoriya yoki qidiruv so‘zini sinab ko‘ring."
            )
            return

        for item in items:
            self.list_card(parent, item)

    def list_card(self, parent, item):
        card = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.pack(fill="x", pady=(0, 9))

        color, soft = self.category_colors(item["category"])

        tk.Label(
            card, text=self.category_icon(item["category"]),
            bg=soft, fg=color,
            font=("Segoe UI", 18, "bold"),
            width=3, height=2
        ).pack(side="left", padx=15, pady=15)

        middle = tk.Frame(card, bg=WHITE)
        middle.pack(side="left", fill="both", expand=True,
                    padx=(0, 10), pady=13)

        title_row = tk.Frame(middle, bg=WHITE)
        title_row.pack(anchor="w", fill="x")

        tk.Label(
            title_row, text=item["title"],
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 12, "bold"),
            wraplength=640, justify="left"
        ).pack(side="left")

        if not item.get("seen", True):
            self.new_badge(title_row)

        source = item.get("source", "")
        source_text = f"  ·  Manba: {source}" if source else ""

        tk.Label(
            middle,
            text=(f'{item.get("location", "")}  ·  {item.get("type", "")}  ·  '
                  f'E’lon: {ago(item.get("published", ""))}{source_text}'),
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(4, 5))

        tags = ", ".join(item.get("fields", []))
        tk.Label(
            middle, text=f"Soha: {tags}",
            bg=WHITE, fg="#475467",
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        right = tk.Frame(card, bg=WHITE)
        right.pack(side="right", padx=15, pady=15)

        self.button(
            right, "Batafsil  →",
            lambda x=item: self.show_detail(x)
        ).pack()

    # ---------------------- RECOMMENDATIONS ----------------------

    def show_recommended(self):
        self.current_page = "recommended"
        self.current_search = None
        self.set_active("recommended")
        self.clear_content()

        interest = self.profile.get("Qiziqish", "").strip()

        if not interest:
            self.heading(
                "Menga mos",
                "Sohangizni kiriting — platforma mos imkoniyatlarni ajratib beradi."
            )
            card = tk.Frame(
                self.content, bg=WHITE,
                highlightbackground=BORDER,
                highlightthickness=1
            )
            card.pack(fill="x", padx=35)

            tk.Label(
                card,
                text="Hozircha qiziqishingiz ko‘rsatilmagan.",
                bg=WHITE, fg=TEXT,
                font=("Segoe UI", 13, "bold")
            ).pack(anchor="w", padx=25, pady=(25, 5))

            tk.Label(
                card,
                text="Profilingizda “Qiziqish” maydoniga masalan, Logistika deb yozing.",
                bg=WHITE, fg=MUTED,
                font=("Segoe UI", 9)
            ).pack(anchor="w", padx=25, pady=(0, 18))

            self.button(
                card, "Profilni to‘ldirish",
                self.show_profile
            ).pack(anchor="w", padx=25, pady=(0, 25))
            return

        self.heading(
            f"{interest} bo‘yicha sizga mos",
            "Profilingizdagi soha asosida mos imkoniyatlar ajratildi."
        )

        results = self.match_by_field(interest)

        container_outer = tk.Frame(self.content, bg=BG)
        container_outer.pack(fill="both", expand=True, padx=35)
        container = self.make_scrollable(container_outer)

        if not results:
            self.empty_state(
                container,
                f"{interest} bo‘yicha hozircha imkoniyat yo‘q",
                "Boshqa soha nomini sinab ko‘ring yoki yangi imkoniyat qo‘shing."
            )
            return

        tk.Label(
            container,
            text=f"{len(results)} ta mos imkoniyat topildi",
            bg=BG, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 8))

        for item in results:
            self.list_card(container, item)

    def match_by_field(self, field):
        words = [
            w for w in _norm(field).replace(",", " ").split()
            if len(w) > 1
        ]

        scored = []
        for item in self.opportunities:
            text = _norm(" ".join(
                item.get("fields", []) +
                [item.get("title", ""), item.get("description", "")]
            ))

            score = sum(2 for word in words if word in text)
            if score:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]

    # ---------------------- SAVED ----------------------

    def show_saved(self):
        self.current_page = "saved"
        self.current_search = None
        self.set_active("saved")
        self.clear_content()

        self.heading(
            "Saqlanganlar",
            "Keyinroq ko‘rmoqchi bo‘lgan imkoniyatlaringiz shu yerda."
        )

        container_outer = tk.Frame(self.content, bg=BG)
        container_outer.pack(fill="both", expand=True, padx=35)
        container = self.make_scrollable(container_outer)

        items = [x for x in self.opportunities if x["id"] in self.saved_ids]

        if not items:
            self.empty_state(
                container,
                "Saqlangan imkoniyatlar yo‘q",
                "Sizga yoqqan imkoniyatni ochib, “Saqlash” tugmasini bosing."
            )
            return

        for item in items:
            self.list_card(container, item)

    # ---------------------- DETAIL ----------------------

    def show_detail(self, item):
        item["seen"] = True  # ko'rildi — "YANGI" belgisi yo'qoladi
        self.clear_content()

        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x", padx=35, pady=(25, 10))

        tk.Button(
            top, text="← Ortga",
            command=self.go_back,
            bg=BG, fg=MUTED,
            activebackground=BG,
            activeforeground=TEXT,
            relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        ).pack(anchor="w")

        card = tk.Frame(
            self.content, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.pack(fill="x", padx=35, pady=8)

        color, soft = self.category_colors(item["category"])

        tk.Label(
            card, text=item["category"],
            bg=soft, fg=color,
            font=("Segoe UI", 8, "bold"),
            padx=10, pady=5
        ).pack(anchor="w", padx=25, pady=(25, 12))

        tk.Label(
            card, text=item["title"],
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 20, "bold"),
            wraplength=800,
            justify="left"
        ).pack(anchor="w", padx=25)

        info = tk.Frame(card, bg=WHITE)
        info.pack(fill="x", padx=25, pady=18)

        details = [
            ("Hudud", item.get("location", "—")),
            ("Turi", item.get("type", "—")),
            ("Deadline", item.get("deadline", "—")),
            ("E’lon", ago(item.get("published", ""))),
            ("Manba", item.get("source", "—")),
        ]

        for label, value in details:
            box = tk.Frame(info, bg="#F8FAFC")
            box.pack(side="left", padx=(0, 10), ipadx=12, ipady=8)

            tk.Label(
                box, text=label,
                bg="#F8FAFC", fg=MUTED,
                font=("Segoe UI", 8)
            ).pack(anchor="w")

            tk.Label(
                box, text=value,
                bg="#F8FAFC", fg=TEXT,
                font=("Segoe UI", 9, "bold")
            ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            card, text="Tavsif",
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=25)

        tk.Label(
            card, text=item.get("description", ""),
            bg=WHITE, fg="#475467",
            font=("Segoe UI", 10),
            wraplength=820,
            justify="left"
        ).pack(anchor="w", padx=25, pady=(6, 18))

        tk.Label(
            card, text="Mos sohalar",
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=25)

        tk.Label(
            card, text=", ".join(item.get("fields", [])),
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=25, pady=(5, 18))

        actions = tk.Frame(card, bg=WHITE)
        actions.pack(anchor="w", padx=25, pady=(0, 25))

        saved = item["id"] in self.saved_ids
        self.button(
            actions,
            "★ Saqlangan" if saved else "☆ Saqlash",
            lambda x=item: self.toggle_save(x)
        ).pack(side="left", padx=(0, 8))

        if item.get("link"):
            self.button(
                actions, "↗ Havolani ochish",
                lambda: webbrowser.open(item["link"]),
                bg=GREEN
            ).pack(side="left")

    def go_back(self):
        pages = {
            "home": self.show_home,
            "opportunities": self.show_opportunities,
            "recommended": self.show_recommended,
            "saved": self.show_saved,
            "profile": self.show_profile,
            "add": self.add_opportunity,
            "sources": self.show_sources,
        }
        if self.current_page == "opportunities" and self.current_search:
            self.search_results(self.current_search, include_web=False)
            return
        pages.get(self.current_page, self.show_home)()

    def toggle_save(self, item):
        if item["id"] in self.saved_ids:
            self.saved_ids.remove(item["id"])
            messagebox.showinfo("Yoshlar Hub", "Saqlanganlardan olib tashlandi.")
        else:
            self.saved_ids.add(item["id"])
            messagebox.showinfo("Yoshlar Hub", "Imkoniyat saqlandi.")
        save_data(self.opportunities, self.profile, self.saved_ids)
        self.show_detail(item)

    # ---------------------- PROFILE ----------------------

    def show_profile(self):
        self.current_page = "profile"
        self.current_search = None
        self.set_active("profile")
        self.clear_content()

        self.heading(
            "Mening profilim",
            "Ma’lumotlaringizni kiriting. Bu ma’lumotlar sizga mos imkoniyatlarni topishda ishlatiladi."
        )

        card = tk.Frame(
            self.content, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.pack(fill="x", padx=35)

        fields = [
            ("Ism", "Ismingiz"),
            ("Universitet", "Universitetingiz"),
            ("Yo‘nalish", "O‘qiyotgan yo‘nalishingiz"),
            ("Kurs", "Masalan: 1-kurs"),
            ("Hudud", "Viloyat yoki shahar"),
            ("Qiziqish", "Masalan: Logistika, IT, Marketing"),
        ]

        entries = {}

        for label, _placeholder in fields:
            row = tk.Frame(card, bg=WHITE)
            row.pack(fill="x", padx=25, pady=7)

            tk.Label(
                row, text=label,
                bg=WHITE, fg=TEXT,
                width=15, anchor="w",
                font=("Segoe UI", 9, "bold")
            ).pack(side="left")

            entry = tk.Entry(
                row, bg="#F9FAFB", fg=TEXT,
                relief="flat", bd=0,
                font=("Segoe UI", 10),
                highlightbackground=BORDER,
                highlightthickness=1
            )
            entry.insert(0, self.profile.get(label, ""))
            entry.pack(side="left", fill="x", expand=True, ipady=7)
            entries[label] = entry

        self.button(
            card, "Saqlash",
            lambda: self.save_profile(entries)
        ).pack(anchor="w", padx=25, pady=(15, 25))

    def save_profile(self, entries):
        self.profile = {key: entry.get().strip() for key, entry in entries.items()}
        save_data(self.opportunities, self.profile, self.saved_ids)
        messagebox.showinfo(
            "Yoshlar Hub",
            "Profilingiz saqlandi. Endi “Menga mos” bo‘limini oching."
        )
        self.show_home()
        # Yangi qiziqish bo'yicha darhol qayta qidiramiz
        self.refresh_online(manual=False)

    # ---------------------- ADD OPPORTUNITY ----------------------

    def add_opportunity(self):
        self.current_page = "add"
        self.current_search = None
        self.set_active("add")
        self.clear_content()

        self.heading(
            "Imkoniyat qo‘shish",
            "Grant, kurs, tanlov, internship yoki volunteer imkoniyatini platformaga kiriting."
        )

        card = tk.Frame(
            self.content, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        card.pack(fill="x", padx=35)

        fields = [
            ("Nomi", "title"),
            ("Hudud", "location"),
            ("Turi", "type"),
            ("Deadline", "deadline"),
            ("Soha", "fields"),
            ("Havola", "link"),
            ("Tavsif", "description")
        ]
        entries = {}

        for label, key in fields:
            row = tk.Frame(card, bg=WHITE)
            row.pack(fill="x", padx=25, pady=6)

            tk.Label(
                row, text=label,
                bg=WHITE, fg=TEXT,
                width=14, anchor="w",
                font=("Segoe UI", 9, "bold")
            ).pack(side="left")

            entry = tk.Entry(
                row, bg="#F9FAFB", fg=TEXT,
                relief="flat", bd=0,
                font=("Segoe UI", 10),
                highlightbackground=BORDER,
                highlightthickness=1
            )
            entry.pack(side="left", fill="x", expand=True, ipady=7)
            entries[key] = entry

        row = tk.Frame(card, bg=WHITE)
        row.pack(fill="x", padx=25, pady=6)

        tk.Label(
            row, text="Kategoriya",
            bg=WHITE, fg=TEXT,
            width=14, anchor="w",
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        combo = ttk.Combobox(
            row, values=CATEGORIES[1:],
            state="readonly", width=28,
            style="Hub.TCombobox"
        )
        combo.set("Grantlar")
        combo.pack(side="left")
        entries["category"] = combo

        tk.Label(
            card,
            text="Soha maydoniga bir nechta yo‘nalish yozish mumkin: Logistika, IT, Biznes",
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=25, pady=(5, 10))

        self.button(
            card, "Imkoniyatni saqlash",
            lambda: self.save_opportunity(entries),
            bg=GREEN
        ).pack(anchor="w", padx=25, pady=(5, 25))

    def save_opportunity(self, entries):
        title = entries["title"].get().strip()

        if not title:
            messagebox.showwarning("Yoshlar Hub", "Avval imkoniyat nomini kiriting.")
            return

        fields = [
            x.strip()
            for x in entries["fields"].get().replace(";", ",").split(",")
            if x.strip()
        ] or ["Barcha sohalar"]

        new_id = max([x.get("id", 0) for x in self.opportunities] or [0]) + 1

        item = {
            "id": new_id,
            "title": title,
            "category": entries["category"].get(),
            "location": entries["location"].get().strip() or "O‘zbekiston",
            "type": entries["type"].get().strip() or "Umumiy",
            "deadline": entries["deadline"].get().strip() or "Ko‘rsatilmagan",
            "fields": fields,
            "link": entries["link"].get().strip(),
            "source": SRC_MANUAL,
            "published": fmt_ts(now_utc()),
            "description": entries["description"].get().strip() or "Tavsif kiritilmagan.",
            "seen": True,
        }

        self.opportunities.insert(0, item)
        save_data(self.opportunities, self.profile, self.saved_ids)

        messagebox.showinfo("Yoshlar Hub", "Imkoniyat muvaffaqiyatli qo‘shildi.")
        self.show_opportunities()

    # ---------------------- MANBALAR (RSS) ----------------------

    def show_sources(self):
        self.current_page = "sources"
        self.current_search = None
        self.set_active("sources")
        self.clear_content()

        self.heading(
            "Manbalar",
            "RSS/Atom manbalarni qo‘shing. Dastur ularni har yangilashda avtomatik tekshiradi."
        )

        card = tk.Frame(
            self.content, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.pack(fill="x", padx=35, pady=(0, 14))

        tk.Label(
            card, text="Standart manbalar",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=25, pady=(20, 4))
        tk.Label(
            card,
            text="Google News, Bing News va gov.uz qidiruvi (doim yoqilgan).",
            bg=WHITE, fg=MUTED, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=25, pady=(0, 14))

        tk.Label(
            card, text="Sizning manbalaringiz",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=25, pady=(0, 6))

        if not USER_FEEDS:
            tk.Label(
                card, text="Hozircha qo‘shilmagan.",
                bg=WHITE, fg=MUTED, font=("Segoe UI", 9)
            ).pack(anchor="w", padx=25, pady=(0, 10))

        for name, url in list(USER_FEEDS):
            row = tk.Frame(card, bg=WHITE)
            row.pack(fill="x", padx=25, pady=3)
            tk.Label(
                row, text=f"{name}  ·  {url}",
                bg=WHITE, fg="#475467", font=("Segoe UI", 9),
                anchor="w", wraplength=620, justify="left"
            ).pack(side="left", fill="x", expand=True)
            self.button(
                row, "O‘chirish",
                lambda u=url: self.remove_feed(u),
                bg=ORANGE
            ).pack(side="right")

        form = tk.Frame(card, bg=WHITE)
        form.pack(fill="x", padx=25, pady=(16, 6))

        entries = {}
        for label, key in (("Nomi", "name"), ("RSS havola", "url")):
            row = tk.Frame(form, bg=WHITE)
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=label, bg=WHITE, fg=TEXT,
                width=12, anchor="w", font=("Segoe UI", 9, "bold")
            ).pack(side="left")
            e = tk.Entry(
                row, bg="#F9FAFB", fg=TEXT, relief="flat", bd=0,
                font=("Segoe UI", 10),
                highlightbackground=BORDER, highlightthickness=1
            )
            e.pack(side="left", fill="x", expand=True, ipady=7)
            entries[key] = e

        self.feed_msg = tk.Label(
            card, text="", bg=WHITE, fg=MUTED,
            font=("Segoe UI", 9), anchor="w", justify="left", wraplength=700
        )
        self.feed_msg.pack(anchor="w", padx=25, pady=(4, 0))

        self.button(
            card, "Tekshirish va qo‘shish",
            lambda: self.add_feed(entries["name"].get().strip(), entries["url"].get().strip()),
            bg=GREEN
        ).pack(anchor="w", padx=25, pady=(8, 22))

        tk.Label(
            self.content,
            text=("Maslahat: sayt RSS taklif qilsa, odatda manzil /rss, /feed yoki /rss.xml bilan tugaydi. "
                  "Qo‘shishdan oldin dastur havolani tekshiradi va nechta yozuv topganini aytadi."),
            bg=BG, fg=MUTED, font=("Segoe UI", 9),
            wraplength=800, justify="left"
        ).pack(anchor="w", padx=35)

    def _feed_say(self, text, color=MUTED):
        try:
            self.feed_msg.configure(text=text, fg=color)
        except (tk.TclError, AttributeError):
            pass

    def add_feed(self, name, url):
        if not url.startswith(("http://", "https://")):
            self._feed_say("Havola http:// yoki https:// bilan boshlanishi kerak.", ORANGE)
            return
        if any(u == url for _, u in USER_FEEDS):
            self._feed_say("Bu manba allaqachon qo‘shilgan.", ORANGE)
            return
        name = name or urlparse(url).netloc
        self._feed_say("Havola tekshirilmoqda...", PRIMARY)

        def worker():
            try:
                count = len(parse_feed(_http_get(url)))
                err = None
            except Exception as exc:
                count, err = 0, str(exc)[:120]

            def done():
                if count > 0:
                    USER_FEEDS.append((name, url))
                    try:
                        save_data(self.opportunities, self.profile, self.saved_ids)
                    except Exception:
                        pass
                    self.show_sources()
                    self._feed_say(f"✓ “{name}” qo‘shildi ({count} ta yozuv topildi). Yangilash bosilganda ishlatiladi.", GREEN)
                    self.refresh_online(manual=False)
                elif err:
                    self._feed_say(f"⚠ Havolaga ulanib bo‘lmadi: {err}", ORANGE)
                else:
                    self._feed_say("⚠ Havola ochildi, lekin RSS/Atom yozuvlari topilmadi. Bu oddiy sayt sahifasi bo‘lishi mumkin.", ORANGE)

            try:
                self.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def remove_feed(self, url):
        USER_FEEDS[:] = [f for f in USER_FEEDS if f[1] != url]
        save_data(self.opportunities, self.profile, self.saved_ids)
        self.show_sources()

    # ---------------------- SEARCH ----------------------

    def search_web_async(self, query, local_results):
        """Foydalanuvchi so'rovi bo'yicha web qidiruvni UI ni bloklamasdan bajaradi."""
        words = [w for w in _norm(query).split() if w]

        def worker():
            try:
                web_items, _ok, _total = fetch_real_opportunities(query)
            except Exception:
                return

            filtered = []
            for item in web_items:
                hay = _norm(" ".join([
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("category", ""),
                    " ".join(item.get("fields", [])),
                ]))
                if all(w in hay for w in words):
                    filtered.append(item)

            def apply():
                if not filtered:
                    return
                merged, added = merge_opportunities(
                    self.opportunities, filtered, self.saved_ids
                )
                if not added:
                    return
                self.opportunities = merged
                save_data(self.opportunities, self.profile, self.saved_ids)
                # Faqat foydalanuvchi hali shu qidiruv sahifasida bo'lsa yangilaymiz.
                if self.current_page == "opportunities" and self.current_search == query:
                    self.search_results(query, include_web=False)

            try:
                self.after(0, apply)
            except Exception:
                pass  # oyna yopilgan

        threading.Thread(target=worker, daemon=True).start()

    def search_results(self, query, include_web=True):
        self.current_page = "opportunities"
        self.current_search = query
        self.set_active("opportunities")
        self.clear_content()

        self.heading(
            f'"{query}" bo‘yicha natijalar',
            "Nom, kategoriya, hudud, tavsif va sohalar bo‘yicha qidirildi."
        )

        q = _norm(query)
        results = []
        for item in self.opportunities:
            text = _norm(" ".join([
                item.get("title", ""),
                item.get("category", ""),
                item.get("location", ""),
                item.get("type", ""),
                item.get("description", ""),
                " ".join(item.get("fields", []))
            ]))
            if q in text:
                results.append(item)

        container_outer = tk.Frame(self.content, bg=BG)
        container_outer.pack(fill="both", expand=True, padx=35)
        container = self.make_scrollable(container_outer)

        tk.Label(
            container,
            text=f"{len(results)} ta natija" + ("  ·  internetdan qidirilmoqda..." if include_web else ""),
            bg=BG, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 8))

        self.render_list(container, results)

        if include_web:
            self.search_web_async(query, results)

    # ---------------------- JONLI YANGILASH ----------------------

    def auto_refresh(self):
        """Har AUTO_REFRESH_MINUTES daqiqada o'zi chaqiriladi."""
        self.refresh_online(manual=False)
        self.after(AUTO_REFRESH_MINUTES * 60 * 1000, self.auto_refresh)

    def refresh_online(self, manual=True):
        """Internetdan yangi imkoniyatlarni fon oqimida oladi (UI muzlamaydi)."""
        if self.refreshing:
            return
        self.refreshing = True
        interest = self.profile.get("Qiziqish", "").strip()
        self.set_status("● Internetdan yangi imkoniyatlar qidirilmoqda...", PRIMARY)

        def worker():
            try:
                results, ok, total = fetch_real_opportunities(interest)
            except Exception:
                results, ok, total = [], 0, 0

            def apply_results():
                self.refreshing = False
                stamp = datetime.now().strftime("%H:%M")

                if ok == 0:
                    self.set_status(
                        f"⚠ {stamp} — internet yo‘q yoki manbalar javob bermadi. "
                        "Mavjud ma’lumotlar saqlanib turibdi.", ORANGE)
                    return

                merged, added = merge_opportunities(
                    self.opportunities, results, self.saved_ids
                )
                self.opportunities = merged
                try:
                    save_data(self.opportunities, self.profile, self.saved_ids)
                except Exception:
                    pass

                if added:
                    self.set_status(
                        f"✓ {stamp} — {added} ta yangi imkoniyat topildi "
                        f"({ok}/{total} manba)", GREEN)
                else:
                    self.set_status(
                        f"✓ {stamp} — yangilik yo‘q ({ok}/{total} manba)", MUTED)

                # Foydalanuvchini bezovta qilmaslik uchun: qo'lda bosganda yoki
                # bosh sahifada yangilik chiqqanda ekranni yangilaymiz.
                if self.current_page == "home" and (manual or added):
                    self.show_home()
                elif manual and self.current_page == "opportunities" and not self.current_search:
                    self.show_opportunities()
                elif manual and self.current_page == "recommended":
                    self.show_recommended()

            try:
                self.after(0, apply_results)
            except Exception:
                pass  # oyna yopilgan

        threading.Thread(target=worker, daemon=True).start()

    # ---------------------- HELPERS ----------------------

    def count_category(self, category):
        return sum(1 for x in self.opportunities if x.get("category") == category)

    def category_colors(self, category):
        colors = {
            "Grantlar": (PURPLE, SOFT_PURPLE),
            "Ish va internship": (PRIMARY, SOFT_BLUE),
            "Tanlovlar": (ORANGE, SOFT_ORANGE),
            "Kurslar": (GREEN, SOFT_GREEN),
            "Volunteer": ("#039855", "#ECFDF3"),
            "Tadbirlar": ("#B54708", "#FFFAEB")
        }
        return colors.get(category, (PRIMARY, SOFT_BLUE))

    def category_icon(self, category):
        icons = {
            "Grantlar": "₲",
            "Ish va internship": "↗",
            "Tanlovlar": "★",
            "Kurslar": "▣",
            "Volunteer": "♥",
            "Tadbirlar": "◷"
        }
        return icons.get(category, "•")

    def empty_state(self, parent, title, description):
        box = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        box.pack(fill="x", pady=20)

        tk.Label(
            box, text=title,
            bg=WHITE, fg=TEXT,
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(25, 5))

        tk.Label(
            box, text=description,
            bg=WHITE, fg=MUTED,
            font=("Segoe UI", 9)
        ).pack(pady=(0, 25))


if __name__ == "__main__":
    app = YoshlarHub()
    # Ishga tushgandan 0.7 soniya keyin birinchi yangilash, so'ng har 15 daqiqada.
    app.after(700, lambda: app.refresh_online(manual=False))
    app.after(AUTO_REFRESH_MINUTES * 60 * 1000, app.auto_refresh)
    app.mainloop()
