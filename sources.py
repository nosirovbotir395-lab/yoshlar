"""
Yoshlar Hub — veb versiya uchun ma'lumot qatlami.

Bu modul tkinter dasturidagi (yoshlar_hub.py) manba olish mantiqini qayta ishlatadi:
Google News / Bing News RSS, kategoriya aniqlash, deadline topish, dublikat olib tashlash.
Interfeysga (oyna) hech qanday bog'liqlik yo'q.
"""
import re
import os
import json
import time
import html
import hashlib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse, parse_qs, unquote
import xml.etree.ElementTree as ET

MAX_AGE_DAYS = 60
REQUEST_TIMEOUT = 10

# Server bu ro'yxatni har yangilashdan oldin bazadagi "feeds" jadvalidan to'ldiradi.
USER_FEEDS = []

SRC_SEARCH = "Web qidiruv"
SRC_MANUAL = "Qo‘lda qo‘shilgan"
SRC_OFFICIAL = "Rasmiy manba (gov.uz)"

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
     [r"\bgrants?\b", r"stipend", r"scholarship", r"fellowship", r"funding", r"грант", r"стипенди", r"subsidiya"]),
    ("Ish va internship", "Ish / internship",
     [r"internship", r"\bintern\b", r"vacanc", r"\bjobs?\b", r"\bcareers?\b",
      r"amaliyot", r"vakansiya", r"stajirovka", r"ish o'rin", r"ishga qabul", r"вакансия", r"стажировк", r"ярмарка вакансий", r"ish yarmarka"]),
    ("Kurslar", "Kurs",
     [r"\bcourses?\b", r"\bkurs", r"курс", r"training", r"academy", r"akademiya", r"bootcamp",
      r"workshop", r"o'quv", r"trening", r"master-klass", r"bepul dars"]),
    ("Volunteer", "Volunteer",
     [r"volunteer", r"volontyor", r"ko'ngilli"]),
    ("Tadbirlar", "Tadbir",
     [r"\bevents?\b", r"tadbir", r"\bforum", r"summit", r"conference",
      r"konferensiya"]),
    ("Tanlovlar", "Tanlov",
     [r"competition", r"contest", r"hackathon", r"hakaton", r"challenge", r"tanlov", r"танлов", r"конкурс",
      r"festival", r"olimpiada", r"chempionat", r"ko'rik-tanlov",
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


def build_item(row, source_label, strict=True, default=None):
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
        cls = default or ("Tanlovlar", "Imkoniyat")
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


# ---------------------------------------------------------------------------
# Mavzu bo'yicha jonli Google News qidiruvi ("Tez saralash" tugmalari uchun)
# ---------------------------------------------------------------------------
_TOPIC_CACHE = {}  # {kalit: (vaqt, natijalar)}
_TOPIC_CACHE_SEC = 900


def _gnews_url(query, lang):
    if lang == "uz":
        tail = "&hl=uz&gl=UZ&ceid=UZ:uz"
    elif lang == "ru":
        tail = "&hl=ru&gl=UZ&ceid=UZ:ru"
    else:
        tail = "&hl=en-US&gl=US&ceid=US:en"
    return "https://news.google.com/rss/search?q=" + quote(query + " when:30d") + tail


_UZ_HINTS = (" va ", " uchun ", " bo'yicha ", "o'", "g'", " yoshlar", " tanlov", "e'lon", " qabul", "tashkil",
             " o‘", "g‘", "ʻ", " bilan ", " ham ", " qilindi", " boshlandi")


def lang_rank(text):
    """0 — o'zbekcha (lotin yoki kirill), 1 — ruscha, 2 — boshqa (inglizcha)."""
    t = " " + (text or "").lower() + " "
    if any(h in t for h in _UZ_HINTS) or any(c in t for c in "ўқғҳ"):
        return 0
    if any("а" <= c <= "я" for c in t):
        return 1
    return 2


def topic_search(key, queries, terms, default, hh_query=""):
    """
    Bitta mavzu bo'yicha Google News'dan qidiradi va faqat mavzuga mos
    natijalarni qaytaradi. queries: [(so'rov, til)], terms: mavzu so'zlari,
    default: (kategoriya, tur) — kategoriya aniqlanmasa shu qo'yiladi.
    """
    now = time.time()
    hit = _TOPIC_CACHE.get(key)
    if hit and now - hit[0] < _TOPIC_CACHE_SEC:
        return hit[1]
    year = now_utc().year

    def fetch(job):
        q, lang = job
        try:
            return parse_feed(_http_get(_gnews_url(q.format(year=year), lang)))
        except Exception:
            return None

    out, seen, answered = [], set(), 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for rows in pool.map(fetch, queries):
            if rows is None:
                continue
            answered += 1
            for row in rows[:30]:
                # strict=True: matnda tanlov/grant/kurs/vakansiya kabi imkoniyat belgisi bo'lmasa — oddiy yangilik, tashlaymiz
                item = build_item(row, "Google News", strict=True)
                if not item:
                    continue
                text = " " + _norm(item["title"] + " " + item["description"]) + " "
                if not any(t in text for t in terms):
                    continue  # mavzuga aloqasi yo'q
                if not has_apply_sign(row["title"] + " " + row.get("description", "")):
                    continue  # ro'yxatdan o'tish / ariza belgisi yo'q — oddiy yangilik
                k = _title_key(item["title"])
                if k in seen or item["link"].lower() in seen:
                    continue
                seen.update((k, item["link"].lower()))
                out.append(item)
    # To'g'ridan-to'g'ri ariza beriladigan manbalar
    for item in (hh_vacancies(hh_query, 20) if hh_query else []) + feed_opportunities(terms):
        k = _title_key(item["title"])
        if k in seen or item["link"].lower() in seen:
            continue
        seen.update((k, item["link"].lower()))
        out.append(item)
    # O'zbek tilidagi natijalar birinchi, keyin rus, keyin ingliz
    out.sort(key=lambda x: x.get("published", ""), reverse=True)
    out.sort(key=lambda x: lang_rank(x["title"] + " " + x["description"]))
    if answered:  # tarmoq xatosini keshlamaymiz
        if len(_TOPIC_CACHE) > 50:
            _TOPIC_CACHE.clear()
        _TOPIC_CACHE[key] = (now, out[:40])
    return out[:40]


# ---------------------------------------------------------------------------
# Jonli web qidiruv (SearXNG). Manzil muhit o'zgaruvchisidan olinadi.
# ---------------------------------------------------------------------------
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")
_WEB_CACHE = {}  # {so'rov: (vaqt, natijalar)} — bir xil so'rovni qayta yubormaslik uchun
_WEB_CACHE_SEC = 600


def web_search(query, limit=10):
    """SearXNG orqali internetdan qidiradi. Xato bo'lsa jimgina [] qaytaradi."""
    query = (query or "").strip()
    if not query:
        return []
    now = time.time()
    hit = _WEB_CACHE.get(query.lower())
    if hit and now - hit[0] < _WEB_CACHE_SEC:
        return hit[1]
    try:
        raw = _http_get(
            SEARXNG_URL.rstrip("/") + "/search?format=json&language=en&engines=yahoo,startpage,mojeek&q=" + quote(query),
            timeout=12)
        data = json.loads(raw)
    except Exception:
        return []
    out = []
    for r in data.get("results", []):
        url = r.get("url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        out.append({
            "title": _clean_text(r.get("title") or url)[:180],
            "url": url,
            "snippet": _clean_text(r.get("content") or "")[:300],
            "engine": ", ".join(r.get("engines") or []),
        })
        if len(out) >= limit:
            break
    if out:  # bo'sh natijani keshlamaymiz
        if len(_WEB_CACHE) > 200:
            _WEB_CACHE.clear()
        _WEB_CACHE[query.lower()] = (now, out)
    return out


def web_search_opps(query, limit=12):
    """Soha bo'yicha tanlov, startup va loyihalarni qidiradi."""
    generic = {"youth", "program", "programs", "free", "young", "students", "course"}
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2 and w.lower() not in generic]
    stems = [w[:5] for w in words]
    suffixes = ("", "tanlov startup loyiha", "competition startup project", "hackathon accelerator")
    seen, out = set(), []
    for suffix in suffixes:
        for r in web_search(f"{query} {suffix}".strip(), limit=10):
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            text = (r["title"] + " " + r["snippet"] + " " + r["url"]).lower()
            hits = sum(1 for s in stems if s in text)
            if stems and hits == 0:
                continue
            r["_score"] = hits
            out.append(r)
    out.sort(key=lambda r: r["_score"], reverse=True)
    return out[:limit]


