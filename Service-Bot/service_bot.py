import asyncio
import logging
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice, PreCheckoutQuery, FSInputFile
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8547506087:AAE4nn8YmZVpwA5IU3nHU311xrFnKEyCpBw")

SUBSCRIPTION_PLANS = {
    "basic": {"name": "SELF-HOST", "price": 1, "duration_days": 30, "stars": 1, "equal": "(~199₽)"},
    "pro": {"name": "HOSTING", "price": 169, "duration_days": 30, "stars": 169, "equal": "(~299₽)"},
    "premium": {"name": "HOSTING-PRO", "price": 249, "duration_days": 30, "stars": 249, "equal": "(~449₽)"},
    "basic-year": {"name": "SELF-HOST", "price": 1090, "duration_days": 365, "stars": 1090, "equal": "(~1990₽)"},
    "pro-year": {"name": "HOSTING", "price": 1690, "duration_days": 365, "stars": 1690, "equal": "(~2990₽)"},
    "premium-year": {"name": "HOSTING-PRO", "price": 2490, "duration_days": 365, "stars": 2490, "equal": "(~4490₽)"}
}

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('service_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                license_key TEXT,
                subscription_plan TEXT,
                subscription_end_date TEXT,
                bot_token TEXT,
                api_id TEXT,
                api_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_keys (
                key TEXT PRIMARY KEY,
                user_id INTEGER,
                plan TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def create_user(self, telegram_id, username):
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)
        ''', (telegram_id, username))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user(self, telegram_id):
        self.cursor.execute('''
            SELECT * FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        return self.cursor.fetchone()
    
    def update_user_subscription(self, telegram_id, plan, license_key, end_date):
        self.cursor.execute('''
            UPDATE users SET 
                subscription_plan = ?, 
                license_key = ?, 
                subscription_end_date = ?
            WHERE telegram_id = ?
        ''', (plan, license_key, end_date, telegram_id))
        self.conn.commit()
    
    def update_user_bot_config(self, telegram_id, bot_token, api_id, api_hash):
        self.cursor.execute('''
            UPDATE users SET 
                bot_token = ?, 
                api_id = ?, 
                api_hash = ?
            WHERE telegram_id = ?
        ''', (bot_token, api_id, api_hash, telegram_id))
        self.conn.commit()
    
    def create_license_key(self, user_id, plan, duration_days):
        key = self.generate_license_key()
        expires_at = datetime.now() + timedelta(days=duration_days)
        
        self.cursor.execute('''
            INSERT INTO license_keys (key, user_id, plan, expires_at) VALUES (?, ?, ?, ?)
        ''', (key, user_id, plan, expires_at.isoformat()))
        self.conn.commit()
        return key
    
    def generate_license_key(self):
        return f"SB-{uuid.uuid4().hex[:16].upper()}"
    
    def validate_license_key(self, key):
        self.cursor.execute('''
            SELECT lk.*, u.telegram_id FROM license_keys lk
            JOIN users u ON lk.user_id = u.user_id
            WHERE lk.key = ? AND lk.is_active = 1 AND lk.expires_at > datetime('now')
        ''', (key,))
        return self.cursor.fetchone()

db = Database()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.create_user(message.from_user.id, message.from_user.username)
    
    keyboard = [
        [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")],
        [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="bot_settings")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Этот бот поможет вам настроить вашего собственного Telegram бота "
        "с функциями покупки подарков за звезды.\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup
    )

@dp.callback_query(F.data == "select_plan")
async def select_plan(callback: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="📅 Месячные подписки", callback_data="monthly_plans")],
        [InlineKeyboardButton(text="📅 Годовые подписки", callback_data="yearly_plans")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "📦 Выберите тип подписки:\n\n"
        "💰 <b>Годовые подписки</b> - экономия 2 месяца бесплатно!\n"
        "📅 <b>Месячные подписки</b> - гибкий платежный план\n\n"
        "Выберите тип подписки:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "monthly_plans")
async def show_monthly_plans(callback: CallbackQuery):
    keyboard = []
    monthly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if not k.endswith('-year')}
    
    for plan_id, plan_info in monthly_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{plan_info['name']} - {plan_info['stars']} ⭐/мес {plan_info['equal']}",
                callback_data=f"buy_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="select_plan")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "📅 <b>Месячные подписки</b>\n\nВыберите подходящий тариф:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("buy_plan_"))
