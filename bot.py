import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =================== SOZLAMALAR ===================
BOT_TOKEN = "7900980456:AAEZlR4zRWqkFeDfEU0j3KvWaPc5f4ZveRg"
ADMIN_ID = 6884014716
CHANNEL_USERNAME = "@kinolashamz"
DB_PATH = "./kino.db"
# ==================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect(DB_PATH)
cur = db.cursor()

# =================== DATABASE ===================
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    title TEXT,
    file_id TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS saved (
    user_id INTEGER,
    movie_id INTEGER,
    UNIQUE(user_id, movie_id)
)""")

db.commit()
# ===============================================

# =================== OBUNA ===================
async def check_sub(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

# =================== START ===================
@dp.message(F.text.startswith("/start"))
async def start(msg: Message):
    user = msg.from_user

    if not await check_sub(user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
        kb.button(text="🔄 Tekshirish", callback_data="check_sub")
        kb.adjust(2)
        await msg.answer("❗ Botdan foydalanish uchun kanalga obuna bo‘ling", reply_markup=kb.as_markup())
        return

    cur.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (user.id, user.username))
    db.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Inline qidiruv", switch_inline_query_current_chat="")
    kb.button(text="📂 Saqlangan kinolar", callback_data="saved")
    kb.adjust(1)

    await msg.answer("🎬 Kino botga xush kelibsiz!", reply_markup=kb.as_markup())

# =================== INLINE QIDIRUV ===================
@dp.inline_query()
async def inline_search(q: InlineQuery):
    text = q.query.strip()
    if not text:
        await q.answer([])
        return

    cur.execute("SELECT code,title FROM movies WHERE title LIKE ? LIMIT 20", (f"%{text}%",))
    rows = cur.fetchall()

    results = [
        InlineQueryResultArticle(
            id=code,
            title=title,
            description=f"Kod: {code}",
            input_message_content=InputTextMessageContent(
                message_text=f"🎬 {title}\n🔢 Kod: {code}"
            )
        )
        for code, title in rows
    ]
    await q.answer(results, cache_time=1)

# =================== KOD ORQALI ===================
@dp.message(F.text.regexp(r"^\d{3}$"))
async def by_code(msg: Message):
    if not await check_sub(msg.from_user.id):
        await msg.answer("❗ Avval kanalga obuna bo‘ling")
        return

    cur.execute("SELECT id,title,file_id FROM movies WHERE code=?", (msg.text,))
    m = cur.fetchone()
    if not m:
        await msg.answer("❌ Kino topilmadi")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 Saqlash", callback_data=f"save_{m[0]}")

    await bot.send_video(msg.chat.id, m[2], caption=f"🎬 {m[1]}", reply_markup=kb.as_markup())

# =================== SAQLASH ===================
@dp.callback_query(F.data.startswith("save_"))
async def save(call: CallbackQuery):
    mid = int(call.data.split("_")[1])
    cur.execute("INSERT OR IGNORE INTO saved VALUES (?,?)", (call.from_user.id, mid))
    db.commit()
    await call.answer("💾 Saqlandi")

# =================== SAQLANGANLAR ===================
@dp.callback_query(F.data == "saved")
@dp.message(F.text == "/saved")
async def saved(msg_or_call):
    uid = msg_or_call.from_user.id
    cur.execute("""
        SELECT movies.code, movies.title 
        FROM saved JOIN movies ON movies.id = saved.movie_id
        WHERE saved.user_id=?
    """, (uid,))
    rows = cur.fetchall()

    if not rows:
        await msg_or_call.answer("📂 Saqlangan kinolar yo‘q")
        return

    text = "📂 Saqlangan kinolar:\n\n" + "\n".join([f"{c} — {t}" for c, t in rows])
    await msg_or_call.answer(text)

# =================== TOP ===================
@dp.message(F.text == "/top")
async def top(msg: Message):
    cur.execute("""
        SELECT movies.title, COUNT(*) as cnt
        FROM saved JOIN movies ON movies.id = saved.movie_id
        GROUP BY movie_id ORDER BY cnt DESC LIMIT 10
    """)
    rows = cur.fetchall()

    if not rows:
        await msg.answer("📊 Ma’lumot yo‘q")
        return

    text = "🔥 TOP kinolar:\n\n"
    for i, (t, c) in enumerate(rows, 1):
        text += f"{i}. {t} — {c} ta\n"

    await msg.answer(text)

# =================== ADMIN PANEL ===================
@dp.message(F.text == "/panel")
async def panel(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Kino qo‘shish", callback_data="add")
    kb.button(text="📊 Stat", callback_data="stat")
    kb.button(text="📢 Broadcast", callback_data="send")
    kb.adjust(1)

    await msg.answer("🛠 Admin panel", reply_markup=kb.as_markup())

# =================== ADD MOVIE ===================
@dp.callback_query(F.data == "add")
async def add_info(call: CallbackQuery):
    await call.message.answer("🎬 Video yuboring\nFormat: 001|Kino nomi")

@dp.message(F.video & (F.from_user.id == ADMIN_ID))
async def add_movie(msg: Message):
    if not msg.caption or "|" not in msg.caption:
        await msg.answer("❗ 001|Kino nomi")
        return

    code, title = msg.caption.split("|", 1)
    code = code.strip()

    if not code.isdigit() or len(code) != 3:
        await msg.answer("❌ Kod 3 xonali bo‘lsin")
        return

    try:
        cur.execute("INSERT INTO movies(code,title,file_id) VALUES(?,?,?)",
                    (code, title.strip(), msg.video.file_id))
        db.commit()
        await msg.answer("✅ Kino qo‘shildi")
    except:
        await msg.answer("❌ Kod mavjud")

# =================== STAT ===================
@dp.callback_query(F.data == "stat")
async def stat(call: CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM users")
    u = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM movies")
    m = cur.fetchone()[0]
    await call.message.answer(f"👥 Users: {u}\n🎬 Movies: {m}")

# =================== BROADCAST ===================
@dp.callback_query(F.data == "send")
async def send_info(call: CallbackQuery):
    await call.message.answer("📢 Yuboriladigan xabarni yozing")

@dp.message(F.from_user.id == ADMIN_ID)
async def broadcast(msg: Message):
    if msg.text.startswith("/"):
        return
    cur.execute("SELECT user_id FROM users")
    for (uid,) in cur.fetchall():
        try:
            await bot.send_message(uid, msg.text)
        except:
            pass
    await msg.answer("✅ Yuborildi")

# =================== RUN ===================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
