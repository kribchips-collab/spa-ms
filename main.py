import os
import random
import sqlite3
import time

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# СЮДА ВСТАВЬ НОВЫЙ ТОКЕН (Старый засвечен, сбрось его в BotFather!)
TOKEN = "8799074728:AAHgmUBmEr4NXX8w8mpyZMS8epPWDzQoWBg"

CLIENTS = ["Бобр", "Герокс", "Редик", "Вебер", "Криб"]

# ---------- БАЗА ДАННЫХ ----------
db_folder = os.path.join("app", "data")
if not os.path.exists(db_folder):
    os.makedirs(db_folder)

db_path = os.path.join(db_folder, "spa.db")
db = sqlite3.connect(db_path, check_same_thread=False)
cursor = db.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        money INTEGER,
        spa_name TEXT,
        emoji TEXT,
        client TEXT,
        client_time INTEGER,
        heater_status INTEGER DEFAULT 1,
        bath_count INTEGER DEFAULT 1,
        repair_count INTEGER DEFAULT 0,
        achievements TEXT DEFAULT '',
        loan_time INTEGER DEFAULT 0,
        loan_amount INTEGER DEFAULT 0,
        item_beaver INTEGER DEFAULT 0,
        item_tea INTEGER DEFAULT 0,
        sword INTEGER DEFAULT 0,
        crab_time INTEGER DEFAULT 0
    )
    """)
    db.commit()

    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    needed = [
        ("loan_time", "INTEGER DEFAULT 0"), ("loan_amount", "INTEGER DEFAULT 0"),
        ("item_beaver", "INTEGER DEFAULT 0"), ("item_tea", "INTEGER DEFAULT 0"),
        ("sword", "INTEGER DEFAULT 0"), ("crab_time", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in needed:
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
    db.commit()

init_db()

# ---------- ДАННЫЕ ИГРЫ ----------
REVIEWS = {
    "Редик": '"Медный бык" лучшая ванна из всех!',
    "Бобр": '"Бобр деревянный... Крабы отступают..."',
    "Вебер": '"Пауков нету, не очень((("',
    "Герокс": '"Я будто бы снова сгнил в этой ванне!"',
    "Криб": '"Я получил зрение и снова его потерял от этого мыла"'
}

ACHIEVEMENTS = {
    "honeymoon": {"title": "Медовый Месяц", "desc": "Принять сразу Герокса и Криба"},
    "handyman": {"title": "Мастер на все руки", "desc": "Починить нагреватель 10 раз"}
}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    if user is None:
        user_data = (user_id, 0, "Мой СПА", "🧖", None, 0, 1, 1, 0, "", 0, 0, 0, 0, 0, 0)
        cursor.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", user_data)
        db.commit()
        return user_data
    return user

def menu():
    keyboard = [
        [InlineKeyboardButton("🧖 Спа", callback_data="spa")],
        [InlineKeyboardButton("💰 Взять в долг", callback_data="get_loan")],
        [InlineKeyboardButton("🏆 Рейтинг", callback_data="rating"), InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("⚙ Кастомизация", callback_data="custom"), InlineKeyboardButton("💬 Отзывы", callback_data="reviews")],
        [InlineKeyboardButton("🔥 Нагреватель", callback_data="heater"), InlineKeyboardButton("🎖 Достижения", callback_data="achievements")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_text(user):
    if not user: return "Ошибка загрузки данных."
    now = int(time.time())
    heater = "✅ работает" if user[6] else "❌ сломан"
    
    if user[15] > now:
        timeLeft = (user[15] - now) // 60
        status = f"🦀 ЗАХВАЧЕНО КРАБАМИ ({max(0, timeLeft)} мин)"
    elif user[4]:
        status = f"👤 В гостях: {user[4].replace(',', ', ')}"
    else:
        status = "✨ Сейчас никого нет"

    txt = f"{user[3]} {user[2]}\n\n💰 Деньги: {user[1]}\n🔥 Нагреватель: {heater}\n🛁 Ванные: {user[7]}\n"
    if user[14]: txt += "⚔️ Меч: В наличии\n"
    txt += f"--------------------\n{status}"
    
    if user[11] > 0:
        l_left = max(0, 14400 - (now - user[10]))
        txt += f"\n⚠️ Долг: {user[11]}💰 (списание через {l_left//60} мин)"
    
    return txt

# ---------- ОБРАБОТЧИКИ КНОПОК ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(menu_text(user), reply_markup=menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    user = get_user(user_id) # Загружаем юзера сразу
    
    try: await query.answer()
    except: pass

    if not user:
        return # Если юзер не нашелся, ничего не делаем

    if data == "spa":
        await handle_spa_logic(update, context)
    elif data == "rating":
        cursor.execute("SELECT spa_name, emoji, money FROM users ORDER BY money DESC LIMIT 5")
        top = cursor.fetchall()
        txt = "🏆 ТОП СПА-САЛОНОВ:\n\n"
        for i, p in enumerate(top, 1): txt += f"{i}. {p[1]} {p[0]} — {p[2]}💰\n"
        await query.message.edit_text(txt, reply_markup=menu())
    elif data == "custom":
        context.user_data["custom"] = True
        await query.message.edit_text("Введите новое название вашего салона!:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Назад", callback_data="back")]]))
    elif data == "reviews":
        all_reviews = list(REVIEWS.values())
        recent_reviews = all_reviews[-5:]
        txt = f"💬 Последние отзывы:\n\n" + "\n\n".join(recent_reviews)
        await query.message.edit_text(txt, reply_markup=menu())
    elif data == "heater":
        status = "✅ работает" if user[6] else "❌ сломан. Почините в магазине!"
        await query.message.edit_text(f"🔥 Нагреватель: {status}", reply_markup=menu())
    elif data == "achievements":
        u_achs = user[9].split(",") if user[9] else []
        txt = "🎖 Ваши достижения:\n\n"
        for k, a in ACHIEVEMENTS.items():
            txt += f"{'✅' if k in u_achs else '❌'} {a['title']} — {a['desc']}\n"
        await query.message.edit_text(txt, reply_markup=menu())
    elif data == "get_loan":
        now = int(time.time())
        if user[11] > 0: await query.message.edit_text(menu_text(user)+"\n❌ Долг уже активен!", reply_markup=menu())
        elif now - user[10] < 86400 and user[10] != 0: await query.message.edit_text(menu_text(user)+"\n❌ Можно брать раз в сутки!", reply_markup=menu())
        else:
            cursor.execute("UPDATE users SET money=money+50, loan_time=?, loan_amount=100 WHERE id=?", (now, user_id))
            db.commit()
            await query.message.edit_text(menu_text(get_user(user_id))+"\n💸 Вы взяли 50💰!", reply_markup=menu())
    elif data == "shop":
        await show_shop(update)
    elif data in ["fix_heater", "buy_bath", "buy_beaver", "buy_tea", "buy_sword", "back"]:
        await handle_shop_logic(update, data)

# ---------- ЛОГИКА СПА И КРАБОВ ----------
async def handle_spa_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    now = int(time.time())

    if user[15] > now:
        await query.message.edit_text(menu_text(user) + "\n\n🦀 КРАБЫ! Ждите завершения осады.", reply_markup=menu())
        return

    if random.random() < 0.025:
        if user[14] == 1:
            cursor.execute("UPDATE users SET sword=0 WHERE id=?", (user_id,))
            db.commit()
            await query.message.edit_text(menu_text(get_user(user_id)) + "\n\n⚔️ ПАЛУНДРА! Крабы напали, но вы уничтожили их мечом!", reply_markup=menu())
        else:
            cursor.execute("UPDATE users SET crab_time=? WHERE id=?", (now + 1800, user_id))
            db.commit()
            await query.message.edit_text(menu_text(get_user(user_id)) + "\n\n🦀 ПАЛУНДРА! Крабы захватили салон на 30 минут!", reply_markup=menu())
        return

    if user[4] is not None:
        await query.message.edit_text(menu_text(user) + "\n\n⏳ Ванны заняты!", reply_markup=menu())
        return

    clients = []
    for _ in range(user[7]):
        roll = random.random()
        if user[12] == 1 and roll < 0.20: clients.append("🦫 Большой Бобёр")
        elif user[13] == 1 and roll < 0.15: clients.append("🔮 Аметистовый Незнакомец")
        else: clients.append(random.choice(CLIENTS))

    cursor.execute("UPDATE users SET client=?, client_time=? WHERE id=?", (",".join(clients), now, user_id))
    db.commit()
    await query.message.edit_text(menu_text(get_user(user_id)) + f"\n\n✨ Гости зашли: {', '.join(clients)}", reply_markup=menu())

# ---------- МАГАЗИН ----------
async def show_shop(update: Update):
    user = get_user(update.callback_query.from_user.id)
    kb = []
    if user[7] < 2: kb.append([InlineKeyboardButton("🛁 2-я ванна (50💰)", callback_data="buy_bath")])
    kb.append([InlineKeyboardButton("🔧 Ремонт (25💰)", callback_data="fix_heater")])
    if user[12] == 0: kb.append([InlineKeyboardButton("🪵 Статуэтка Бобра (150💰)", callback_data="buy_beaver")])
    if user[13] == 0: kb.append([InlineKeyboardButton("🍵 Пакетик Чая (200💰)", callback_data="buy_tea")])
    if user[14] == 0: kb.append([InlineKeyboardButton("⚔️ Стальной меч (300💰)", callback_data="buy_sword")])
    kb.append([InlineKeyboardButton("⬅ Назад", callback_data="back")])
    await update.callback_query.message.edit_text("🛒 МАГАЗИН:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_shop_logic(update: Update, data: str):
    u_id = update.callback_query.from_user.id
    user = get_user(u_id)
    
    if data == "back":
        await update.callback_query.message.edit_text(menu_text(user), reply_markup=menu())
        return

    price_map = {"fix_heater": 25, "buy_bath": 50, "buy_beaver": 150, "buy_tea": 200, "buy_sword": 300}
    price = price_map.get(data, 999999)
    
    if user[1] >= price:
        if data == "fix_heater": cursor.execute("UPDATE users SET money=money-25, heater_status=1 WHERE id=?", (u_id,))
        elif data == "buy_bath": cursor.execute("UPDATE users SET money=money-50, bath_count=2 WHERE id=?", (u_id,))
        elif data == "buy_beaver": cursor.execute("UPDATE users SET money=money-150, item_beaver=1 WHERE id=?", (u_id,))
        elif data == "buy_tea": cursor.execute("UPDATE users SET money=money-200, item_tea=1 WHERE id=?", (u_id,))
        elif data == "buy_sword": cursor.execute("UPDATE users SET money=money-300, sword=1 WHERE id=?", (u_id,))
        db.commit()
        await update.callback_query.message.edit_text("✅ Успешно куплено!", reply_markup=menu())
    else:
        await update.callback_query.message.edit_text("💰 Недостаточно денег!", reply_markup=menu())

# ---------- ОБРАБОТКА ТЕКСТА ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("custom"):
        new_name = update.message.text.strip()
        emojis = ["🦀", "🐻", "🦁", "🐬", "🦑", "🐹", "🧖"]
        found_emoji = next((c for c in new_name if c in emojis), "🧖")
        clean_name = "".join([c for c in new_name if c not in emojis]).strip()
        cursor.execute("UPDATE users SET spa_name=?, emoji=? WHERE id=?", (clean_name or "СПА", found_emoji, update.effective_user.id))
        db.commit()
        context.user_data["custom"] = False
        await update.message.reply_text("✅ Название обновлено!", reply_markup=menu())

# ---------- ФОНОВЫЙ ЧЕКЕР ----------
async def client_checker(context: ContextTypes.DEFAULT_TYPE):
    now = int(time.time())
    cursor.execute("SELECT id, loan_time, loan_amount FROM users WHERE loan_amount > 0")
    for u_id, l_t, l_a in cursor.fetchall():
        if now - l_t >= 14400:
            cursor.execute("UPDATE users SET money=money-?, loan_amount=0 WHERE id=?", (l_a, u_id))
            db.commit()
            try: await context.bot.send_message(u_id, "📢 Срок долга истек! Списано 100💰.")
            except: pass

    cursor.execute("SELECT id, client_time, client, heater_status FROM users WHERE client IS NOT NULL")
    for u_id, c_t, c_names, h_s in cursor.fetchall():
        if now - c_t >= 300:
            pay = 0
            for c in c_names.split(","):
                if "Бобёр" in c: pay += 150
                elif "Незнакомец" in c: pay += 200
                else: pay += 50
            
            if h_s:
                cursor.execute("UPDATE users SET money=money+?, client=NULL WHERE id=?", (pay, u_id))
                msg = f"✅ Гости ушли и заплатили {pay}💰!"
            else:
                cursor.execute("UPDATE users SET client=NULL WHERE id=?", (u_id,))
                msg = "❌ Гости ушли недовольными из-за холодной воды!"
            db.commit()
            try: await context.bot.send_message(u_id, msg)
            except: pass

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    if app.job_queue:
        app.job_queue.run_repeating(client_checker, interval=30)

    print("Бот успешно запущен!")
    app.run_polling()
