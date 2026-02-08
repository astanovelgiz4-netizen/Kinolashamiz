import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import *
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =================== SOZLAMALAR ===================
BOT_TOKEN = "7900980456:AAEZlR4zRWqkFeDfEU0j3KvWaPc5f4ZveRg"
ADMIN_ID = 6884014716
CHANNEL_USERNAME = "@kinolashamz"
# ==================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect("kino.db")
cur = db.cursor()

# =================== DATABASE ======================
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    title TEXT,
    file_id TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS saved (
    user_id INTEGER,
    movie_id INTEGER
)
""")

db.commit()
# ==================================================

# =================== OBUNA TEKSHIRISH ===================
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# =================== START ===================
@dp.message(F.text.startswith("/start"))
async def start(msg: Message):
    user_name = msg.from_user.full_name
    text = msg.text

    param = None
    if len(text.split()) > 1:
        param = text.split()[1]

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Kanalga obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
    kb.button(text="🔍 Tekshirish", callback_data="check_sub")
    kb.adjust(2)

    if not await check_sub(msg.from_user.id):
        await msg.answer(
            f"Salom {user_name}!\nBotdan foydalanish uchun kanalga obuna bo‘ling 👇",
            reply_markup=kb.as_markup()
        )
        return

    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?)",
        (msg.from_user.id, msg.from_user.username)
    )
    db.commit()

    if param and param.isdigit() and len(param) == 3:
        cur.execute("SELECT title, file_id FROM movies WHERE code=?", (param,))
        movie = cur.fetchone()
        if movie:
            await bot.send_video(
                msg.chat.id,
                movie[1],
                caption=f"🎬 {movie[0]}\n🔢 Kod: {param}"
            )
        else:
            await msg.answer("❌ Bu kodda kino topilmadi")

    kb2 = InlineKeyboardBuilder()
    kb2.button(text="🔍 Inline qidiruv", switch_inline_query_current_chat="")
    kb2.adjust(1)

    await msg.answer(
        f"🎬 Xush kelibsiz, {user_name}!\n\n"
        f"🔎 Inline qidiruv orqali kino toping yoki 3 xonali kod yuboring.",
        reply_markup=kb2.as_markup()
    )

# =================== OBUNA TEKSHIRISH TUGMASI ===================
@dp.callback_query(F.data == "check_sub")
async def check_subscription(call: CallbackQuery):
    if await check_sub(call.from_user.id):
        cur.execute(
            "INSERT OR IGNORE INTO users VALUES (?,?)",
            (call.from_user.id, call.from_user.username)
        )
        db.commit()

        kb2 = InlineKeyboardBuilder()
        kb2.button(text="🔍 Inline qidiruv", switch_inline_query_current_chat="")
        kb2.adjust(1)

        await call.message.edit_text(
            "✅ Obuna tasdiqlandi!\nInline qidiruvdan foydalanishingiz mumkin.",
            reply_markup=kb2.as_markup()
        )
    else:
        await call.answer("❌ Hali obuna bo‘lmadingiz", show_alert=True)

# =================== INLINE QIDIRUV (TO‘G‘RILANGAN) ===================
@dp.inline_query()
async def inline_search(query: InlineQuery):
    text = query.query.strip()

    if not text:
        await query.answer([], cache_time=1)
        return

    cur.execute(
        "SELECT code, title FROM movies WHERE title LIKE ? LIMIT 20",
        (f"%{text}%",)
    )
    movies = cur.fetchall()

    results = []
    for code, title in movies:
        results.append(
            InlineQueryResultArticle(
                id=code,
                title=title,
                description=f"Kod: {code}",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎬 {title}\n🔢 Kod: {code}\n\n👉 Kodni botga yuboring"
                )
            )
        )

    await query.answer(results, cache_time=1)

# =================== KOD ORQALI KINO ===================
@dp.message(F.text.regexp(r"^\d{3}$"))
async def by_code(msg: Message):
    if not await check_sub(msg.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Kanalga obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
        kb.button(text="🔍 Tekshirish", callback_data="check_sub")
        kb.adjust(2)
        await msg.answer("❗ Avval kanalga obuna bo‘ling", reply_markup=kb.as_markup())
        return

    cur.execute("SELECT id, title, file_id FROM movies WHERE code=?", (msg.text,))
    movie = cur.fetchone()
    if not movie:
        await msg.answer("❌ Bu kodda kino topilmadi")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="💾 Saqlash", callback_data=f"save_{movie[0]}")

    await bot.send_video(
        msg.chat.id,
        movie[2],
        caption=f"🎬 {movie[1]}\n🔢 Kod: {msg.text}",
        reply_markup=kb.as_markup()
    )

# =================== SAQLASH ===================
@dp.callback_query(F.data.startswith("save_"))
async def save_movie(call: CallbackQuery):
    movie_id = int(call.data.split("_")[1])
    cur.execute("INSERT INTO saved VALUES (?,?)", (call.from_user.id, movie_id))
    db.commit()
    await call.answer("💾 Saqlandi")

# =================== ADMIN PANEL ===================
@dp.message(F.text == "/panel")
async def panel(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Kino qo‘shish", callback_data="add")
    kb.button(text="🗑 Kino o‘chirish", callback_data="del")
    kb.button(text="📊 Statistika", callback_data="stat")
    kb.button(text="📢 Xabar yuborish", callback_data="send")
    kb.adjust(1)

    await msg.answer("🛠 Admin panel", reply_markup=kb.as_markup())

# =================== KINO QO‘SHISH ===================
@dp.callback_query(F.data == "add")
async def add_info(call: CallbackQuery):
    await call.message.answer("🎬 Video yuboring\nCaption: `001|Kino nomi`")

@dp.message(F.video & (F.from_user.id == ADMIN_ID))
async def add_movie(msg: Message):
    if not msg.caption or "|" not in msg.caption:
        await msg.answer("❗ Format: 001|Kino nomi")
        return

    code, title = msg.caption.split("|", 1)
    try:
        cur.execute(
            "INSERT INTO movies (code,title,file_id) VALUES (?,?,?)",
            (code.strip(), title.strip(), msg.video.file_id)
        )
        db.commit()
        await msg.answer("✅ Kino qo‘shildi")
    except:
        await msg.answer("❌ Bu kod mavjud")

# =================== STAT ===================
@dp.callback_query(F.data == "stat")
async def stat(call: CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM movies")
    movies = cur.fetchone()[0]

    await call.message.answer(
        f"📊 Statistika\n👥 Foydalanuvchilar: {users}\n🎬 Kinolar: {movies}"
    )

# =================== RUN ===================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