# ---------------------------------------------------------------------------
# To'g'ridan-to'g'ri ariza beriladigan manbalar (yangilik emas)
# ---------------------------------------------------------------------------
SRC_HH = "hh.uz"
DIRECT_SOURCES = (SRC_HH, "Opportunity Desk", "Opportunities for Youth", "Scholars4Dev", "Rasmiy manba", "Qo‘lda qo‘shilgan")

# Ariza / ro'yxatdan o'tish belgilari: Google News natijasida bulardan biri bo'lmasa — oddiy yangilik
APPLY_SIGNS = (
    "ro'yxatdan o'tish", "ro'yxatdan o't", "ariza qabul", "arizalar qabul", "ariza topshir", "ariza ber",
    "qatnashish uchun", "ishtirok etish uchun", "ishtirok etishi mumkin", "qatnashishi mumkin", "hujjatlar qabul",
    "qabul boshlandi", "qabul davom", "muddat", "havola orqali", "anketa", "registratsiya",
    "регистрац", "заявк", "прием документов", "приём документов", "принять участие", "до ",
    "apply", "application", "applications open", "registration", "register", "deadline", "call for",
)

OPP_FEEDS = [
    ("Opportunity Desk", "https://opportunitydesk.org/feed/"),
    ("Opportunities for Youth", "https://opportunitiesforyouth.org/feed/"),
    ("Scholars4Dev", "https://www.scholars4dev.com/feed/"),
]
_FEED_CACHE = {"t": 0, "rows": []}


