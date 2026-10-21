"""Soha so'zlari uchun sinonimlar: o'zbekcha so'z -> boshqa shakllar (uz/en/ru).
Kalit — so'zning boshi (o'zak). Qidiruvda shu o'zak bilan boshlangan so'z topilsa, sinonimlari ham ishlatiladi."""
SYN = {
    "raqs": ["raqs", "raqqos", "dance", "танц", "хореограф", "balet", "ballet"],
    "raqqo": ["raqs", "raqqos", "dance", "танц", "хореограф"],
    "musiq": ["musiqa", "music", "музык", "qo'shiq", "vokal", "vocal"],
    "qo'shi": ["qo'shiq", "vokal", "music", "song", "песн"],
    "sport": ["sport", "спорт", "athlet", "futbol", "football"],
    "futbo": ["futbol", "football", "футбол"],
    "tibbi": ["tibbiyot", "medic", "health", "медицин", "shifokor", "doctor", "hamshira"],
    "shifo": ["shifokor", "doctor", "медицин", "tibbiyot"],
    "dizay": ["dizayn", "design", "дизайн", "ui/ux", "grafik"],
    "jurna": ["jurnalist", "journalis", "журналист", "media", "ommaviy axborot"],
    "huquq": ["huquq", "law", "legal", "юрист", "право", "advokat"],
    "iqtis": ["iqtisod", "econom", "экономик", "moliya", "finance"],
    "moliy": ["moliya", "finance", "финанс", "bank", "buxgalter"],
    "buxga": ["buxgalter", "accountant", "accounting", "бухгалтер"],
    "pedag": ["pedagog", "o'qituvchi", "teacher", "учител", "ta'lim", "education"],
    "o'qit": ["o'qituvchi", "teacher", "учител", "pedagog"],
    "ta'li": ["ta'lim", "education", "образован", "o'qituvchi"],
    "qishl": ["qishloq xo'jaligi", "agricultur", "agro", "сельск", "fermer"],
    "agro": ["agro", "agricultur", "qishloq xo'jaligi", "сельск"],
    "turiz": ["turizm", "touris", "туризм", "mehmonxona", "hotel"],
    "ekolo": ["ekolog", "ecolog", "environment", "экологи", "climate", "iqlim"],
    "kino": ["kino", "film", "кино", "video", "rejissyor"],
    "fotog": ["fotograf", "photo", "фотограф"],
    "san'a": ["san'at", "art", "искусств", "rassom", "artist"],
    "rasso": ["rassom", "artist", "painter", "художник", "san'at"],
    "teatr": ["teatr", "theatre", "theater", "театр", "aktyor"],
    "aktyo": ["aktyor", "actor", "актер", "teatr"],
    "adabi": ["adabiyot", "literature", "литератур", "yozuvchi", "she'r", "poet"],
    "kimyo": ["kimyo", "chemistr", "хими"],
    "fizik": ["fizika", "physics", "физик"],
    "matem": ["matematika", "math", "математ", "olimpiada"],
    "biolo": ["biologiya", "biolog", "биолог"],
    "muhan": ["muhandis", "engineer", "инженер"],
    "quril": ["qurilish", "construction", "строител", "arxitekt"],
    "arxit": ["arxitektur", "architect", "архитект"],
    "psixo": ["psixolog", "psycholog", "психолог"],
    "robot": ["robot", "робот", "arduino"],
    "kiber": ["kiber", "cyber", "кибер", "security"],
    "oshpa": ["oshpaz", "cook", "chef", "повар", "culinar"],
    "tikuv": ["tikuvchi", "fashion", "moda", "швей", "dizayn"],
    "moda": ["moda", "fashion", "мода"],
    "blog": ["blog", "bloger", "блог", "kontent", "content"],
    "til": ["til", "language", "язык", "ielts", "ingliz"],
}


def expand(word):
    """So'z -> qidiruv o'zaklari ro'yxati (o'zining o'zagi + sinonimlar)."""
    w = word.lower()
    base = w[:5] if len(w) > 5 else w
    for key, vals in SYN.items():
        if w.startswith(key):
            return list(dict.fromkeys([base] + vals))
    return [base]


def english(word):
    """Inglizcha so'rov uchun tarjima (topilsa)."""
    for v in expand(word)[1:]:
        if v.isascii() and "'" not in v and v.isalpha():
            return v
    return word

EN = {"raqs": "dance", "raqqo": "dance", "musiq": "music", "qo'shi": "singing", "sport": "sport", "futbo": "football",
      "tibbi": "medical", "shifo": "medical", "dizay": "design", "jurna": "journalism", "huquq": "law", "iqtis": "economics",
      "moliy": "finance", "buxga": "accounting", "pedag": "teaching", "o'qit": "teaching", "ta'li": "education",
      "qishl": "agriculture", "agro": "agriculture", "turiz": "tourism", "ekolo": "environment", "kino": "film",
      "fotog": "photography", "san'a": "art", "rasso": "art", "teatr": "theatre", "aktyo": "acting", "adabi": "literature",
      "kimyo": "chemistry", "fizik": "physics", "matem": "math", "biolo": "biology", "muhan": "engineering",
      "quril": "construction", "arxit": "architecture", "psixo": "psychology", "robot": "robotics", "kiber": "cybersecurity",
      "oshpa": "culinary", "tikuv": "fashion", "moda": "fashion", "blog": "content creator", "til": "language"}


def english(word):  # noqa: F811 — aniq tarjima
    w = word.lower()
    for key, en in EN.items():
        if w.startswith(key):
            return en
    return word
