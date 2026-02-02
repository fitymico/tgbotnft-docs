import asyncio
import logging
import sqlite3
import uuid
import os
from datetime import datetime, timedelta
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, 
    InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice, PreCheckoutQuery, FSInputFile
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан. Установите переменную окружения BOT_TOKEN.")

ADMIN_IDS = set()
for raw_id in os.getenv("ADMIN_IDS", "").split(","):
    raw_id = raw_id.strip()
    if raw_id.isdigit():
        ADMIN_IDS.add(int(raw_id))

# Обратная совместимость: если задан ADMIN_ID (старый формат)
_legacy = os.getenv("ADMIN_ID", "").strip()
if _legacy.isdigit():
    ADMIN_IDS.add(int(_legacy))

if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS не задан. Установите переменную окружения ADMIN_IDS (или ADMIN_ID).")

SERVER_API_ID = int(os.getenv("SERVER_API_ID", "0"))
SERVER_API_HASH = os.getenv("SERVER_API_HASH", "")
WEB_AUTH_HOST = os.getenv("WEB_AUTH_HOST", "http://localhost:8082")
WEB_AUTH_PORT = int(os.getenv("WEB_AUTH_PORT", "8082"))

SUBSCRIPTION_PLANS = {
    "basic": {"name": "SELF-HOST", "price": 1, "duration_days": 30, "stars": 1, "equal": "(~199₽)"},
    "pro": {"name": "HOSTING", "price": 169, "duration_days": 30, "stars": 169, "equal": "(~299₽)"},
    "premium": {"name": "HOSTING-PRO", "price": 249, "duration_days": 30, "stars": 249, "equal": "(~449₽)"},
    "basic-year": {"name": "SELF-HOST", "price": 1090, "duration_days": 365, "stars": 1090, "equal": "(~1990₽)"},
    "pro-year": {"name": "HOSTING", "price": 1690, "duration_days": 365, "stars": 1690, "equal": "(~2990₽)"},
    "premium-year": {"name": "HOSTING-PRO", "price": 2490, "duration_days": 365, "stars": 2490, "equal": "(~4490₽)"}
}

class BotSetupStates(StatesGroup):
    waiting_bot_token = State()

class UserStates(StatesGroup):
    waiting_admin_message = State()