def is_direct(source):
    return any(x in (source or "") for x in DIRECT_SOURCES)


def has_apply_sign(text):
    t = _norm(text)
    return any(sig in t for sig in APPLY_SIGNS)


def _opp_feed_rows():
    """Imkoniyat saytlarining RSS lentalari (1 soat kesh)."""
    now = time.time()
    if _FEED_CACHE["rows"] and now - _FEED_CACHE["t"] < 3600:
        return _FEED_CACHE["rows"]
    def one(job):
        name, url = job
        try:
            return [(name, r) for r in parse_feed(_http_get(url))[:40]]
        except Exception:
            return []
    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for part in pool.map(one, OPP_FEEDS):
            rows += part
    if rows:
        _FEED_CACHE.update(t=now, rows=rows)
    return rows


def feed_opportunities(terms):
    """Imkoniyat saytlaridan mavzuga mos (terms) dasturlar."""
    out = []
    for name, row in _opp_feed_rows():
        item = build_item(row, name, strict=False, default=("Grantlar", "Dastur"))
        if not item:
            continue
        item["source"] = name
        item["location"] = "Xalqaro / Online"
        text = " " + _norm(item["title"] + " " + row.get("description", "")) + " "
        if terms and not any(t in text for t in terms):
            continue
        out.append(item)
    return out


def _hh_clean(v):
    return _clean_text(re.sub(r"</?highlighttext>", "", v or ""))


def hh_vacancies(text, limit=20):
    """hh.uz ochiq API: O'zbekistondagi vakansiya va amaliyotlar (ariza shu sahifada beriladi)."""
    text = (text or "").strip()
    if not text:
        return []
    url = ("https://api.hh.ru/vacancies?area=97&order_by=publication_time&per_page=%d&text=%s"
           % (limit, quote(text)))
    try:
        req = Request(url, headers={"User-Agent": "YoshlarHub/1.0", "HH-User-Agent": "YoshlarHub/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read(2_000_000).decode("utf-8", "ignore"))
    except Exception:
        return []
    out = []
    for v in data.get("items", []):
        link = v.get("alternate_url") or ""
        title = _clean_text(v.get("name"))
        if not title or not link.startswith("https://"):
            continue
        emp = (v.get("employer") or {}).get("name") or ""
        sal = v.get("salary") or {}
        sal_txt = ""
        if sal.get("from") or sal.get("to"):
            sal_txt = f"Maosh: {sal.get('from') or ''}–{sal.get('to') or ''} {sal.get('currency') or ''}".replace("–  ", " ").strip()
        exp = (v.get("experience") or {}).get("id")
        snip = v.get("snippet") or {}
        desc = " ".join(x for x in (f"{emp}." if emp else "", _hh_clean(snip.get("responsibility")),
                                    _hh_clean(snip.get("requirement")), sal_txt) if x)
        intern = exp == "noExperience" or any(w in title.lower() for w in ("стаж", "intern", "trainee", "amaliyot", "junior", "младш"))
        pub = None
        try:
            pub = datetime.strptime(v.get("published_at", "")[:19], "%Y-%m-%dT%H:%M:%S") - timedelta(hours=3)
            pub = pub.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        item = {
            "id": _make_id(title, link), "title": title[:180], "category": "Ish va internship",
            "location": ((v.get("area") or {}).get("name") or "O‘zbekiston"),
            "type": "Amaliyot / tajribasiz" if intern else "Vakansiya",
            "deadline": "Doimiy qabul", "fields": detect_fields(_norm(title + " " + desc)) + (["Talabalar"] if intern else []),
            "link": link, "source": SRC_HH, "published": fmt_ts(pub or now_utc()),
            "description": (desc or "Vakansiya tafsilotlari hh.uz sahifasida.")[:500], "seen": False,
        }
        out.append(item)
    return out
