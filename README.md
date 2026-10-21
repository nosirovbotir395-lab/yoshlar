# Yoshlar Hub — veb versiya

Flask + SQLite. Foydalanuvchilar ro'yxatdan o'tadi, har kimning profili va saqlanganlari alohida.
Server o'zi har 30 daqiqada (`REFRESH_MINUTES`) internetdan yangi imkoniyatlarni oladi.

## 1. Kompyuterda sinash

```bash
cd yoshlar_hub_web
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
set ADMIN_EMAIL=sizning@emailingiz.uz     # Mac/Linux: export ADMIN_EMAIL=...
python app.py
```

Brauzerda oching: http://127.0.0.1:5000

1. "Ro'yxatdan o'tish" orqali `ADMIN_EMAIL` dagi email bilan hisob yarating — shu hisob **Admin** paneliga kira oladi.
2. Admin → "Hozir yangilash" ni bosing, 20–30 soniyadan keyin sahifani yangilang.
3. Boshqa brauzerda (yoki inkognito oynada) ikkinchi hisob yarating: saqlanganlar va profil alohida ekanini ko'rasiz.

## 2. Internetga chiqarish (qisqacha)

Kerak: Python ishlaydigan server (Render, Railway, PythonAnywhere yoki o'zingizning VPS). Narx va tarif shartlari
o'zgarib turadi — tanlashdan oldin xizmatning o'z saytidan tekshiring.

Ishga tushirish buyrug'i:

```bash
gunicorn app:app --workers 2 --bind 0.0.0.0:8000
```

**Muhit o'zgaruvchilari** (hosting panelida kiritiladi):

| Nomi | Nima uchun |
|---|---|
| `SECRET_KEY` | **Majburiy (serverda).** Uzun tasodifiy matn: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL` | Admin bo'ladigan foydalanuvchi emaili |
| `SESSION_COOKIE_SECURE` | HTTPS bo'lsa `1` qo'ying |
| `DB_PATH` | Bazaning joyi. **Doimiy disk** (persistent volume) ko'rsating, aks holda server qayta ishga tushganda baza o'chib ketishi mumkin |
| `REFRESH_MINUTES` | Yangilash oralig'i (standart 30) |

**Muhim:**
- Faqat HTTPS orqali ishlating (hosting xizmatlari odatda sertifikatni o'zi beradi).
- SQLite fayli saqlanadigan joy doimiy bo'lishi shart. Bepul tariflarning ko'pida fayl tizimi vaqtinchalik bo'ladi — bunda foydalanuvchilar yo'qolishi mumkin.
- Ommaga ochishdan oldin `templates/privacy.html` ni o'z ma'lumotlaringiz bilan to'ldiring va
  shaxsiy ma'lumotlar to'g'risidagi qonun talablarini mutaxassis bilan tekshiring.
- Bazadan nusxa (backup) olib turing: `yoshlar.db` faylini nusxalash yetarli.

## 3. Fayllar

- `app.py` — server (kirish, profil, saqlanganlar, admin, avtomatik yangilash)
- `sources.py` — RSS manbalardan olish, kategoriya aniqlash, deadline topish
- `templates/`, `static/style.css` — sahifalar va dizayn
- `yoshlar.db` — ishga tushganda avtomatik yaratiladi (git ga qo'shmang)

## 4. Himoya choralari (nima bor)

Parollar hash qilinadi · CSRF himoyasi · login urinishlari cheklangan (5 ta / 15 daqiqa) ·
sessiya cookie `HttpOnly` + `SameSite` · XSS dan avtomatik escape · Content-Security-Policy ·
foydalanuvchi o'z hisobini o'chira oladi.

**Hali yo'q (keyingi bosqich uchun):** emailni tasdiqlash, "parolni unutdim", ikki bosqichli kirish.