async def buy_plan(callback: CallbackQuery):
    plan_id = callback.data.replace("buy_plan_", "")
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    
    if not plan:
        await callback.answer("❌ Неверный тарифный план", show_alert=True)
        return
    
    # Генерируем уникальный payload
    invoice_payload = f"plan_{plan_id}_{uuid.uuid4().hex[:8]}"
    
    # Цена в звездах (в центах для Telegram Stars)
    price_in_cents = plan["stars"]  # * 100

    try:
        # Отправляем инвойс
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Подписка {plan['name']}",
            description=f"Доступ к Service Bot на {plan['duration_days']} дней",
            payload=invoice_payload,
            provider_token="",  # Пустая строка для Telegram Stars
            currency="XTR",  # Код валюты Telegram Stars
            prices=[LabeledPrice(label=f"Подписка {plan['name']}", amount=price_in_cents)],
            max_tip_amount=0,
            suggested_tip_amounts=[]
        )
        
        await callback.message.edit_text(
            f"✅ Инвойс для тарифа <b>{plan['name']}</b> отправлен!\n\n"
            f"Проверьте чат с ботом, вам должно прийти платежное окно.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при создании платежа\n\n"
            f"<b>Причина:</b> {str(e)[:200]}\n\n"
            f"Проверьте настройки бота в @BotFather (Bot Settings → Telegram Stars)",
            parse_mode=ParseMode.HTML
        )

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payment = message.successful_payment
    
    payload_parts = payment.invoice_payload.split("_")
    plan_id = payload_parts[1] if len(payload_parts) > 1 else None
    
    if not plan_id or plan_id not in SUBSCRIPTION_PLANS:
        await message.answer("❌ Ошибка обработки платежа: неверный план")
        return
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    license_key = db.create_license_key(user[0], plan_id, plan["duration_days"])
    end_date = (datetime.now() + timedelta(days=plan["duration_days"])).isoformat()
    
    db.update_user_subscription(user_id, plan_id, license_key, end_date)
    
    keyboard = [
        [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton(text="⚙️ Настроить бота", callback_data="bot_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        f"✅ <b>Оплата успешно завершена!</b>\n\n"
        f"📋 <b>Детали подписки:</b>\n"
        f"• Тариф: {plan['name']}\n"
        f"• Срок: {plan['duration_days']} дней\n"
        f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
        f"Ваш лицензионный ключ сгенерирован!\n"
        f"Теперь вы можете настроить вашего бота.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "my_license")
async def my_license(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    if not user or not user[4]:  # subscription_plan
        keyboard = [[InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            "❌ У вас нет активной подписки.\n\n"
            "Выберите тариф для начала работы:",
            reply_markup=reply_markup
        )
        return
    
    plan = SUBSCRIPTION_PLANS.get(user[4])
    end_date = datetime.fromisoformat(user[5]) if user[5] else None
    
    license_info = f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{user[3]}</code>\n\n"
    license_info += f"📋 <b>Информация о подписке:</b>\n"
    license_info += f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
    license_info += f"• Статус: {'✅ Активна' if end_date and end_date > datetime.now() else '❌ Истекла'}\n"
    
    if end_date:
        license_info += f"• Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    keyboard = [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_license")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        license_info,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "bot_settings")
async def bot_settings(callback: CallbackQuery, state: FSMContext):
    user = db.get_user(callback.from_user.id)
    
    if not user or not user[4]:
        keyboard = [[InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            "❌ Сначала выберите тарифный план!",
            reply_markup=reply_markup
        )
        return
    
    config_status = "✅ Настроено" if user[6] and user[7] and user[8] else "❌ Не настроено"
    
    keyboard = [
        [InlineKeyboardButton(text=f"🤖 Токен бота: {'✅' if user[6] else '❌'}", callback_data="set_bot_token")],
        [InlineKeyboardButton(text=f"🔑 API ID: {'✅' if user[7] else '❌'}", callback_data="set_api_id")],
        [InlineKeyboardButton(text=f"🔐 API Hash: {'✅' if user[8] else '❌'}", callback_data="set_api_hash")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"Статус конфигурации: {config_status}\n\n"
        f"Для полноценной работы бота необходимо настроить:\n"
        f"• Токен вашего бота (от @BotFather)\n"
        f"• API ID и API Hash (от my.telegram.org)\n\n"
        f"Выберите параметр для настройки:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "help")
async def help_command(callback: CallbackQuery):
    help_text = """
ℹ️ <b>Помощь - Service Bot</b>

📄 Прочитайте файл для получения полной информации о настройке бота.

Поддержка:
Если у вас возникли вопросы, свяжитесь с @Dimopster.
    """
    
    keyboard = [[InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Сначала отправляем текст
    await callback.message.edit_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    # Отправляем файл
    try:
        # Проверяем наличие файла с разными возможными названиями
        possible_files = ["README.pdf", "Инструкция.pdf", "instruction.pdf"]
        file_to_send = None
        
        for file_name in possible_files:
            if os.path.exists(file_name):
                file_to_send = FSInputFile(file_name, filename="Инструкция.pdf")
                break
        
        if file_to_send:
            await bot.send_document(
                chat_id=callback.message.chat.id,
                document=file_to_send,
                caption="📖 Полная инструкция по настройке бота"
            )
        else:
            await callback.message.answer("❌ Файл инструкции не найден. Свяжитесь с поддержкой.")
    
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        await callback.message.answer("❌ Ошибка при отправке файла инструкции.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")],
        [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="bot_settings")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "👋 Добро пожаловать в Service Bot!\n\nВыберите действие ниже:",
        reply_markup=reply_markup
    )

async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())