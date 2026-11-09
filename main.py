import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

TOKEN = "SIZNING_BOT_TOKENINGIZ"
MAIN_ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ==========================================
# 1. SQLITE BAZA BILAN ISHLASH FUNKSIYALARI
# ==========================================

def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    
    # Narxlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        service_name TEXT PRIMARY KEY,
        price INTEGER
    )
    """)
    
    # Sozlamalar va rekvizitlar
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Foydalanuvchilar jadvali (Sana, vaqt va statusi bilan)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        joined_date TEXT,
        is_blocked INTEGER DEFAULT 0
    )
    """)
    
    # Adminlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        admin_id INTEGER PRIMARY KEY
    )
    """)
    
    # Majburiy obuna kanallari jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT
    )
    """)
    
    # Boshlang'ich qiymatlar
    cursor.execute("INSERT OR IGNORE INTO prices (service_name, price) VALUES ('Telegram Premium 1 oy', 35000)")
    cursor.execute("INSERT OR IGNORE INTO prices (service_name, price) VALUES ('Telegram Premium 1 yil', 250000)")
    cursor.execute("INSERT OR IGNORE INTO prices (service_name, price) VALUES ('100 Telegram Stars', 20000)")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_info', 'Humo/Uzcard: 8600 0000 0000 0000\nIsm Familiya')")
    
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (user_id, username, joined_date, is_blocked) VALUES (?, ?, ?, 0)", 
                       (user_id, username, joined_date))
        conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, is_blocked FROM users")
    res = cursor.fetchall()
    conn.close()
    return res

def set_user_block(user_id, status):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def is_user_blocked(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def is_admin(user_id, main_admin_id):
    if user_id == main_admin_id:
        return True
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return True if res else False

def add_admin(admin_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))
    conn.commit()
    conn.close()