class AdminStates(StatesGroup):
    waiting_user_search = State()
    waiting_message_text = State()
    waiting_refund_txn = State()

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('service_bot.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
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
                session_string TEXT,
                has_used_refund BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refund_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                license_key TEXT,
                stars_amount INTEGER,
                status TEXT DEFAULT 'pending', -- pending, approved, rejected
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            user_id INTEGER,
            license_key TEXT,
            stars_amount INTEGER,
            telegram_payment_charge_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            license_key TEXT,
            reminder_type TEXT,
            scheduled_time TEXT,
            sent BOOLEAN DEFAULT 0,
            sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS queued_subscriptions (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            telegram_id INTEGER,
            plan TEXT,
            stars_amount INTEGER,
            telegram_payment_charge_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        try:
            cursor.execute('ALTER TABLE users ADD COLUMN session_string TEXT')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('ALTER TABLE users ADD COLUMN deployment_status TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('ALTER TABLE users ADD COLUMN container_id TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute('ALTER TABLE users ADD COLUMN vps_ip TEXT DEFAULT NULL')
        except sqlite3.OperationalError:
            pass

        self.conn.commit()
    
    def save_payment(self, user_id, license_key, stars_amount, telegram_payment_charge_id):
        """Сохранить информацию о платеже"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO payments (payment_id, user_id, license_key, stars_amount, telegram_payment_charge_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_payment_charge_id, user_id, license_key, stars_amount, telegram_payment_charge_id))
        self.conn.commit()

    def get_payment_by_license(self, license_key):
        """Получить платеж по лицензии"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM payments WHERE license_key = ? ORDER BY created_at DESC LIMIT 1
        ''', (license_key,))
        return cursor.fetchone()
    
    def create_user(self, telegram_id, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)
        ''', (telegram_id, username))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_user(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        return cursor.fetchone()
    
    def has_user_used_refund(self, telegram_id):
        """Проверить, использовал ли пользователь возврат"""
        if telegram_id in ADMIN_IDS:
            return False

        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT has_used_refund FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        result = cursor.fetchone()
        return result and result[0] == 1 if result else False
    
    def mark_refund_used(self, telegram_id):
        """Отметить, что пользователь использовал возврат"""
        if telegram_id in ADMIN_IDS:
            return True

        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET has_used_refund = 1 WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reset_refund_status(self, telegram_id):
        """Сбросить статус возврата (для администратора)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET has_used_refund = 0 WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_bot_settings(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT bot_token, api_id, api_hash FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        return cursor.fetchone()
    
    def update_bot_token(self, telegram_id, bot_token):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET bot_token = ? WHERE telegram_id = ?
        ''', (bot_token, telegram_id))
        self.conn.commit()
    
    def update_api_id(self, telegram_id, api_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET api_id = ? WHERE telegram_id = ?
        ''', (api_id, telegram_id))
        self.conn.commit()
    
    def update_api_hash(self, telegram_id, api_hash):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET api_hash = ? WHERE telegram_id = ?
        ''', (api_hash, telegram_id))
        self.conn.commit()
    
    def update_session_string(self, telegram_id, session_string):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET session_string = ? WHERE telegram_id = ?
        ''', (session_string, telegram_id))
        self.conn.commit()
    
    def get_session_string(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT session_string FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_active_license(self, telegram_id):
        """Получить активную лицензию пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.*, lk.expires_at
            FROM users u
            LEFT JOIN license_keys lk ON u.license_key = lk.key
            WHERE u.telegram_id = ? AND lk.is_active = 1 AND lk.expires_at > datetime('now')
        ''', (telegram_id,))
        return cursor.fetchone()
    
    def update_user_subscription(self, telegram_id, plan, license_key, end_date):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET
                subscription_plan = ?,
                license_key = ?,
                subscription_end_date = ?
            WHERE telegram_id = ?
        ''', (plan, license_key, end_date, telegram_id))
        self.conn.commit()
    
    def create_license_key(self, user_id, plan, duration_days):
        key = self.generate_license_key()
        expires_at = datetime.now() + timedelta(days=duration_days)

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO license_keys (key, user_id, plan, expires_at) VALUES (?, ?, ?, ?)
        ''', (key, user_id, plan, expires_at.isoformat()))
        self.conn.commit()

        self.create_reminders(user_id, key, expires_at)

        return key
    
    def generate_license_key(self):
        return f"SB-{uuid.uuid4().hex[:16].upper()}"
    
    def validate_license_key(self, key):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT lk.*, u.telegram_id FROM license_keys lk
            JOIN users u ON lk.user_id = u.user_id
            WHERE lk.key = ? AND lk.is_active = 1 AND lk.expires_at > datetime('now')
        ''', (key,))
        return cursor.fetchone()
    
    def deactivate_license(self, license_key):
        """Деактивировать лицензию"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE license_keys SET is_active = 0 WHERE key = ?
        ''', (license_key,))
        cursor.execute('''
            DELETE FROM reminders WHERE license_key = ?
        ''', (license_key,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def create_refund_request(self, user_id, license_key, stars_amount):
        """Создать запрос на возврат"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO refund_requests (user_id, license_key, stars_amount)
            VALUES (?, ?, ?)
        ''', (user_id, license_key, stars_amount))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_refund_request(self, user_id, license_key):
        """Получить запрос на возврат"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM refund_requests
            WHERE user_id = ? AND license_key = ? AND status = 'pending'
        ''', (user_id, license_key))
        return cursor.fetchone()
    
    def update_refund_status(self, request_id, status):
        """Обновить статус возврата"""
        processed_at = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE refund_requests
            SET status = ?, processed_at = ?
            WHERE request_id = ?
        ''', (status, processed_at, request_id))
        self.conn.commit()

    def create_reminders(self, user_id, license_key, expires_at):
        """Создать напоминания о продлении подписки"""
        three_days_before = expires_at - timedelta(days=3)
        one_hour_before = expires_at - timedelta(hours=1)

        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM reminders WHERE license_key = ?
        ''', (license_key,))

        cursor.execute('''
            INSERT INTO reminders (user_id, license_key, reminder_type, scheduled_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, license_key, '3_days', three_days_before.isoformat()))

        cursor.execute('''
            INSERT INTO reminders (user_id, license_key, reminder_type, scheduled_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, license_key, '1_hour', one_hour_before.isoformat()))
        self.conn.commit()

    def get_due_reminders(self):
        """Получить напоминания, которые нужно отправить"""
        now = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT r.*, u.telegram_id, u.username, lk.expires_at, u.subscription_plan
            FROM reminders r
            JOIN users u ON r.user_id = u.user_id
            JOIN license_keys lk ON r.license_key = lk.key
            WHERE r.sent = 0 AND r.scheduled_time <= ? AND lk.is_active = 1
        ''', (now,))

        reminders = cursor.fetchall()
        return reminders
    
    def mark_reminder_sent(self, reminder_id):
        sent_at = datetime.now().isoformat()

        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE reminders SET sent = 1, sent_at = ? WHERE reminder_id = ?
        ''', (sent_at, reminder_id))
        self.conn.commit()
    
    def save_queued_subscription(self, user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO queued_subscriptions (user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_queued_subscription(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM queued_subscriptions WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (telegram_id,))
        return cursor.fetchone()
    
    def delete_queued_subscription(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM queued_subscriptions WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_expired_subscriptions_with_queue(self):
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.user_id, u.telegram_id, u.license_key, qs.*
            FROM users u
            JOIN queued_subscriptions qs ON u.telegram_id = qs.telegram_id
            WHERE u.subscription_end_date < ? AND u.license_key IS NOT NULL
        ''', (now,))
        return cursor.fetchall()

    def get_all_users(self) -> list:
        """Все пользователи, отсортированные по дате создания"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        return cursor.fetchall()

    def get_users_page(self, offset: int, limit: int = 10) -> tuple:
        """Пагинированный список. Возвращает (rows, total_count)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        return rows, total

    def search_users(self, query: str) -> list:
        """Поиск по telegram_id или username (LIKE)"""
        cursor = self.conn.cursor()
        if query.isdigit():
            cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (int(query),))
        else:
            cursor.execute('SELECT * FROM users WHERE username LIKE ?', (f'%{query}%',))
        return cursor.fetchall()

    def get_payment_by_charge_id(self, charge_id: str):
        """Найти платёж по telegram_payment_charge_id"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.*, u.telegram_id, u.username
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.telegram_payment_charge_id = ?
        ''', (charge_id,))
        return cursor.fetchone()

    def get_user_payments(self, telegram_id: int) -> list:
        """Все платежи пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM payments
            WHERE user_id = (SELECT user_id FROM users WHERE telegram_id = ?)
            ORDER BY created_at DESC
        ''', (telegram_id,))
        return cursor.fetchall()

    def clear_user_subscription(self, telegram_id: int):
        """Очистить подписку (subscription_plan, license_key, subscription_end_date → NULL)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET
                subscription_plan = NULL,
                license_key = NULL,
                subscription_end_date = NULL
            WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()

    def update_deployment_status(self, telegram_id: int, status: str | None):
        """Обновить статус деплоя: NULL, pending_setup, running, stopped, awaiting_admin"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET deployment_status = ? WHERE telegram_id = ?', (status, telegram_id))
        self.conn.commit()

    def update_container_id(self, telegram_id: int, container_id: str | None):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET container_id = ? WHERE telegram_id = ?', (container_id, telegram_id))
        self.conn.commit()

    def get_deployment_info(self, telegram_id: int):
        """Получить (deployment_status, container_id, vps_ip)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT deployment_status, container_id, vps_ip FROM users WHERE telegram_id = ?', (telegram_id,))
        return cursor.fetchone()

    def get_hosting_users(self) -> list:
        """Все пользователи с планом HOSTING и deployment_status='running'"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users
            WHERE deployment_status = 'running'
              AND subscription_plan IN ('pro', 'pro-year')
        ''')
        return cursor.fetchall()

    def get_awaiting_admin_users(self) -> list:
        """Пользователи HOSTING-PRO, ожидающие деплоя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users
            WHERE deployment_status = 'awaiting_admin'
              AND subscription_plan IN ('premium', 'premium-year')
        ''')
        return cursor.fetchall()

    def get_user_plan_name(self, telegram_id: int) -> str | None:
        """Получить имя тарифа пользователя (SELF-HOST / HOSTING / HOSTING-PRO)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT subscription_plan FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        plan = SUBSCRIPTION_PLANS.get(row[0])
        return plan["name"] if plan else None

db = Database()
user_invoice_data = {}
user_menu_message: dict[int, int] = {}  # telegram_id -> message_id
user_notification_message: dict[int, int] = {}  # telegram_id -> message_id
# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def build_main_menu_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    active_license = db.get_active_license(telegram_id)
    plan_name = db.get_user_plan_name(telegram_id)
    keyboard = []
    if active_license:
        keyboard.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")])
    else:
        keyboard.append([InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")])
    keyboard.append([InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")])
    if active_license:
        if plan_name == "SELF-HOST":
            keyboard.append([InlineKeyboardButton(text="📖 Документация", url="https://seventyzero.github.io/tgbotnft-docs/")])
        elif plan_name in ("HOSTING", "HOSTING-PRO"):
            keyboard.append([InlineKeyboardButton(text="⚙️ Управление ботом", callback_data="bot_settings")])
        else:
            keyboard.append([InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="bot_settings")])
        keyboard.append([InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")])
    keyboard.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def delete_tracked_messages(telegram_id: int) -> None:
    for store in (user_notification_message, user_menu_message):
        msg_id = store.pop(telegram_id, None)
        if msg_id is not None:
            try:
                await bot.delete_message(chat_id=telegram_id, message_id=msg_id)
            except Exception:
                pass


async def send_menu(telegram_id: int) -> None:
    reply_markup = build_main_menu_keyboard(telegram_id)
    msg = await bot.send_message(
        chat_id=telegram_id,
        text="👋 Добро пожаловать в Service Bot!\n\nВыберите действие ниже:",
        reply_markup=reply_markup,
    )
    user_menu_message[telegram_id] = msg.message_id


async def notify_user(telegram_id: int, text: str) -> None:
    await delete_tracked_messages(telegram_id)
    notif = await bot.send_message(chat_id=telegram_id, text=text, parse_mode=ParseMode.HTML)
    user_notification_message[telegram_id] = notif.message_id
    await send_menu(telegram_id)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.create_user(message.from_user.id, message.from_user.username)
    await delete_tracked_messages(message.from_user.id)
    reply_markup = build_main_menu_keyboard(message.from_user.id)
    msg = await message.answer(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Этот бот поможет вам настроить вашего собственного Telegram бота "
        "с функциями покупки подарков за звезды.\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup
    )
    user_menu_message[message.from_user.id] = msg.message_id

@dp.callback_query(F.data == "select_plan")
async def select_plan(callback: CallbackQuery):
    # Проверяем, есть ли активная подписка
    active_license = db.get_active_license(callback.from_user.id)
    
    if active_license:
        plan = SUBSCRIPTION_PLANS.get(active_license[4])  # subscription_plan
        end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
        
        keyboard = [
            [InlineKeyboardButton(text="🔄 Продолжить покупку новой подписки", callback_data="confirm_new_purchase")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            f"⚠️ <b>У вас уже есть активная подписка!</b>\n\n"
            f"Текущий тариф: <b>{plan['name'] if plan else 'Неизвестно'}</b>\n"
            f"Действует до: <b>{end_date.strftime('%d.%m.%Y') if end_date else 'Неизвестно'}</b>\n\n"
            f"При покупке новой подписки:\n"
            f"• Старая подписка будет отменена\n"
            f"• Вам будет предложен возврат звезд за оставшиеся дни\n"
            f"• Будет активирована новая подписка\n\n"
            f"Хотите продолжить?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
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

@dp.callback_query(F.data == "confirm_new_purchase")
async def confirm_new_purchase(callback: CallbackQuery):
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

@dp.callback_query(F.data == "yearly_plans")
async def show_yearly_plans(callback: CallbackQuery):
    keyboard = []
    yearly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if k.endswith('-year')}
    
    for plan_id, plan_info in yearly_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{plan_info['name']} - {plan_info['stars']} ⭐/год {plan_info['equal']}",
                callback_data=f"buy_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="select_plan")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "📆 <b>Годовые подписки</b>\n\n"
        "💰 Экономия 2 месяца бесплатно!\n"
        "Выберите подходящий тариф:",
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
    
    # Проверяем, есть ли активная подписка
    active_license = db.get_active_license(callback.from_user.id)
    if active_license:
        # Создаем запрос на возврат для старой подписки
        old_plan = SUBSCRIPTION_PLANS.get(active_license[4])
        if old_plan:
            # Рассчитываем остаток звезд пропорционально оставшимся дням
            end_date = datetime.fromisoformat(active_license[5])
            days_left = (end_date - datetime.now()).days
            total_days = old_plan["duration_days"]
            
            if days_left > 0:
                total_days = old_plan["duration_days"]
                
                cost_per_day = old_plan["stars"] / total_days
                refund_amount = cost_per_day * days_left
                refund_amount = max(1, int(refund_amount + 0.5))  # Округление вверх
                refund_amount = min(refund_amount, old_plan["stars"])
                logger.info(f"Расчет возврата: {old_plan['stars']}⭐, дней осталось: {days_left}, возврат: {refund_amount}⭐")
                
                db.create_refund_request(callback.from_user.id, active_license[3], refund_amount)
                db.deactivate_license(active_license[3])
    
    # Генерируем уникальный payload
    invoice_payload = f"plan_{plan_id}_{uuid.uuid4().hex[:8]}"
    
    # Цена в звездах
    price_in_cents = plan["stars"]
    
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text=f"Купить подписку за {plan['stars']}⭐",
                    pay=True
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Сохраняем ID сообщения с инвойсом
        invoice_message = await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Подписка {plan['name']}",
            description=f"Доступ к Service Bot на {plan['duration_days']} дней",
            payload=invoice_payload,
            provider_token="",  # Пустая строка для Telegram Stars
            currency="XTR",  # Код валюты Telegram Stars
            prices=[LabeledPrice(label=f"Подписка {plan['name']}", amount=price_in_cents)],
            max_tip_amount=0,
            suggested_tip_amounts=[],
            reply_markup=reply_markup
        )

        # Сохраняем ID обоих сообщений
        global user_invoice_data
        user_invoice_data[callback.from_user.id] = {
            "invoice_id": invoice_message.message_id,
            "cancel_message_id": callback.message.message_id  # ID сообщения с кнопкой отмены
        }

        declinekeyboard = [
            [InlineKeyboardButton(text="❌ Отмена покупки", callback_data="cancel_invoice")]
        ]
        reply_markup_decline = InlineKeyboardMarkup(inline_keyboard=declinekeyboard)
        
        # Отправляем сообщение с кнопкой отмены (но не редактируем старое, а создаем новое)
        cancel_message = await callback.message.edit_text(
            f"✅ Инвойс для тарифа <b>{plan['name']}</b> отправлен!\n\n"
            f"Проверьте чат с ботом, вам должно прийти платежное окно.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup_decline
        )
        
        # Обновляем ID сообщения с кнопкой отмены (теперь это новое сообщение)
        if callback.from_user.id in user_invoice_data:
            user_invoice_data[callback.from_user.id]["cancel_message_id"] = cancel_message.message_id
        
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при создании платежа\n\n"
            f"<b>Причина:</b> {str(e)[:200]}\n\n"
            f"Проверьте настройки бота в @BotFather (Bot Settings → Telegram Stars)",
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(F.data == "cancel_invoice")
async def cancel_invoice(callback: CallbackQuery):
    """Удалить инвойс и вернуться к выбору тарифа"""
    user_id = callback.from_user.id
    
    try:
        global user_invoice_data
        
        # Пытаемся удалить оба сообщения, если они есть
        if user_id in user_invoice_data:
            invoice_data = user_invoice_data[user_id]
            
            # Удаляем инвойс
            try:
                await bot.delete_message(
                    chat_id=user_id,
                    message_id=invoice_data["invoice_id"]
                )
                logger.info(f"Инвойс удален для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить инвойс: {e}")
                # Инвойс мог быть уже удален или оплачен
            
            # Удаляем сообщение с кнопкой отмены
            try:
                await bot.delete_message(
                    chat_id=user_id,
                    message_id=invoice_data["cancel_message_id"]
                )
                logger.info(f"Сообщение с кнопкой отмены удалено для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение с кнопкой отмены: {e}")
            
            # Убираем из словаря
            user_invoice_data.pop(user_id, None)
        
        # После удаления сообщений нужно отправить новое, а не редактировать старое
        # Проверяем, есть ли активная подписка
        active_license = db.get_active_license(callback.from_user.id)
        
        if active_license:
            plan = SUBSCRIPTION_PLANS.get(active_license[4])  # subscription_plan
            end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
            
            keyboard = [
                [InlineKeyboardButton(text="🔄 Продолжить покупку новой подписки", callback_data="confirm_new_purchase")],
                [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            await bot.send_message(
                chat_id=user_id,
                text=f"⚠️ <b>У вас уже есть активная подписка!</b>\n\n"
                     f"Текущий тариф: <b>{plan['name'] if plan else 'Неизвестно'}</b>\n"
                     f"Действует до: <b>{end_date.strftime('%d.%m.%Y') if end_date else 'Неизвестно'}</b>\n\n"
                     f"При покупке новой подписки:\n"
                     f"• Старая подписка будет отменена\n"
                     f"• Вам будет предложен возврат звезд за оставшиеся дни\n"
                     f"• Будет активирована новая подписка\n\n"
                     f"Хотите продолжить?",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return
        
        keyboard = [
            [InlineKeyboardButton(text="📅 Месячные подписки", callback_data="monthly_plans")],
            [InlineKeyboardButton(text="📅 Годовые подписки", callback_data="yearly_plans")],
            [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await bot.send_message(
            chat_id=user_id,
            text="📦 Выберите тип подписки:\n\n"
                 "💰 <b>Годовые подписки</b> - экономия 2 месяца бесплатно!\n"
                 "📅 <b>Месячные подписки</b> - гибкий платежный план\n\n"
                 "Выберите тип подписки:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене инвойса: {e}")
        # Пытаемся хотя бы отправить сообщение об ошибке
        try:
            await bot.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при отмене покупки. Попробуйте снова через /start"
            )
        except:
            pass

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    try:
        payload = query.invoice_payload
        if not payload:
            await bot.answer_pre_checkout_query(query.id, ok=False, error_message="Некорректные данные платежа")
            return
        parts = payload.split("_")
        payload_type = parts[0] if len(parts) > 0 else None
        plan_id = parts[1] if len(parts) > 1 else None
        if payload_type not in ("plan", "renew") or not plan_id or plan_id not in SUBSCRIPTION_PLANS:
            await bot.answer_pre_checkout_query(query.id, ok=False, error_message="Неверный тарифный план")
            return
        plan = SUBSCRIPTION_PLANS[plan_id]
        if query.total_amount != plan["price"]:
            await bot.answer_pre_checkout_query(query.id, ok=False, error_message="Несоответствие суммы платежа")
            return
        await bot.answer_pre_checkout_query(query.id, ok=True)
    except Exception as e:
        logger.error(f"Ошибка pre_checkout: {e}")
        await bot.answer_pre_checkout_query(query.id, ok=False, error_message="Внутренняя ошибка")

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payment = message.successful_payment
    
    payload_parts = payment.invoice_payload.split("_")
    payload_type = payload_parts[0] if len(payload_parts) > 0 else None
    plan_id = payload_parts[1] if len(payload_parts) > 1 else None
    
    if not plan_id or plan_id not in SUBSCRIPTION_PLANS:
        await message.answer("❌ Ошибка обработки платежа: неверный план")
        return
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    global user_invoice_data
    if user_id in user_invoice_data:
        invoice_data = user_invoice_data[user_id]
        try:
            await bot.delete_message(chat_id=user_id, message_id=invoice_data["invoice_id"])
        except Exception as e:
            logger.error(f"Не удалось удалить инвойс после оплаты: {e}")
        try:
            await bot.delete_message(chat_id=user_id, message_id=invoice_data["cancel_message_id"])
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с кнопкой отмены после оплаты: {e}")
        user_invoice_data.pop(user_id, None)
    
    if payload_type == "renew":
        db.save_queued_subscription(
            user_id=user[0],
            telegram_id=user_id,
            plan=plan_id,
            stars_amount=plan["stars"],
            telegram_payment_charge_id=payment.telegram_payment_charge_id
        )
        
        active_license = db.get_active_license(user_id)
        end_date = datetime.fromisoformat(active_license[5]) if active_license and active_license[5] else None
        
        keyboard = [
            [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await message.answer(
            f"✅ <b>Продление успешно оплачено!</b>\n\n"
            f"📋 <b>Подписка добавлена в очередь:</b>\n"
            f"• Тариф: {plan['name']}\n"
            f"• Срок: {plan['duration_days']} дней\n"
            f"• Стоимость: {plan['stars']} ⭐\n\n"
            f"Подписка автоматически активируется после окончания текущей "
            f"({end_date.strftime('%d.%m.%Y') if end_date else 'неизвестно'}).",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
    license_key = db.create_license_key(user[0], plan_id, plan["duration_days"])
    end_date = (datetime.now() + timedelta(days=plan["duration_days"])).isoformat()

    db.update_user_subscription(user_id, plan_id, license_key, end_date)

    refund_request = db.get_refund_request(user_id, user[3] if user[3] else "")
    if refund_request:
        refund_text = f"\n💰 <b>Возврат:</b> Запрошен возврат {refund_request[3]} ⭐ за предыдущую подписку."
        db.update_refund_status(refund_request[0], "approved")
    else:
        refund_text = ""

    db.save_payment(
        user_id=user[0],
        license_key=license_key,
        stars_amount=plan["stars"],
        telegram_payment_charge_id=payment.telegram_payment_charge_id
    )

    # Разветвление по тарифу
    plan_name = plan["name"]  # SELF-HOST / HOSTING / HOSTING-PRO

    if plan_name == "SELF-HOST":
        keyboard = [
            [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="📖 Документация", url="https://seventyzero.github.io/tgbotnft-docs/")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"✅ <b>Оплата успешно завершена!</b>\n\n"
            f"📋 <b>Детали подписки:</b>\n"
            f"• Тариф: {plan_name}\n"
            f"• Срок: {plan['duration_days']} дней\n"
            f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n"
            f"{refund_text}\n\n"
            f"Ваш лицензионный ключ сгенерирован!\n"
            f"Используйте документацию для настройки бота на своём сервере.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

    elif plan_name == "HOSTING":
        db.update_deployment_status(user_id, "pending_setup")
        keyboard = [
            [InlineKeyboardButton(text="⚙️ Настроить бота", callback_data="bot_settings")],
            [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"✅ <b>Оплата принята!</b>\n\n"
            f"📋 <b>Детали подписки:</b>\n"
            f"• Тариф: {plan_name}\n"
            f"• Срок: {plan['duration_days']} дней\n"
            f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n"
            f"{refund_text}\n\n"
            f"Настройте бота для запуска на нашем сервере.\n"
            f"После настройки Bot Token и авторизации бот будет запущен автоматически.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

    elif plan_name == "HOSTING-PRO":
        db.update_deployment_status(user_id, "pending_setup")
        keyboard = [
            [InlineKeyboardButton(text="⚙️ Настроить бота", callback_data="bot_settings")],
            [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"✅ <b>Оплата принята!</b>\n\n"
            f"📋 <b>Детали подписки:</b>\n"
            f"• Тариф: {plan_name}\n"
            f"• Срок: {plan['duration_days']} дней\n"
            f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n"
            f"{refund_text}\n\n"
            f"Настройте бота, после чего мы развернём его на отдельном VPS.\n"
            f"После настройки Bot Token и авторизации администратор получит уведомление.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        # Уведомить админов о новом HOSTING-PRO пользователе
        uname = f"@{message.from_user.username}" if message.from_user.username else f"ID:{user_id}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🆕 <b>Новый HOSTING-PRO пользователь!</b>\n\n"
                    f"👤 {uname} (ID: <code>{user_id}</code>)\n"
                    f"📦 Тариф: {plan_name}\n"
                    f"📅 До: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
                    f"Пользователь настраивает бота. После авторизации потребуется ручной деплой на VPS.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id} о HOSTING-PRO: {e}")

    else:
        # Fallback для неизвестных тарифов — стандартное поведение
        keyboard = [
            [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"✅ <b>Оплата успешно завершена!</b>\n\n"
            f"📋 <b>Детали подписки:</b>\n"
            f"• Тариф: {plan_name}\n"
            f"• Срок: {plan['duration_days']} дней\n"
            f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n"
            f"{refund_text}\n\n"
            f"Ваш лицензионный ключ сгенерирован!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(F.data == "cancel_subscription")
async def cancel_subscription(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    active_license = db.get_active_license(callback.from_user.id)
    queued = db.get_queued_subscription(callback.from_user.id)
    
    if not active_license and not queued:
        await callback.answer("❌ У вас нет подписок для отмены", show_alert=True)
        return
    
    if active_license and queued:
        active_plan = SUBSCRIPTION_PLANS.get(active_license[4], {})
        queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
        
        keyboard = [
            [InlineKeyboardButton(text=f"🔴 Текущая: {active_plan.get('name', '?')}", callback_data="cancel_current")],
            [InlineKeyboardButton(text=f"🟡 В очереди: {queued_plan.get('name', '?')}", callback_data="cancel_queued")],
            [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            f"⚠️ <b>Какую подписку отменить?</b>\n\n"
            f"📋 <b>Текущая подписка:</b>\n"
            f"• Тариф: {active_plan.get('name', 'Неизвестно')}\n"
            f"• Стоимость: {active_plan.get('stars', 0)} ⭐\n"
            f"• Действует до: {end_date.strftime('%d.%m.%Y') if end_date else 'Неизвестно'}\n\n"
            f"📋 <b>Подписка в очереди:</b>\n"
            f"• Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
            f"• Стоимость: {queued[4]} ⭐\n\n"
            f"Выберите какую подписку отменить:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
    if queued and not active_license:
        queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        if callback.from_user.id in ADMIN_IDS:
            cancel_note = "При отмене будет выполнен возврат средств."
        else:
            cancel_note = "Подписка будет отменена без возврата.\nДля возврата — свяжитесь с администратором."
        keyboard = [
            [InlineKeyboardButton(text="✅ Да, отменить", callback_data="cancel_queued")],
        ]
        if callback.from_user.id not in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton(text="📩 Связаться с админом (возврат)", callback_data="contact_admin_refund")])
        keyboard.append([InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            f"⚠️ <b>Отмена подписки в очереди</b>\n\n"
            f"📋 <b>Подписка в очереди:</b>\n"
            f"• Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
            f"• Стоимость: {queued[4]} ⭐\n\n"
            f"{cancel_note}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
    plan = SUBSCRIPTION_PLANS.get(user[4])
    end_date = datetime.fromisoformat(user[5]) if user[5] else None
    
    if not end_date or end_date <= datetime.now():
        await callback.answer("❌ Ваша подписка уже истекла", show_alert=True)
        return
    
    days_left = (end_date - datetime.now()).days
    if days_left <= 0:
        await callback.answer("❌ Подписка уже истекла", show_alert=True)
        return
    
    if callback.from_user.id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton(text="✅ Да, отменить подписку", callback_data="cancel_current")],
            [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        text = f"⚠️ <b>Отмена подписки (АДМИН)</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: <b>♾️ БЕЗГРАНИЧНО (режим админа)</b>\n\n"
        text += f"Вы хотите отменить подписку?"
    else:
        keyboard = [
            [InlineKeyboardButton(text="✅ Да, отменить подписку", callback_data="cancel_current")],
            [InlineKeyboardButton(text="📩 Связаться с админом (возврат)", callback_data="contact_admin_refund")],
            [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        text = f"⚠️ <b>Отмена подписки</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n\n"
        text += f"⚠️ При отмене подписка будет деактивирована <b>без возврата</b>.\n"
        text += f"Для возврата средств — свяжитесь с администратором.\n\n"
        text += f"Вы хотите отменить подписку?"

    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "cancel_current")
async def cancel_current_subscription(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user or not user[3]:
        await callback.answer("❌ Ошибка: лицензия не найдена", show_alert=True)
        return
    
    license_key = user[3]
    plan = SUBSCRIPTION_PLANS.get(user[4])
    if not plan:
        await callback.answer("❌ Ошибка: план не найден", show_alert=True)
        return
    
    payment_info = db.get_payment_by_license(license_key)

    db.deactivate_license(license_key)
    db.clear_user_subscription(callback.from_user.id)

    # Остановка контейнера/уведомление при отмене подписки
    plan_name = plan["name"]
    deployment_info = db.get_deployment_info(callback.from_user.id)
    dep_status = deployment_info[0] if deployment_info else None
    if plan_name == "HOSTING" and dep_status in ("running", "pending_setup"):
        import docker_manager
        await docker_manager.remove_container(callback.from_user.id)
        db.update_deployment_status(callback.from_user.id, "stopped")
        db.update_container_id(callback.from_user.id, None)
    elif plan_name == "HOSTING-PRO" and dep_status in ("running", "awaiting_admin", "pending_setup"):
        db.update_deployment_status(callback.from_user.id, "stopped")
        uname = f"@{callback.from_user.username}" if callback.from_user.username else f"ID:{callback.from_user.id}"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ <b>HOSTING-PRO: подписка отменена</b>\n\n"
                    f"👤 {uname} (ID: <code>{callback.from_user.id}</code>)\n"
                    f"Необходимо удалить VPS / остановить сервис.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    end_date = datetime.fromisoformat(user[5]) if user[5] else datetime.now()
    days_left = max(0, (end_date - datetime.now()).days)

    refund_info = ""

    if callback.from_user.id in ADMIN_IDS and payment_info:
        try:
            await callback.message.edit_text("🔄 Выполняется возврат средств...", parse_mode=ParseMode.HTML)

            refund_success = await refund_star_payment(
                telegram_id=callback.from_user.id,
                payment_id=payment_info[4],
                stars_amount=plan["stars"]
            )

            if refund_success:
                refund_info = f"\n💰 <b>Возврат выполнен!</b> {plan['stars']} ⭐ возвращено.\n"
            else:
                refund_info = f"\n⚠️ <b>Автоматический возврат не удался.</b>\nСвяжитесь с @Dimopster.\n"
        except Exception as e:
            logger.error(f"Ошибка при возврате: {e}")
            refund_info = f"\n⚠️ <b>Ошибка возврата.</b> Свяжитесь с @Dimopster.\n"
    
    queued = db.get_queued_subscription(callback.from_user.id)
    queue_activated_info = ""
    
    if queued:
        queued_plan_id = queued[3]
        queued_plan = SUBSCRIPTION_PLANS.get(queued_plan_id)
        queued_payment_id = queued[5]
        queued_stars = queued[4]
        
        if queued_plan:
            new_license_key = db.create_license_key(user[0], queued_plan_id, queued_plan["duration_days"])
            new_end_date = (datetime.now() + timedelta(days=queued_plan["duration_days"])).isoformat()
            
            db.update_user_subscription(callback.from_user.id, queued_plan_id, new_license_key, new_end_date)
            
            db.save_payment(
                user_id=user[0],
                license_key=new_license_key,
                stars_amount=queued_stars,
                telegram_payment_charge_id=queued_payment_id
            )
            
            db.delete_queued_subscription(callback.from_user.id)
            
            queue_activated_info = (
                f"\n🎉 <b>Подписка из очереди активирована!</b>\n"
                f"• Тариф: {queued_plan['name']}\n"
                f"• Действует до: {datetime.fromisoformat(new_end_date).strftime('%d.%m.%Y')}\n"
            )
    
    if queue_activated_info:
        keyboard = [
            [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📦 Купить новую подписку", callback_data="select_plan")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
        ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"✅ <b>Подписка отменена!</b>\n\n"
        f"Тариф: {plan['name']}\n"
        f"Дата отмены: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"{refund_info}"
        f"{queue_activated_info}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "cancel_queued")
async def cancel_queued_subscription(callback: CallbackQuery):
    queued = db.get_queued_subscription(callback.from_user.id)
    if not queued:
        await callback.answer("❌ Нет подписки в очереди", show_alert=True)
        return
    
    queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
    payment_id = queued[5]
    stars_amount = queued[4]

    db.delete_queued_subscription(callback.from_user.id)

    refund_info = ""

    if callback.from_user.id in ADMIN_IDS and payment_id:
        try:
            await callback.message.edit_text("🔄 Выполняется возврат средств...", parse_mode=ParseMode.HTML)

            refund_success = await refund_star_payment(
                telegram_id=callback.from_user.id,
                payment_id=payment_id,
                stars_amount=stars_amount
            )

            if refund_success:
                refund_info = f"\n💰 <b>Возврат выполнен!</b> {stars_amount} ⭐ возвращено.\n"
            else:
                refund_info = f"\n⚠️ <b>Автоматический возврат не удался.</b>\nСвяжитесь с @Dimopster.\nID платежа: <code>{payment_id}</code>\n"
        except Exception as e:
            logger.error(f"Ошибка при возврате очереди: {e}")
            refund_info = f"\n⚠️ <b>Ошибка возврата.</b> Свяжитесь с @Dimopster.\n"
    
    keyboard = [
        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"✅ <b>Подписка из очереди отменена!</b>\n\n"
        f"Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
        f"Стоимость: {stars_amount} ⭐\n"
        f"{refund_info}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def refund_star_payment(telegram_id: int, payment_id: str, stars_amount: int = None) -> bool:
    """
    Выполнить возврат звезд через Telegram Bot API
    Требует наличия прав у бота на возврат платежей
    """
    try:
        # URL для вызова метода refundStarPayment
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/refundStarPayment"
        
        # Параметры запроса
        payload = {
            "user_id": telegram_id,
            "telegram_payment_charge_id": payment_id
        }
        
        # Если указана сумма возврата (опционально)
        if stars_amount:
            payload["amount"] = stars_amount
        
        # Отправляем запрос к Telegram Bot API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                
                if result.get("ok"):
                    logger.info(f"Успешный возврат: пользователь {telegram_id}, платеж {payment_id}")
                    return True
                else:
                    logger.error(f"Ошибка возврата: {result.get('description')}")
                    return False
                    
    except Exception as e:
        logger.error(f"Ошибка при выполнении возврата: {e}")
        return False

@dp.callback_query(F.data == "renew_subscription")
async def renew_subscription(callback: CallbackQuery):
    active_license = db.get_active_license(callback.from_user.id)
    
    if not active_license:
        await select_plan(callback)
        return
    
    queued = db.get_queued_subscription(callback.from_user.id)
    if queued:
        queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        keyboard = [
            [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            f"⚠️ <b>У вас уже есть подписка в очереди!</b>\n\n"
            f"📋 <b>Подписка в очереди:</b>\n"
            f"• Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
            f"• Стоимость: {queued[4]} ⭐\n\n"
            f"Эта подписка автоматически активируется после окончания текущей.\n\n"
            f"Если хотите изменить тариф — сначала отмените подписку в очереди.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
    plan = SUBSCRIPTION_PLANS.get(active_license[4])
    end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
    
    keyboard = [
        [InlineKeyboardButton(text="📅 Месячные подписки", callback_data="renew_monthly_plans")],
        [InlineKeyboardButton(text="📅 Годовые подписки", callback_data="renew_yearly_plans")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"🔄 <b>Продление подписки</b>\n\n"
        f"📋 <b>Текущая подписка:</b>\n"
        f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
        f"• Действует до: {end_date.strftime('%d.%m.%Y') if end_date else 'Неизвестно'}\n\n"
        f"Выберите тариф для продления.\n"
        f"Новая подписка будет добавлена в очередь и автоматически активируется после окончания текущей.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "renew_monthly_plans")
async def show_renew_monthly_plans(callback: CallbackQuery):
    keyboard = []
    monthly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if not k.endswith('-year')}
    
    for plan_id, plan_info in monthly_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{plan_info['name']} - {plan_info['stars']} ⭐/мес {plan_info['equal']}",
                callback_data=f"renew_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="renew_subscription")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "📅 <b>Месячные подписки для продления</b>\n\nВыберите тариф:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "renew_yearly_plans")
async def show_renew_yearly_plans(callback: CallbackQuery):
    keyboard = []
    yearly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if k.endswith('-year')}
    
    for plan_id, plan_info in yearly_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{plan_info['name']} - {plan_info['stars']} ⭐/год {plan_info['equal']}",
                callback_data=f"renew_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="renew_subscription")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "📆 <b>Годовые подписки для продления</b>\n\n"
        "💰 Экономия 2 месяца бесплатно!\n"
        "Выберите тариф:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("renew_plan_"))
async def renew_plan(callback: CallbackQuery):
    plan_id = callback.data.replace("renew_plan_", "")
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    
    if not plan:
        await callback.answer("❌ Неверный тарифный план", show_alert=True)
        return
    
    active_license = db.get_active_license(callback.from_user.id)
    if not active_license:
        await callback.answer("❌ У вас нет активной подписки", show_alert=True)
        return
    
    queued = db.get_queued_subscription(callback.from_user.id)
    if queued:
        await callback.answer("❌ У вас уже есть подписка в очереди", show_alert=True)
        return
    
    invoice_payload = f"renew_{plan_id}_{uuid.uuid4().hex[:8]}"
    
    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    text=f"Оплатить продление {plan['stars']}⭐",
                    pay=True
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        invoice_message = await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Продление: {plan['name']}",
            description=f"Продление подписки на {plan['duration_days']} дней (в очередь)",
            payload=invoice_payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"Продление {plan['name']}", amount=plan["stars"])],
            max_tip_amount=0,
            suggested_tip_amounts=[],
            reply_markup=reply_markup
        )
        
        global user_invoice_data
        user_invoice_data[callback.from_user.id] = {
            "invoice_id": invoice_message.message_id,
            "cancel_message_id": callback.message.message_id
        }
        
        declinekeyboard = [
            [InlineKeyboardButton(text="❌ Отмена покупки", callback_data="cancel_invoice")]
        ]
        reply_markup_decline = InlineKeyboardMarkup(inline_keyboard=declinekeyboard)
        
        cancel_message = await callback.message.edit_text(
            f"✅ Инвойс для продления тарифа <b>{plan['name']}</b> отправлен!\n\n"
            f"После оплаты подписка будет добавлена в очередь.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup_decline
        )
        
        if callback.from_user.id in user_invoice_data:
            user_invoice_data[callback.from_user.id]["cancel_message_id"] = cancel_message.message_id
        
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса для продления: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка при создании платежа\n\n"
            f"<b>Причина:</b> {str(e)[:200]}",
            parse_mode=ParseMode.HTML
        )

async def send_reminder_notifications():
    """Функция для отправки напоминаний о продлении подписки"""
    while True:
        try:
            # Получаем напоминания, которые нужно отправить
            reminders = db.get_due_reminders()
            
            for reminder in reminders:
                reminder_id = reminder[0]
                user_id = reminder[1]
                license_key = reminder[2]
                reminder_type = reminder[3]
                telegram_id = reminder[8]
                username = reminder[9]
                expires_at = datetime.fromisoformat(reminder[10])
                plan_id = reminder[11]
                
                # Проверяем, есть ли у пользователя подписка в очереди
                # Если да — не отправляем напоминание (пользователь уже продлил)
                queued = db.get_queued_subscription(telegram_id)
                if queued:
                    db.mark_reminder_sent(reminder_id)
                    logger.info(f"Пропущено напоминание для {telegram_id} ({username}) — есть подписка в очереди")
                    continue
                
                plan = SUBSCRIPTION_PLANS.get(plan_id, {})
                plan_name = plan.get('name', 'Неизвестный тариф')
                
                if reminder_type == '3_days':
                    message_text = (
                        f"⏰ <b>Напоминание о продлении подписки</b>\n\n"
                        f"Ваша подписка <b>{plan_name}</b> истекает через <b>3 дня</b> ({expires_at.strftime('%d.%m.%Y %H:%M')})\n\n"
                        f"Чтобы продолжить использование сервиса без перерывов, рекомендуем продлить подписку заранее.\n\n"
                        f"Для продления нажмите кнопку ниже ⬇️"
                    )
                elif reminder_type == '1_hour':
                    message_text = (
                        f"⚠️ <b>СРОЧНОЕ НАПОМИНАНИЕ</b>\n\n"
                        f"Ваша подписка <b>{plan_name}</b> истекает через <b>1 час</b>!\n"
                        f"Дата окончания: {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                        f"<b>Внимание!</b> После окончания подписки:\n"
                        f"• Доступ к сервису будет приостановлен\n"
                        f"• Ваш бот перестанет работать\n"
                        f"• Данные могут быть временно недоступны\n\n"
                        f"Срочно продлите подписку! ⬇️"
                    )
                else:
                    continue
                
                try:
                    await notify_user(telegram_id, message_text)

                    # Отмечаем напоминание как отправленное
                    db.mark_reminder_sent(reminder_id)
                    logger.info(f"Отправлено напоминание {reminder_type} пользователю {telegram_id} ({username})")

                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания пользователю {telegram_id}: {e}")
                    # Помечаем напоминание как отправленное, чтобы не пытаться снова
                    db.mark_reminder_sent(reminder_id)
            
            # Ждем 1 минуту перед следующей проверкой
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в процессе отправки напоминаний: {e}")
            await asyncio.sleep(60)

@dp.message(Command("refund"))
async def cmd_refund(message: Message):
    """Команда для возврата оплаты (только для админа)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    # Парсим команду: /refund <telegram_user_id> <payment_id> [amount]
    parts = message.text.split()
    
    if len(parts) < 3:
        await message.answer(
            "📋 <b>Использование:</b>\n"
            "/refund <telegram_id> <payment_id> [amount]\n\n"
            "Примеры:\n"
            "/refund 123456789 stxnPZnwspnU6PSPbCWe7roJKXVSAzz2eG9r5I9WqSguFLA5C7T6MGrSX7jU6AfMxD0AP6qGOZu33NoAMpUDNDYna13tUvWV6ezovADnrKptHo\n"
            "/refund 123456789 payment_id_here 249\n\n"
            "Если amount не указан, возвращается полная сумма платежа",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        telegram_id = int(parts[1])
        payment_id = parts[2]
        stars_amount = int(parts[3]) if len(parts) > 3 else None
        
        # Получаем информацию о пользователе
        user = db.get_user(telegram_id)
        if not user:
            await message.answer(f"❌ Пользователь с ID {telegram_id} не найден")
            return
        
        # Показываем ожидание
        processing_msg = await message.answer("🔄 Обработка запроса на возврат...")
        
        # Выполняем возврат
        success = await refund_star_payment(telegram_id, payment_id, stars_amount)
        
        if success:
            # Обновляем статус возврата в базе
            if user[3]:  # license_key
                # Деактивируем лицензию
                db.deactivate_license(user[3])
                db.clear_user_subscription(telegram_id)

                # Ищем запрос на возврат для этого пользователя
                cursor = db.conn.cursor()
                cursor.execute('''
                    SELECT * FROM refund_requests
                    WHERE user_id = ? AND license_key = ? AND status = 'pending'
                ''', (telegram_id, user[3]))
                refund_request = cursor.fetchone()
                
                if refund_request:
                    db.update_refund_status(refund_request[0], "approved")
            
            await processing_msg.edit_text(
                f"✅ <b>Возврат успешно выполнен!</b>\n\n"
                f"👤 Пользователь: {user[2] or 'Без имени'} (ID: {telegram_id})\n"
                f"💰 ID платежа: <code>{payment_id}</code>\n"
                f"⭐ Сумма: {stars_amount or 'полная'} звезд\n\n"
                f"✅ Средства возвращены на счет пользователя.\n"
                f"✅ Лицензия деактивирована.",
                parse_mode=ParseMode.HTML
            )

            # Уведомляем пользователя о возврате
            try:
                await notify_user(
                    telegram_id,
                    f"✅ <b>Ваш возврат обработан!</b>\n\n"
                    f"Сумма: {stars_amount or 'полная'} ⭐\n"
                    f"Статус: Возврат успешно выполнен\n"
                    f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Средства возвращены на ваш счет.\n"
                    f"Ваша подписка отменена.",
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {telegram_id}: {e}")
                
        else:
            await processing_msg.edit_text(
                f"❌ <b>Ошибка при возврате</b>\n\n"
                f"👤 Пользователь: {user[2] or 'Без имени'} (ID: {telegram_id})\n"
                f"💰 ID платежа: <code>{payment_id}</code>\n\n"
                f"⚠️ <b>Возможные причины:</b>\n"
                f"• Неверный ID платежа\n"
                f"• Прошло больше 48 часов с момента оплаты\n"
                f"• У бота нет прав на возврат\n"
                f"• Платеж уже был возвращен ранее",
                parse_mode=ParseMode.HTML
            )
        
    except ValueError as e:
        await message.answer(f"❌ Неверный формат: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /refund: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.callback_query(F.data == "my_license")
async def my_license(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    
    active_license = db.get_active_license(callback.from_user.id)
    queued = db.get_queued_subscription(callback.from_user.id)
    
    if not active_license and not queued:
        keyboard = [
            [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")],
            [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            "❌ У вас нет активной подписки.\n\n"
            "Выберите тариф для начала работы:",
            reply_markup=reply_markup
        )
        return
    
    license_info = ""
    
    if active_license:
        plan = SUBSCRIPTION_PLANS.get(active_license[4])
        end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
        license_key = active_license[3]
        
        if callback.from_user.id in ADMIN_IDS:
            refund_status = "👑 Доступен (админ)"
        else:
            refund_status = "📩 Через администратора"
        
        license_info += f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{license_key}</code>\n\n"
        license_info += f"📋 <b>Текущая подписка:</b>\n"
        license_info += f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
        license_info += f"• Статус: ✅ Активна\n"
        license_info += f"• Стоимость: {plan['stars'] if plan else 0} ⭐\n"
        license_info += f"• Возврат: {refund_status}\n"
        
        if end_date:
            license_info += f"• Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    if queued:
        queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        license_info += f"\n📋 <b>Подписка в очереди:</b>\n"
        license_info += f"• Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
        license_info += f"• Стоимость: {queued[4]} ⭐\n"
        license_info += f"• Статус: ⏳ Ожидает активации\n"
        if active_license:
            end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
            license_info += f"• Активируется: {end_date.strftime('%d.%m.%Y') if end_date else 'после текущей'}\n"
    
    keyboard = []
    if active_license or queued:
        keyboard.append([InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        license_info,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("reset_sub"))
async def reset_sub(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    active_license = db.get_active_license(message.from_user.id)
    if not active_license:
        await message.answer("❌ У вас нет активной подписки для сброса")
        return
    
    queued = db.get_queued_subscription(message.from_user.id)
    
    cursor = db.conn.cursor()
    cursor.execute('''
        UPDATE users SET subscription_end_date = ? WHERE telegram_id = ?
    ''', ('2020-01-01T00:00:00', message.from_user.id))
    cursor.execute('''
        UPDATE license_keys SET expires_at = ? WHERE key = ?
    ''', ('2020-01-01T00:00:00', active_license[3]))
    db.conn.commit()
    
    queue_info = ""
    if queued:
        queued_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        queue_info = f"\n\n📋 <b>Подписка в очереди:</b> {queued_plan.get('name', '?')}\n⏳ Активируется через ~1 минуту автоматически"
    else:
        queue_info = "\n\n⚠️ Нет подписки в очереди для автоактивации"
    
    await message.answer(
        f"✅ <b>Подписка сброшена!</b>\n\n"
        f"• Дата окончания установлена в прошлое\n"
        f"• Лицензия: <code>{active_license[3]}</code>"
        f"{queue_info}",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("refund_status"))
async def refund_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    parts = message.text.split()
    if len(parts) > 1:
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID")
            return
    else:
        telegram_id = message.from_user.id
    
    user = db.get_user(telegram_id)
    if not user:
        await message.answer(f"❌ Пользователь {telegram_id} не найден")
        return
    
    has_used = db.has_user_used_refund(telegram_id)
    
    await message.answer(
        f"📊 <b>Статус возврата</b>\n\n"
        f"👤 Пользователь: {user[2] or 'Без имени'}\n"
        f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
        f"💰 Возврат использован: {'❌ Да' if has_used else '✅ Нет (доступен)'}\n\n"
        f"<i>Использование: /refund_status [telegram_id]</i>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("reset_refund"))
async def reset_refund(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    parts = message.text.split()
    if len(parts) > 1:
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID")
            return
    else:
        telegram_id = message.from_user.id
    
    success = db.reset_refund_status(telegram_id)
    
    if success:
        await message.answer(
            f"✅ <b>Статус возврата сброшен!</b>\n\n"
            f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
            f"💰 Теперь возврат снова доступен\n\n"
            f"<i>Использование: /reset_refund [telegram_id]</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(f"❌ Пользователь {telegram_id} не найден")

@dp.message(Command("set_refund_used"))
async def set_refund_used(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    parts = message.text.split()
    if len(parts) > 1:
        try:
            telegram_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID")
            return
    else:
        telegram_id = message.from_user.id
    
    success = db.mark_refund_used(telegram_id)
    
    if success:
        await message.answer(
            f"✅ <b>Возврат помечен как использованный!</b>\n\n"
            f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
            f"💰 Теперь возврат недоступен\n\n"
            f"<i>Использование: /set_refund_used [telegram_id]</i>",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(f"❌ Пользователь {telegram_id} не найден")

@dp.callback_query(F.data == "bot_settings")
async def bot_settings_menu(callback: CallbackQuery):
    active_license = db.get_active_license(callback.from_user.id)
    if not active_license:
        await callback.answer("❌ Для доступа к настройкам нужна активная подписка", show_alert=True)
        return

    plan_name = db.get_user_plan_name(callback.from_user.id)

    # SELF-HOST: показываем только ключ и документацию
    if plan_name == "SELF-HOST":
        keyboard = [
            [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
            [InlineKeyboardButton(text="📖 Документация", url="https://seventyzero.github.io/tgbotnft-docs/")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await callback.message.edit_text(
            "📦 <b>SELF-HOST</b>\n\n"
            "Ваш тариф предполагает самостоятельную настройку бота на вашем сервере.\n\n"
            "Используйте лицензионный ключ и документацию для установки.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        return

    settings = db.get_bot_settings(callback.from_user.id)
    bot_token_val = settings[0] if settings and settings[0] else None
    session_string = db.get_session_string(callback.from_user.id)
    deployment_info = db.get_deployment_info(callback.from_user.id)
    deployment_status = deployment_info[0] if deployment_info else None

    status_token = "✅" if bot_token_val else "❌"
    status_session = "✅" if session_string else "❌"
    all_configured = bot_token_val and session_string

    # Автозапуск для HOSTING: если всё настроено и ожидает setup
    if plan_name == "HOSTING" and all_configured and deployment_status == "pending_setup":
        import docker_manager
        user = db.get_user(callback.from_user.id)
        license_key = user[3] if user else None
        api_id = settings[1] if settings and len(settings) > 1 else ""
        api_hash = settings[2] if settings and len(settings) > 2 else ""
        container_id = await docker_manager.start_container(
            telegram_id=callback.from_user.id,
            bot_token=bot_token_val,
            api_id=api_id or "",
            api_hash=api_hash or "",
            session_string=session_string,
            license_key=license_key or "",
        )
        if container_id:
            db.update_deployment_status(callback.from_user.id, "running")
            db.update_container_id(callback.from_user.id, container_id)
            deployment_status = "running"
        else:
            deployment_status = "pending_setup"

    # Автоуведомление для HOSTING-PRO: если всё настроено и ожидает setup -> awaiting_admin
    if plan_name == "HOSTING-PRO" and all_configured and deployment_status == "pending_setup":
        db.update_deployment_status(callback.from_user.id, "awaiting_admin")
        deployment_status = "awaiting_admin"
        uname = f"@{callback.from_user.username}" if callback.from_user.username else f"ID:{callback.from_user.id}"
        for admin_id in ADMIN_IDS:
            try:
                admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Деплой выполнен", callback_data=f"admin_deploy_done_{callback.from_user.id}")],
                    [InlineKeyboardButton(text="👤 Карточка", callback_data=f"admin_user_{callback.from_user.id}")],
                ])
                await bot.send_message(
                    admin_id,
                    f"🚀 <b>HOSTING-PRO: готов к деплою!</b>\n\n"
                    f"👤 {uname} (ID: <code>{callback.from_user.id}</code>)\n"
                    f"Все данные настроены. Необходим ручной деплой на VPS.",
                    reply_markup=admin_kb,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    # Формируем текст
    text = f"⚙️ <b>Управление ботом ({plan_name})</b>\n\n"

    if plan_name == "HOSTING":
        if deployment_status == "running":
            text += "🟢 <b>Статус:</b> Бот запущен\n\n"
        elif deployment_status == "stopped":
            text += "🔴 <b>Статус:</b> Бот остановлен\n\n"
        elif deployment_status == "pending_setup":
            text += "⚙️ <b>Статус:</b> Ожидает настройки\n\n"
        else:
            text += f"⚪ <b>Статус:</b> {deployment_status or 'не определён'}\n\n"
    elif plan_name == "HOSTING-PRO":
        if deployment_status == "awaiting_admin":
            text += "⏳ <b>Статус:</b> Ожидание развёртывания администратором\n\n"
        elif deployment_status == "running":
            text += "🟢 <b>Статус:</b> Бот запущен на VPS\n\n"
        elif deployment_status == "stopped":
            text += "🔴 <b>Статус:</b> Бот остановлен\n\n"
        elif deployment_status == "pending_setup":
            text += "⚙️ <b>Статус:</b> Ожидает настройки\n\n"
        else:
            text += f"⚪ <b>Статус:</b> {deployment_status or 'не определён'}\n\n"

    text += (
        f"{status_token} <b>Bot Token</b> — токен от @BotFather\n"
        f"{status_session} <b>Telegram сессия</b> — авторизация аккаунта\n\n"
    )

    if all_configured and deployment_status == "running":
        text += "✅ <b>Все данные настроены!</b> Бот работает."
    elif all_configured and deployment_status == "awaiting_admin":
        text += "✅ <b>Все данные настроены!</b> Ожидайте развёртывания."
    elif all_configured:
        text += "✅ <b>Все данные настроены!</b>"
    else:
        text += "⚠️ <b>Необходимо заполнить все данные</b> для активации бота."

    keyboard = [
        [InlineKeyboardButton(text=f"{status_token} Изменить Bot Token", callback_data="setup_bot_token")],
        [InlineKeyboardButton(text=f"{status_session} Авторизоваться", callback_data="generate_auth_link")],
    ]

    # Кнопки управления контейнером (только HOSTING с настроенными данными)
    if plan_name == "HOSTING" and all_configured:
        if deployment_status == "running":
            keyboard.append([
                InlineKeyboardButton(text="⏹ Остановить", callback_data="manage_bot_stop"),
                InlineKeyboardButton(text="🔄 Перезапустить", callback_data="manage_bot_restart"),
            ])
            keyboard.append([InlineKeyboardButton(text="📋 Логи", callback_data="manage_bot_logs")])
            keyboard.append([InlineKeyboardButton(text="📊 Статус", callback_data="manage_bot_status")])
        elif deployment_status in ("stopped", "pending_setup"):
            keyboard.append([InlineKeyboardButton(text="▶️ Запустить", callback_data="manage_bot_start")])

    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "setup_bot_token")
async def setup_bot_token(callback: CallbackQuery, state: FSMContext):
    keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data="bot_settings")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "🤖 <b>Настройка Bot Token</b>\n\n"
        "Отправьте токен вашего бота от @BotFather.\n\n"
        "<b>Как получить токен:</b>\n"
        "1. Откройте @BotFather\n"
        "2. Отправьте команду /newbot\n"
        "3. Укажите имя и username бота\n"
        "4. Скопируйте полученный токен\n\n"
        "Формат токена: <code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789</code>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(BotSetupStates.waiting_bot_token)

@dp.message(BotSetupStates.waiting_bot_token)
async def process_bot_token(message: Message, state: FSMContext):
    token = message.text.strip()
    
    if not token or ":" not in token or len(token) < 40:
        await message.answer(
            "❌ Неверный формат токена.\n\n"
            "Токен должен выглядеть примерно так:\n"
            "<code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789</code>\n\n"
            "Попробуйте ещё раз:",
            parse_mode=ParseMode.HTML
        )
        return
    
    db.update_bot_token(message.from_user.id, token)
    await state.clear()

    keyboard = [
        [InlineKeyboardButton(text="➡️ Авторизоваться", callback_data="generate_auth_link")],
        [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="bot_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "✅ <b>Bot Token сохранён!</b>\n\n"
        "Теперь пройдите авторизацию Telegram для работы бота.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "generate_auth_link")
async def generate_auth_link(callback: CallbackQuery):
    active_license = db.get_active_license(callback.from_user.id)
    if not active_license:
        await callback.answer("❌ Для доступа нужна активная подписка", show_alert=True)
        return

    from web_auth import generate_auth_token
    token = generate_auth_token(callback.from_user.id)
    url = f"{WEB_AUTH_HOST}/auth/{token}"

    keyboard = [
        [InlineKeyboardButton(text="⬅️ К настройкам", callback_data="bot_settings")]
    ]
    # Telegram требует HTTPS для URL-кнопок, поэтому если хост не https — отправляем ссылку текстом
    if url.startswith("https://"):
        keyboard.insert(0, [InlineKeyboardButton(text="🔐 Открыть авторизацию", url=url)])
        link_text = ""
    else:
        link_text = f"\n🔗 <code>{url}</code>\n\nСкопируйте ссылку и откройте в браузере.\n"

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "🔐 <b>Авторизация Telegram</b>\n\n"
        "На странице авторизации вы сможете:\n"
        "1. Указать Bot Token\n"
        "2. Ввести номер телефона\n"
        "3. Подтвердить код из Telegram\n\n"
        f"{link_text}"
        "⏱ Ссылка действительна <b>15 минут</b>.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# ==================== УПРАВЛЕНИЕ КОНТЕЙНЕРАМИ ====================

@dp.callback_query(F.data == "manage_bot_start")
async def manage_bot_start_cb(callback: CallbackQuery):
    import docker_manager
    plan_name = db.get_user_plan_name(callback.from_user.id)
    if plan_name != "HOSTING":
        await callback.answer("❌ Эта функция доступна только на тарифе HOSTING", show_alert=True)
        return

    settings = db.get_bot_settings(callback.from_user.id)
    bot_token_val = settings[0] if settings and settings[0] else None
    session_string = db.get_session_string(callback.from_user.id)
    if not bot_token_val or not session_string:
        await callback.answer("❌ Сначала настройте Bot Token и авторизацию", show_alert=True)
        return

    user = db.get_user(callback.from_user.id)
    license_key = user[3] if user else ""
    api_id = settings[1] if settings and len(settings) > 1 else ""
    api_hash = settings[2] if settings and len(settings) > 2 else ""

    await callback.answer("🔄 Запускаю бота...")
    container_id = await docker_manager.start_container(
        telegram_id=callback.from_user.id,
        bot_token=bot_token_val,
        api_id=api_id or "",
        api_hash=api_hash or "",
        session_string=session_string,
        license_key=license_key or "",
    )
    if container_id:
        db.update_deployment_status(callback.from_user.id, "running")
        db.update_container_id(callback.from_user.id, container_id)
        await callback.message.edit_text(
            "✅ <b>Бот успешно запущен!</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
            ]),
            parse_mode=ParseMode.HTML,
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Не удалось запустить бота.</b>\nПроверьте настройки или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
            ]),
            parse_mode=ParseMode.HTML,
        )


@dp.callback_query(F.data == "manage_bot_stop")
async def manage_bot_stop_cb(callback: CallbackQuery):
    import docker_manager
    plan_name = db.get_user_plan_name(callback.from_user.id)
    if plan_name != "HOSTING":
        await callback.answer("❌ Эта функция доступна только на тарифе HOSTING", show_alert=True)
        return

    await callback.answer("🔄 Останавливаю бота...")
    success = await docker_manager.stop_container(callback.from_user.id)
    if success:
        db.update_deployment_status(callback.from_user.id, "stopped")
    await callback.message.edit_text(
        "✅ <b>Бот остановлен.</b>" if success else "❌ <b>Не удалось остановить бота.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
        ]),
        parse_mode=ParseMode.HTML,
    )


@dp.callback_query(F.data == "manage_bot_restart")
async def manage_bot_restart_cb(callback: CallbackQuery):
    import docker_manager
    plan_name = db.get_user_plan_name(callback.from_user.id)
    if plan_name != "HOSTING":
        await callback.answer("❌ Эта функция доступна только на тарифе HOSTING", show_alert=True)
        return

    await callback.answer("🔄 Перезапускаю бота...")
    success = await docker_manager.restart_container(callback.from_user.id)
    await callback.message.edit_text(
        "✅ <b>Бот перезапущен.</b>" if success else "❌ <b>Не удалось перезапустить бота.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
        ]),
        parse_mode=ParseMode.HTML,
    )


@dp.callback_query(F.data == "manage_bot_logs")
async def manage_bot_logs_cb(callback: CallbackQuery):
    import docker_manager
    plan_name = db.get_user_plan_name(callback.from_user.id)
    if plan_name != "HOSTING":
        await callback.answer("❌ Эта функция доступна только на тарифе HOSTING", show_alert=True)
        return

    logs = await docker_manager.get_container_logs(callback.from_user.id, lines=50)
    # Ограничим длину для Telegram (4096 символов)
    if len(logs) > 3800:
        logs = "...\n" + logs[-3800:]

    await callback.message.edit_text(
        f"📋 <b>Логи бота</b> (последние 50 строк):\n\n<pre>{logs}</pre>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="manage_bot_logs")],
            [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
        ]),
        parse_mode=ParseMode.HTML,
    )


@dp.callback_query(F.data == "manage_bot_status")
async def manage_bot_status_cb(callback: CallbackQuery):
    import docker_manager
    plan_name = db.get_user_plan_name(callback.from_user.id)
    if plan_name != "HOSTING":
        await callback.answer("❌ Эта функция доступна только на тарифе HOSTING", show_alert=True)
        return

    status = await docker_manager.get_container_status(callback.from_user.id)
    status_emoji = {"running": "🟢", "stopped": "🔴", "not_found": "⚪"}.get(status, "⚪")

    await callback.message.edit_text(
        f"📊 <b>Статус контейнера</b>\n\n{status_emoji} {status}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="manage_bot_status")],
            [InlineKeyboardButton(text="⬅️ К управлению", callback_data="bot_settings")]
        ]),
        parse_mode=ParseMode.HTML,
    )

# ==================== КОНЕЦ УПРАВЛЕНИЯ КОНТЕЙНЕРАМИ ====================

@dp.callback_query(F.data == "help")
async def help_command(callback: CallbackQuery):
    help_text = (
        "ℹ️ <b>Помощь - Service Bot</b>\n\n"
        "📖 Полная документация по настройке бота:\n"
        "https://seventyzero.github.io/tgbotnft-docs/\n\n"
        "Поддержка:\n"
        "Если у вас возникли вопросы, свяжитесь с @Dimopster."
    )

    keyboard = [
        [InlineKeyboardButton(text="📩 Связаться с админом", callback_data="contact_admin")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "contact_admin")
async def contact_admin(callback: CallbackQuery, state: FSMContext):
    keyboard = [[InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "📩 <b>Связаться с администратором</b>\n\n"
        "Напишите ваше сообщение, и оно будет отправлено администратору:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )
    await state.set_state(UserStates.waiting_admin_message)

@dp.message(UserStates.waiting_admin_message)
async def user_admin_message_handler(message: Message, state: FSMContext):
    await state.clear()
    tid = message.from_user.id
    uname = f"@{message.from_user.username}" if message.from_user.username else f"ID:{tid}"
    text = message.text.strip() if message.text else "(пустое сообщение)"

    for admin_id in ADMIN_IDS:
        try:
            keyboard = [[InlineKeyboardButton(text="✉️ Ответить", callback_data=f"admin_msg_{tid}"),
                          InlineKeyboardButton(text="👤 Карточка", callback_data=f"admin_user_{tid}")]]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await bot.send_message(
                admin_id,
                f"📩 <b>Сообщение от пользователя</b>\n\n"
                f"👤 {uname} (ID: <code>{tid}</code>)\n\n"
                f"{text}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

    await delete_tracked_messages(tid)
    reply_markup = build_main_menu_keyboard(tid)
    msg = await message.answer(
        "✅ Ваше сообщение отправлено администратору. Ожидайте ответа.",
        reply_markup=reply_markup,
    )
    user_menu_message[tid] = msg.message_id

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    reply_markup = build_main_menu_keyboard(callback.from_user.id)
    await callback.message.edit_text(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup
    )
    user_menu_message[callback.from_user.id] = callback.message.message_id

async def process_queued_subscriptions():
    while True:
        try:
            expired = db.get_expired_subscriptions_with_queue()
            
            for row in expired:
                user_id = row[0]
                telegram_id = row[1]
                old_license_key = row[2]
                queue_id = row[3]
                plan_id = row[6]
                stars_amount = row[7]
                payment_charge_id = row[8]
                
                plan = SUBSCRIPTION_PLANS.get(plan_id)
                if not plan:
                    logger.error(f"План {plan_id} не найден для очереди {queue_id}")
                    continue
                
                db.deactivate_license(old_license_key)
                
                new_license_key = db.create_license_key(user_id, plan_id, plan["duration_days"])
                end_date = (datetime.now() + timedelta(days=plan["duration_days"])).isoformat()
                
                db.update_user_subscription(telegram_id, plan_id, new_license_key, end_date)
                
                db.save_payment(
                    user_id=user_id,
                    license_key=new_license_key,
                    stars_amount=stars_amount,
                    telegram_payment_charge_id=payment_charge_id
                )
                
                db.delete_queued_subscription(telegram_id)
                
                try:
                    await notify_user(
                        telegram_id,
                        f"🎉 <b>Подписка автоматически продлена!</b>\n\n"
                        f"📋 <b>Детали:</b>\n"
                        f"• Тариф: {plan['name']}\n"
                        f"• Срок: {plan['duration_days']} дней\n"
                        f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
                        f"Новый лицензионный ключ сгенерирован.",
                    )
                    logger.info(f"Активирована подписка из очереди для {telegram_id}")
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя {telegram_id}: {e}")
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в process_queued_subscriptions: {e}")
            await asyncio.sleep(60)

@dp.callback_query(F.data == "contact_admin_refund")
async def contact_admin_refund(callback: CallbackQuery):
    """Связаться с админом для возврата средств"""
    user = db.get_user(callback.from_user.id)
    plan = SUBSCRIPTION_PLANS.get(user[4], {}) if user and user[4] else {}
    uname = f"@{callback.from_user.username}" if callback.from_user.username else f"ID:{callback.from_user.id}"

    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [[InlineKeyboardButton(text="👤 Открыть карточку", callback_data=f"admin_user_{callback.from_user.id}")]]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await bot.send_message(
                admin_id,
                f"📩 <b>Запрос на возврат</b>\n\n"
                f"👤 Пользователь: {uname} (ID: <code>{callback.from_user.id}</code>)\n"
                f"📦 Тариф: {plan.get('name', '—')}\n"
                f"⭐ Стоимость: {plan.get('stars', '—')} ⭐\n\n"
                f"Пользователь просит рассмотреть возврат средств.",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    keyboard = [[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "✅ <b>Запрос отправлен!</b>\n\n"
        "Администратор получил ваш запрос на возврат средств.\n"
        "Ожидайте ответа.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# ==================== АДМИН-ПАНЕЛЬ ====================

def _admin_keyboard() -> InlineKeyboardMarkup:
    awaiting = db.get_awaiting_admin_users()
    keyboard = [
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_search")],
        [InlineKeyboardButton(text="💰 Возврат по транзакции", callback_data="admin_refund_txn")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ]
    if awaiting:
        keyboard.append([InlineKeyboardButton(
            text=f"🚀 HOSTING-PRO: деплой ({len(awaiting)})",
            callback_data="admin_hosting_pro"
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    reply_markup = _admin_keyboard()
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    reply_markup = _admin_keyboard()
    await callback.message.edit_text(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.callback_query(F.data == "admin_back")
async def admin_back_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    reply_markup = _admin_keyboard()
    await callback.message.edit_text(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Статистика ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    cursor = db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end_date > datetime('now') AND license_key IS NOT NULL")
    active_subs = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM queued_subscriptions')
    queued_subs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_end_date <= datetime('now') AND license_key IS NOT NULL")
    expired_subs = cursor.fetchone()[0]
    keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n"
        f"⏳ В очереди: <b>{queued_subs}</b>\n"
        f"❌ Истёкших: <b>{expired_subs}</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- HOSTING-PRO: ожидающие деплоя ---
@dp.callback_query(F.data == "admin_hosting_pro")
async def admin_hosting_pro_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    awaiting = db.get_awaiting_admin_users()
    if not awaiting:
        await callback.answer("Нет пользователей, ожидающих деплоя", show_alert=True)
        return
    text = "🚀 <b>HOSTING-PRO: ожидают деплоя</b>\n\n"
    keyboard = []
    for u in awaiting:
        tid = u[1]
        uname = f"@{u[2]}" if u[2] else f"ID:{tid}"
        plan_id = u[4]
        plan_info = SUBSCRIPTION_PLANS.get(plan_id, {})
        text += f"👤 {uname} (ID: <code>{tid}</code>) — {plan_info.get('name', plan_id)}\n"
        keyboard.append([
            InlineKeyboardButton(text=f"✅ Деплой: {uname}", callback_data=f"admin_deploy_done_{tid}"),
            InlineKeyboardButton(text=f"👤", callback_data=f"admin_user_{tid}"),
        ])
    keyboard.append([InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


@dp.callback_query(F.data.startswith("admin_deploy_done_"))
async def admin_deploy_done_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_deploy_done_", ""))
    db.update_deployment_status(tid, "running")
    user = db.get_user(tid)
    uname = f"@{user[2]}" if user and user[2] else f"ID:{tid}"

    # Уведомить пользователя
    try:
        await bot.send_message(
            tid,
            "✅ <b>Ваш бот развёрнут!</b>\n\n"
            "Администратор выполнил деплой на отдельном VPS.\n"
            "Ваш бот уже запущен и работает.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить {tid} о деплое: {e}")

    await callback.message.edit_text(
        f"✅ <b>Деплой отмечен!</b>\n\n"
        f"👤 {uname} (ID: <code>{tid}</code>)\n"
        f"Статус изменён на <b>running</b>.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]
        ]),
        parse_mode=ParseMode.HTML,
    )


# --- Список пользователей (пагинация) ---
def _build_users_page(users: list, page: int, total: int, per_page: int = 10):
    total_pages = max(1, (total + per_page - 1) // per_page)
    lines = []
    for u in users:
        tid = u[1]
        uname = f"@{u[2]}" if u[2] else "Без имени"
        plan = u[4]
        end = u[5]
        if plan and end:
            try:
                end_dt = datetime.fromisoformat(end)
                plan_name = SUBSCRIPTION_PLANS.get(plan, {}).get("name", plan)
                lines.append(f"👤 {uname} (ID: {tid})\n  • Тариф: {plan_name} | До: {end_dt.strftime('%d.%m.%Y')}")
            except Exception:
                lines.append(f"👤 {uname} (ID: {tid})\n  • Тариф: {plan}")
        else:
            lines.append(f"👤 {uname} (ID: {tid})\n  • Нет подписки")
    text = f"👥 <b>Пользователи</b> (стр. {page + 1}/{total_pages})\n\n" + "\n\n".join(lines) if lines else "Нет пользователей."
    keyboard = []
    # Кнопки пользователей
    for u in users:
        tid = u[1]
        uname = f"@{u[2]}" if u[2] else f"ID:{tid}"
        keyboard.append([InlineKeyboardButton(text=f"👤 {uname}", callback_data=f"admin_user_{tid}")])
    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_users_page_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️ Вперёд", callback_data=f"admin_users_page_{page + 1}"))
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")])
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.callback_query(F.data == "admin_users")
async def admin_users_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    users, total = db.get_users_page(0, 10)
    text, reply_markup = _build_users_page(users, 0, total)
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("admin_users_page_"))
async def admin_users_page_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    page = int(callback.data.replace("admin_users_page_", ""))
    users, total = db.get_users_page(page * 10, 10)
    text, reply_markup = _build_users_page(users, page, total)
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()

# --- Поиск пользователя ---
@dp.callback_query(F.data == "admin_search")
async def admin_search_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_search)
    keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\nВведите Telegram ID (число) или username:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.message(AdminStates.waiting_user_search)
async def admin_search_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    query = message.text.strip().lstrip("@")
    results = db.search_users(query)
    await state.clear()
    if not results:
        keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer("🔍 Ничего не найдено.", reply_markup=reply_markup)
        return
    keyboard = []
    for u in results:
        tid = u[1]
        uname = f"@{u[2]}" if u[2] else f"ID:{tid}"
        keyboard.append([InlineKeyboardButton(text=f"👤 {uname} (ID: {tid})", callback_data=f"admin_user_{tid}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(f"🔍 Найдено: {len(results)}", reply_markup=reply_markup)

# --- Карточка пользователя ---
@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user_card_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_user_", ""))
    user = db.get_user(tid)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    uname = f"@{user[2]}" if user[2] else "Без имени"
    created = user[11] if len(user) > 11 and user[11] else "—"
    plan_id = user[4]
    license_key = user[3]
    end_date_str = user[5]
    has_used_refund = db.has_user_used_refund(tid)

    text = f"👤 Пользователь {uname}\n"
    text += f"📋 Telegram ID: <code>{tid}</code>\n"
    text += f"📅 Зарегистрирован: {created}\n\n"

    active = db.get_active_license(tid)
    if active and plan_id:
        plan_info = SUBSCRIPTION_PLANS.get(plan_id, {})
        plan_name = plan_info.get("name", plan_id)
        text += f"📦 Подписка: {plan_name} ({plan_id})\n"
        text += f"🔑 Ключ: <code>{license_key}</code>\n"
        if end_date_str:
            try:
                end_dt = datetime.fromisoformat(end_date_str)
                days_left = max(0, (end_dt - datetime.now()).days)
                text += f"📅 Действует до: {end_dt.strftime('%d.%m.%Y')}\n"
                text += f"⏳ Осталось: {days_left} дн.\n"
            except Exception:
                text += f"📅 До: {end_date_str}\n"
        refund_icon = "❌ Использован" if has_used_refund else "✅ Доступен"
        text += f"💰 Возврат: {refund_icon}\n"
        # Показать transaction ID последнего платежа
        payment = db.get_payment_by_license(license_key)
        if payment:
            text += f"🧾 Транзакция: <code>{payment[4]}</code>\n"
    else:
        text += "📦 Подписка: Нет\n"

    queued = db.get_queued_subscription(tid)
    if queued:
        q_plan = SUBSCRIPTION_PLANS.get(queued[3], {})
        text += f"\n📋 В очереди: {q_plan.get('name', queued[3])}"
    else:
        text += "\n📋 В очереди: Нет"

    keyboard = []
    keyboard.append([InlineKeyboardButton(text="🎁 Выдать подписку", callback_data=f"admin_grant_{tid}")])
    if active and plan_id:
        keyboard.append([InlineKeyboardButton(text="❌ Отменить с возвратом", callback_data=f"admin_cancel_refund_{tid}")])
        keyboard.append([InlineKeyboardButton(text="🚫 Отменить без возврата", callback_data=f"admin_cancel_norefund_{tid}")])
    keyboard.append([InlineKeyboardButton(text="✉️ Написать сообщение", callback_data=f"admin_msg_{tid}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="admin_users")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# --- Возврат по транзакции ---
@dp.callback_query(F.data == "admin_refund_txn")
async def admin_refund_txn_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_refund_txn)
    keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "💰 <b>Возврат по транзакции</b>\n\n"
        "Введите <b>telegram_payment_charge_id</b> (длинный хеш транзакции):",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.message(AdminStates.waiting_refund_txn)
async def admin_refund_txn_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    manual_charge_id = data.get("manual_charge_id")

    # Второй шаг: ввод telegram_id для ручного возврата
    if manual_charge_id:
        await state.clear()
        tid_str = message.text.strip()
        if not tid_str.isdigit():
            await message.answer("❌ Telegram ID должен быть числом. Начните заново через /admin.")
            return
        tid = int(tid_str)
        keyboard = [
            [InlineKeyboardButton(text="✅ Да, вернуть", callback_data=f"armr_{tid}_{manual_charge_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back")],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"💰 <b>Ручной возврат</b>\n\n"
            f"👤 Telegram ID: <code>{tid}</code>\n"
            f"🧾 Транзакция: <code>{manual_charge_id}</code>\n\n"
            f"Выполнить возврат?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        return

    # Первый шаг: ввод charge_id
    charge_id = message.text.strip()
    await state.clear()

    payment = db.get_payment_by_charge_id(charge_id)
    if payment:
        tid = payment[6]
        uname = f"@{payment[7]}" if payment[7] else f"ID:{tid}"
        stars = payment[3]
        created = payment[5] or "—"
        # charge_id слишком длинный для callback_data (лимит 64), сохраняем в state
        await state.set_data({"refund_charge_id": charge_id, "refund_tid": tid})
        keyboard = [
            [InlineKeyboardButton(text=f"✅ Да, вернуть {stars} ⭐", callback_data="artc_confirm")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back")],
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"💰 <b>Платёж найден</b>\n\n"
            f"👤 Пользователь: {uname} (ID: <code>{tid}</code>)\n"
            f"⭐ Сумма: {stars}\n"
            f"🔑 Ключ: <code>{payment[2]}</code>\n"
            f"📅 Дата: {created}\n"
            f"🧾 ID: <code>{charge_id}</code>\n\n"
            f"Выполнить возврат?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    else:
        await state.set_state(AdminStates.waiting_refund_txn)
        await state.update_data(manual_charge_id=charge_id)
        keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(
            f"⚠️ Платёж с таким ID не найден в базе.\n\n"
            f"Для ручного возврата введите <b>Telegram ID пользователя</b>:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )

@dp.callback_query(F.data == "artc_confirm")
async def admin_refund_txn_confirm_cb(callback: CallbackQuery, state: FSMContext):
    """Возврат по транзакции (платёж найден в БД)"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    charge_id = data.get("refund_charge_id")
    await state.clear()
    if not charge_id:
        await callback.answer("❌ Данные утеряны, начните заново", show_alert=True)
        return
    payment = db.get_payment_by_charge_id(charge_id)
    if not payment:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return
    tid = payment[6]
    stars = payment[3]
    uname = f"@{payment[7]}" if payment[7] else f"ID:{tid}"

    await callback.message.edit_text("🔄 Выполняется возврат...", parse_mode=ParseMode.HTML)
    success = await refund_star_payment(telegram_id=tid, payment_id=charge_id, stars_amount=stars)

    if success:
        if payment[2]:
            db.deactivate_license(payment[2])
            user = db.get_user(tid)
            if user and user[3] == payment[2]:
                db.clear_user_subscription(tid)
        try:
            await notify_user(tid, f"✅ Вам выполнен возврат {stars} ⭐ администратором.")
        except Exception:
            pass
        result_text = f"✅ <b>Возврат выполнен!</b>\n\n👤 {uname}\n⭐ {stars}\n🧾 <code>{charge_id}</code>"
    else:
        result_text = (
            f"❌ <b>Возврат не удался</b>\n\n👤 {uname}\n🧾 <code>{charge_id}</code>\n\n"
            f"Возможные причины: прошло >48ч, уже возвращён, неверный ID."
        )

    keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(result_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "armr_confirm")
async def admin_refund_manual_confirm_cb(callback: CallbackQuery, state: FSMContext):
    """Ручной возврат (платёж НЕ в БД)"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    charge_id = data.get("refund_charge_id")
    tid = data.get("refund_tid")
    await state.clear()
    if not charge_id or not tid:
        await callback.answer("❌ Данные утеряны, начните заново", show_alert=True)
        return

    await callback.message.edit_text("🔄 Выполняется возврат...", parse_mode=ParseMode.HTML)
    success = await refund_star_payment(telegram_id=tid, payment_id=charge_id)

    if success:
        try:
            await notify_user(tid, "✅ Вам выполнен возврат звёзд администратором.")
        except Exception:
            pass
        result_text = f"✅ <b>Возврат выполнен!</b>\n\n👤 ID: {tid}\n🧾 <code>{charge_id}</code>"
    else:
        result_text = (
            f"❌ <b>Возврат не удался</b>\n\n👤 ID: {tid}\n🧾 <code>{charge_id}</code>\n\n"
            f"Возможные причины: прошло >48ч, уже возвращён, неверный ID."
        )

    keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(result_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# --- Выдать подписку бесплатно ---
@dp.callback_query(F.data.startswith("admin_grant_"))
async def admin_grant_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_grant_", ""))
    user = db.get_user(tid)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"
    keyboard = []
    for plan_id, plan_info in SUBSCRIPTION_PLANS.items():
        dur = f"{plan_info['duration_days']}д"
        # ag_ — короткий префикс чтобы уложиться в лимит callback_data
        keyboard.append([InlineKeyboardButton(
            text=f"{plan_info['name']} ({dur})",
            callback_data=f"ag_{tid}_{plan_id}"
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_user_{tid}")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"🎁 <b>Выдать подписку</b> для {uname}\n\nВыберите тариф:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.callback_query(F.data.startswith("ag_"))
async def admin_grant_plan_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    # ag_{tid}_{plan_id}
    parts = callback.data.split("_", 2)
    tid = int(parts[1])
    plan_id = parts[2]
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    user = db.get_user(tid)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"
    active = db.get_active_license(tid)
    warn = "\n⚠️ У пользователя есть активная подписка — она будет заменена." if active else ""
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, выдать", callback_data=f"agc_{tid}_{plan_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_{tid}")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"🎁 Выдать <b>{plan['name']}</b> ({plan['duration_days']} дн.) "
        f"пользователю {uname} бесплатно?{warn}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.callback_query(F.data.startswith("agc_"))
async def admin_grant_confirm_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    # agc_{tid}_{plan_id}
    parts = callback.data.split("_", 2)
    tid = int(parts[1])
    plan_id = parts[2]
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    user = db.get_user(tid)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"

    # Деактивируем старую подписку, если есть
    active = db.get_active_license(tid)
    if active and user[3]:
        db.deactivate_license(user[3])
        db.clear_user_subscription(tid)

    # Создаём новую подписку
    license_key = db.create_license_key(user[0], plan_id, plan["duration_days"])
    end_date = (datetime.now() + timedelta(days=plan["duration_days"])).isoformat()
    db.update_user_subscription(tid, plan_id, license_key, end_date)

    # Уведомляем пользователя
    try:
        await notify_user(
            tid,
            f"🎉 <b>Вам выдана подписка!</b>\n\n"
            f"📦 Тариф: {plan['name']}\n"
            f"📅 Срок: {plan['duration_days']} дн.\n"
            f"📅 До: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
            f"Лицензионный ключ сгенерирован.",
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить {tid} о выдаче подписки: {e}")

    keyboard = [[InlineKeyboardButton(text="👤 К карточке", callback_data=f"admin_user_{tid}"),
                  InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"✅ Подписка <b>{plan['name']}</b> ({plan['duration_days']} дн.) "
        f"выдана {uname}.\n🔑 <code>{license_key}</code>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Отмена с возвратом (подтверждение) ---
@dp.callback_query(F.data.startswith("admin_cancel_refund_"))
async def admin_cancel_refund_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_cancel_refund_", ""))
    user = db.get_user(tid)
    if not user or not user[3]:
        await callback.answer("❌ Нет активной подписки", show_alert=True)
        return
    plan_info = SUBSCRIPTION_PLANS.get(user[4], {})
    stars = plan_info.get("stars", 0)
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, отменить с возвратом", callback_data=f"admin_confirm_refund_{tid}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"admin_user_{tid}")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"⚠️ Отменить подписку {uname} с возвратом <b>{stars} ⭐</b>?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Отмена с возвратом (выполнение) ---
@dp.callback_query(F.data.startswith("admin_confirm_refund_"))
async def admin_confirm_refund_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_confirm_refund_", ""))
    user = db.get_user(tid)
    if not user or not user[3]:
        await callback.answer("❌ Нет активной подписки", show_alert=True)
        return
    license_key = user[3]
    plan_info = SUBSCRIPTION_PLANS.get(user[4], {})
    stars = plan_info.get("stars", 0)
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"

    payment_info = db.get_payment_by_license(license_key)
    db.deactivate_license(license_key)
    db.clear_user_subscription(tid)

    refund_ok = False
    if payment_info:
        refund_ok = await refund_star_payment(
            telegram_id=tid,
            payment_id=payment_info[4],
            stars_amount=stars,
        )

    # Уведомляем пользователя
    try:
        if refund_ok:
            await notify_user(tid, f"ℹ️ Ваша подписка отменена администратором. Возврат {stars} ⭐ выполнен.")
        else:
            await notify_user(tid, "ℹ️ Ваша подписка отменена администратором. Возврат не удался — обратитесь в поддержку.")
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {tid}: {e}")

    # Активируем очередь, если есть
    queued = db.get_queued_subscription(tid)
    queue_text = ""
    if queued:
        q_plan_id = queued[3]
        q_plan = SUBSCRIPTION_PLANS.get(q_plan_id)
        if q_plan:
            new_key = db.create_license_key(user[0], q_plan_id, q_plan["duration_days"])
            new_end = (datetime.now() + timedelta(days=q_plan["duration_days"])).isoformat()
            db.update_user_subscription(tid, q_plan_id, new_key, new_end)
            db.save_payment(user_id=user[0], license_key=new_key, stars_amount=queued[4], telegram_payment_charge_id=queued[5])
            db.delete_queued_subscription(tid)
            queue_text = f"\n🎉 Подписка из очереди ({q_plan['name']}) активирована."

    refund_status = "✅ Возврат выполнен" if refund_ok else "⚠️ Возврат не удался"
    keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"✅ Подписка {uname} отменена.\n{refund_status}{queue_text}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Отмена без возврата (подтверждение) ---
@dp.callback_query(F.data.startswith("admin_cancel_norefund_"))
async def admin_cancel_norefund_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_cancel_norefund_", ""))
    user = db.get_user(tid)
    if not user or not user[3]:
        await callback.answer("❌ Нет активной подписки", show_alert=True)
        return
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, отменить БЕЗ возврата", callback_data=f"admin_confirm_norefund_{tid}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"admin_user_{tid}")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"⚠️ Отменить подписку {uname} <b>БЕЗ возврата</b>?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Отмена без возврата (выполнение) ---
@dp.callback_query(F.data.startswith("admin_confirm_norefund_"))
async def admin_confirm_norefund_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_confirm_norefund_", ""))
    user = db.get_user(tid)
    if not user or not user[3]:
        await callback.answer("❌ Нет активной подписки", show_alert=True)
        return
    license_key = user[3]
    uname = f"@{user[2]}" if user[2] else f"ID:{tid}"

    db.deactivate_license(license_key)
    db.clear_user_subscription(tid)

    try:
        await notify_user(tid, "ℹ️ Ваша подписка отменена администратором.")
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {tid}: {e}")

    # Активируем очередь
    queued = db.get_queued_subscription(tid)
    queue_text = ""
    if queued:
        q_plan_id = queued[3]
        q_plan = SUBSCRIPTION_PLANS.get(q_plan_id)
        if q_plan:
            new_key = db.create_license_key(user[0], q_plan_id, q_plan["duration_days"])
            new_end = (datetime.now() + timedelta(days=q_plan["duration_days"])).isoformat()
            db.update_user_subscription(tid, q_plan_id, new_key, new_end)
            db.save_payment(user_id=user[0], license_key=new_key, stars_amount=queued[4], telegram_payment_charge_id=queued[5])
            db.delete_queued_subscription(tid)
            queue_text = f"\n🎉 Подписка из очереди ({q_plan['name']}) активирована."

    keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"✅ Подписка {uname} отменена (без возврата).{queue_text}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

# --- Написать сообщение пользователю ---
@dp.callback_query(F.data.startswith("admin_msg_"))
async def admin_msg_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tid = int(callback.data.replace("admin_msg_", ""))
    await state.set_state(AdminStates.waiting_message_text)
    await state.update_data(target_telegram_id=tid)
    keyboard = [[InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_user_{tid}")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        f"✉️ Введите текст сообщения для пользователя (ID: {tid}):",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
    )

@dp.message(AdminStates.waiting_message_text)
async def admin_msg_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    tid = data.get("target_telegram_id")
    await state.clear()
    if not tid:
        await message.answer("❌ Ошибка: не найден ID пользователя.")
        return
    text = message.text.strip()
    user = db.get_user(tid)
    uname = f"@{user[2]}" if user and user[2] else f"ID:{tid}"
    try:
        await notify_user(tid, f"📩 Сообщение от администратора:\n\n{text}")
        keyboard = [[InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(f"✅ Сообщение отправлено {uname}", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение {tid}: {e}")
        await message.answer(f"❌ Не удалось отправить сообщение: {e}")

# ==================== КОНЕЦ АДМИН-ПАНЕЛИ ====================

async def main():
    logger.info("Бот запускается...")

    from web_auth import create_web_app, start_web_server, cleanup_expired_sessions
    web_app = create_web_app(db, bot, SERVER_API_ID, SERVER_API_HASH)
    web_app["web_base_url"] = WEB_AUTH_HOST
    runner = await start_web_server(web_app, WEB_AUTH_PORT)

    # Проверка Docker-образа при старте
    import docker_manager
    asyncio.create_task(docker_manager.build_image_if_needed())

    asyncio.create_task(send_reminder_notifications())
    asyncio.create_task(process_queued_subscriptions())
    asyncio.create_task(cleanup_expired_sessions())
    asyncio.create_task(docker_manager.monitor_containers(db, bot))

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())