def remove_admin(admin_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admins")
    res = cursor.fetchall()
    conn.close()
    return [row[0] for row in res]

def get_price(service_name):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT price FROM prices WHERE service_name = ?", (service_name,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 0

def update_price(service_name, new_price):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE prices SET price = ? WHERE service_name = ?", (new_price, service_name))
    conn.commit()
    conn.close()

def get_card():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'card_info'")
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "Karta topilmadi"

def update_card(new_card):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'card_info'", (new_card,))
    conn.commit()
    conn.close()

def get_all_prices():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT service_name, price FROM prices")
    res = cursor.fetchall()
    conn.close()
    return res

def add_channel(channel_id, channel_name):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO channels (channel_id, channel_name) VALUES (?, ?)", (channel_id, channel_name))
    conn.commit()
    conn.close()

def remove_channel(channel_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()

def get_channels():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name FROM channels")
    res = cursor.fetchall()
    conn.close()
    return res


# ==========================================
# 2. BOT HOLATLARI (FSM)
# ==========================================

class AdminState(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_new_card = State()
    waiting_for_broadcast = State()
    waiting_for_new_admin_id = State()
    waiting_for_del_admin_id = State()
    waiting_for_channel_id = State()
    service_name = State()

class OrderState(StatesGroup):
    waiting_for_screenshot = State()


# ==========================================
# 3. MAJBURIY OBUNANI TEKSHIRISH
# ==========================================

async def check_subscription(user_id: int):
    channels = get_channels()
    if not channels:
        return True
    
    for ch_id, ch_name in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except TelegramBadRequest:
            return False
    return True


# ==========================================
# 4. BOT HANDLERLARI (BUYRUQLAR VA TUGMALAR)
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Nomalum"
    
    add_user(user_id, username)
    
    if is_user_blocked(user_id):
        await message.answer("Siz botdan bloklangansiz ❌")
        return

    if not await check_subscription(user_id):
        channels = get_channels()
        kb = InlineKeyboardBuilder()
        for ch_id, ch_name in channels:
            try:
                chat = await bot.get_chat(ch_id)
                invite_link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else "https://t.me/")
            except:
                invite_link = "https://t.me/"
            kb.button(text=f"📢 {ch_name}", url=invite_link)
        kb.button(text="✅ Obunani tekshirish", callback_data="check_sub")
        kb.adjust(1)
        
        await message.answer("Botimizdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:", reply_markup=kb.as_markup())
        return

    await show_main_menu(message)

async def show_main_menu(message: types.Message):
    user_id = message.from_user.id
    kb = ReplyKeyboardBuilder()
    kb.button(text="⭐ Telegram Stars sotib olish")
    kb.button(text="💎 Telegram Premium sotib olish")
    if is_admin(user_id, MAIN_ADMIN_ID):
        kb.button(text="⚙️ Admin Panel")
    kb.adjust(1)
    
    await message.answer(
        "Assalomu alaykum! Botimiz orqali Telegram Premium va Stars xizmatlarini xarid qilishingiz mumkin.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.delete()
        await show_main_menu(callback.message)
    else:
        await callback.answer("Siz hali hamma kanallarga obuna bo'lmadingiz! ❌", show_alert=True)

# Foydalanuvchi qismi (Xizmatlar)
@dp.message(F.text == "💎 Telegram Premium sotib olish")
async def premium_menu(message: types.Message):
    if is_user_blocked(message.from_user.id): return
    p_1m = get_price('Telegram Premium 1 oy')
    p_1y = get_price('Telegram Premium 1 yil')
    
    kb = InlineKeyboardBuilder()
    kb.button(text=f"1 Oylik - {p_1m} so'm", callback_data="buy_Telegram Premium 1 oy")
    kb.button(text=f"1 Yillik - {p_1y} so'm", callback_data="buy_Telegram Premium 1 yil")
    kb.adjust(1)
    
    await message.answer("Kerakli muddatni tanlang:", reply_markup=kb.as_markup())

@dp.message(F.text == "⭐ Telegram Stars sotib olish")
async def stars_menu(message: types.Message):
    if is_user_blocked(message.from_user.id): return
    p_100 = get_price('100 Telegram Stars')
    
    kb = InlineKeyboardBuilder()
    kb.button(text=f"100 Stars - {p_100} so'm", callback_data="buy_100 Telegram Stars")
    kb.adjust(1)
    
    await message.answer("Kerakli miqdorni tanlang:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    service = callback.data.replace("buy_", "")
    price = get_price(service)
    card = get_card()
    
    await state.update_data(service=service)
    text = (
        f"Siz tanlagan xizmat: <b>{service}</b>\n"
        f"Narxi: <b>{price} so'm</b>\n\n"
        f"To'lov uchun karta:\n<code>{card}</code>\n\n"
        f"Pulni o'tkazgandan so'ng, chek (skrinshot) rasmini yuboring!"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(OrderState.waiting_for_screenshot)
    await callback.answer()

@dp.message(OrderState.waiting_for_screenshot, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    service = data.get("service")
    photo_id = message.photo[-1].file_id
    
    admin_text = (
        f"📥 <b>Yangi buyurtma!</b>\n\n"
        f"Foydalanuvchi: @{message.from_user.username} (<code>{message.from_user.id}</code>)\n"
        f"Xizmat: <b>{service}</b>"
    )
    
    all_admins = get_all_admins() + [MAIN_ADMIN_ID]
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"approve_{message.from_user.id}")
    kb.button(text="❌ Rad etish", callback_data=f"reject_{message.from_user.id}")
    
    for adm in set(all_admins):
        try:
            await bot.send_photo(adm, photo_id, caption=admin_text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except:
            pass
            
    await message.answer("Buyurtmangiz adminga yuborildi!")
    await state.clear()


# ==========================================
# 5. ADMIN PANEL QISMI
# ==========================================

@dp.message(F.text == "⚙️ Admin Panel")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id, MAIN_ADMIN_ID):
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Narxlarni o'zgartirish", callback_data="adm_prices")
    kb.button(text="💳 Rekvizitni o'zgartirish", callback_data="adm_card")
    kb.button(text="📢 Ommaviy xabar", callback_data="adm_broadcast")
    kb.button(text="👥 Foydalanuvchini bloklash/ochish", callback_data="adm_block_menu")
    kb.button(text="➕ Admin qo'shish/o'chirish", callback_data="adm_admins_menu")
    kb.button(text="📌 Majburiy obuna kanallari", callback_data="adm_channels_menu")
    kb.adjust(1)
    
    await message.answer("⚙️ <b>Admin boshqaruv paneli:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")

# Narxlar
@dp.callback_query(F.data == "adm_prices")
async def admin_prices(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id, MAIN_ADMIN_ID): return
    prices = get_all_prices()
    kb = InlineKeyboardBuilder()
    for service, price in prices:
        kb.button(text=f"✏️ {service} ({price})", callback_data=f"editprice_{service}")
    kb.button(text="« Orqaga", callback_data="back_to_admin")
    kb.adjust(1)
    await callback.message.edit_text("Xizmat narxini tanlang:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("editprice_"))
async def edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    service = callback.data.replace("editprice_", "")
    await state.update_data(service_name=service)
    await callback.message.answer(f"<b>{service}</b> uchun yangi narxni kiriting:", parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_new_price)
    await callback.answer()

@dp.message(AdminState.waiting_for_new_price, F.text)
async def save_new_price(message: types.Message, state: FSMContext):
    try:
        new_price = int(message.text)
        data = await state.get_data()
        service = data.get("service_name")
        update_price(service, new_price)
        await message.answer(f"Muvaffaqiyatli! <b>{service}</b> narxi yangilandi.", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("Faqat raqam kiriting!")

# Rekvizit
@dp.callback_query(F.data == "adm_card")
async def edit_card_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id, MAIN_ADMIN_ID): return
    current_card = get_card()
    await callback.message.answer(f"Joriy rekvizit:\n<code>{current_card}</code>\n\nYangi rekvizitni yuboring:", parse_mode="HTML")
    await state.set_state(AdminState.waiting_for_new_card)
    await callback.answer()

@dp.message(AdminState.waiting_for_new_card, F.text)
async def save_new_card(message: types.Message, state: FSMContext):
    update_card(message.text)
    await message.answer("To'lov rekvizitlari yangilandi!")
    await state.clear()

# Broadcast (Ommaviy xabar)
@dp.callback_query(F.data == "adm_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id, MAIN_ADMIN_ID): return
    await callback.message.answer("Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:")
    await state.set_state(AdminState.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    users = get_all_users()
    success, fail = 0, 0
    await message.answer("Ommaviy xabar yuborish boshlandi...")
    for user_id, is_bl in users:
        try:
            await message.send_copy(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    await message.answer(f"Tugatildi ✅\n\nMuvaffaqiyatli: {success}\nXato: {fail}")
    await state.clear()

# Bloklash / Ochish
@dp.callback_query(F.data == "adm_block_menu")
async def block_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id, MAIN_ADMIN_ID): return
    users = get_all_users()
    kb = InlineKeyboardBuilder()
    for uid, bl in users:
        status = "🔴 Blok" if bl else "🟢 Aktiv"
        kb.button(text=f"ID: {uid} - {status}", callback_data=f"toggleblock_{uid}")
    kb.button(text="« Orqaga", callback_data="back_to_admin")
    kb.adjust(1)
    await callback.message.edit_text("Foydalanuvchini tanlang:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("toggleblock_"))
async def toggle_block(callback: types.CallbackQuery):
    uid = int(callback.data.replace("toggleblock_", ""))
    current_status = is_user_blocked(uid)
    new_status = 0 if current_status else 1
    set_user_block(uid, new_status)
    await callback.answer(f"Status o'zgartirildi!")
    await block_menu(callback)

# Adminlar boshqaruvi
@dp.callback_query(F.data == "adm_admins_menu")
async def admins_menu(callback: types.CallbackQuery):
    if callback.from_user.id != MAIN_ADMIN_ID:
        await callback.answer("Faqat asosiy bot egasi uchun!", show_alert=True)
        return
    admins = get_all_admins()
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Admin qo'shish", callback_data="add_admin_btn")
    for adm in admins:
        kb.button(text=f"❌ O'chirish: {adm}", callback_data=f"deladmin_{adm}")
    kb.button(text="« Orqaga", callback_data="back_to_admin")
    kb.adjust(1)
    await callback.message.edit_text(f"Joriy adminlar ID lari:\n{admins}", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "add_admin_btn")
async def add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi adminning Telegram ID raqamini yuboring:")
    await state.set_state(AdminState.waiting_for_new_admin_id)
    await callback.answer()

@dp.message(AdminState.waiting_for_new_admin_id, F.text)
async def save_new_admin(message: types.Message, state: FSMContext):
    try:
        new_adm = int(message.text)
        add_admin(new_adm)
        await message.answer(f"ID: {new_adm} admin qilindi!")
        await state.clear()
    except ValueError:
        await message.answer("Faqat raqam kiriting!")

@dp.callback_query(F.data.startswith("deladmin_"))
async def delete_admin(callback: types.CallbackQuery):
    adm_id = int(callback.data.replace("deladmin_", ""))
    remove_admin(adm_id)
    await callback.answer("Admin o'chirildi!")
    await admins_menu(callback)

# Majburiy obuna kanallari
@dp.callback_query(F.data == "adm_channels_menu")
async def channels_menu(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id, MAIN_ADMIN_ID): return
    channels = get_channels()
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Kanal qo'shish", callback_data="add_chan_btn")
    for ch_id, ch_name in channels:
        kb.button(text=f"❌ O'chirish: {ch_name}", callback_data=f"delchan_{ch_id}")
    kb.button(text="« Orqaga", callback_data="back_to_admin")
    kb.adjust(1)
    await callback.message.edit_text("Majburiy obuna kanallari:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "add_chan_btn")
async def add_chan_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal username yoki ID raqamini yuboring (Masalan: @kanal yoki -100...):\n\n*Bot kanalga admin bo'lishi shart!*")
    await state.set_state(AdminState.waiting_for_channel_id)
    await callback.answer()

@dp.message(AdminState.waiting_for_channel_id, F.text)
async def save_channel(message: types.Message, state: FSMContext):
    ch_input = message.text.strip()
    try:
        chat = await bot.get_chat(ch_input)
        add_channel(str(chat.id), chat.title)
        await message.answer(f"<b>{chat.title}</b> kanali qo'shildi! ✅", parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(f"Xatolik! Bot kanalni topolmadi yoki admin emas. Xato: {e}")

@dp.callback_query(F.data.startswith("delchan_"))
async def delete_channel(callback: types.CallbackQuery):
    ch_id = callback.data.replace("delchan_", "")
    remove_channel(ch_id)
    await callback.answer("Kanal o'chirildi!")
    await channels_menu(callback)

@dp.callback_query(F.data == "back_to_admin")
async def back_admin(callback: types.CallbackQuery):
    await admin_panel(callback.message)
    await callback.answer()


# ==========================================
# 6. ISHGA TUSHIRish (MAIN)
# ==========================================

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
