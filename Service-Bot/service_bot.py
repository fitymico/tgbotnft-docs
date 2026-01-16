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
from dotenv import load_dotenv

load_dotenv()
ADMIN_ID = 981919884

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
                has_used_refund BOOLEAN DEFAULT 0,
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
        
        self.cursor.execute('''
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

        self.cursor.execute('''
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

        self.cursor.execute('''
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
        
        self.cursor.execute('''
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
        self.conn.commit()
    
    def save_payment(self, user_id, license_key, stars_amount, telegram_payment_charge_id):
        """Сохранить информацию о платеже"""
        self.cursor.execute('''
            INSERT INTO payments (payment_id, user_id, license_key, stars_amount, telegram_payment_charge_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_payment_charge_id, user_id, license_key, stars_amount, telegram_payment_charge_id))
        self.conn.commit()

    def get_payment_by_license(self, license_key):
        """Получить платеж по лицензии"""
        self.cursor.execute('''
            SELECT * FROM payments WHERE license_key = ? ORDER BY created_at DESC LIMIT 1
        ''', (license_key,))
        return self.cursor.fetchone()
    
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
    
    def has_user_used_refund(self, telegram_id):
        """Проверить, использовал ли пользователь возврат"""
        if telegram_id == ADMIN_ID:
            return False

        self.cursor.execute('''
            SELECT has_used_refund FROM users WHERE telegram_id = ?
        ''', (telegram_id,))
        result = self.cursor.fetchone()
        return result and result[0] == 1 if result else False
    
    def mark_refund_used(self, telegram_id):
        """Отметить, что пользователь использовал возврат"""
        if telegram_id == ADMIN_ID:
            return True

        self.cursor.execute('''
            UPDATE users SET has_used_refund = 1 WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def reset_refund_status(self, telegram_id):
        """Сбросить статус возврата (для администратора)"""
        self.cursor.execute('''
            UPDATE users SET has_used_refund = 0 WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_active_license(self, telegram_id):
        """Получить активную лицензию пользователя"""
        self.cursor.execute('''
            SELECT u.*, lk.expires_at 
            FROM users u
            LEFT JOIN license_keys lk ON u.license_key = lk.key
            WHERE u.telegram_id = ? AND lk.is_active = 1 AND lk.expires_at > datetime('now')
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
    
    def create_license_key(self, user_id, plan, duration_days):
        key = self.generate_license_key()
        expires_at = datetime.now() + timedelta(days=duration_days)
        
        self.cursor.execute('''
            INSERT INTO license_keys (key, user_id, plan, expires_at) VALUES (?, ?, ?, ?)
        ''', (key, user_id, plan, expires_at.isoformat()))
        self.conn.commit()

        self.create_reminders(user_id, key, expires_at)

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
    
    def deactivate_license(self, license_key):
        """Деактивировать лицензию"""
        self.cursor.execute('''
            UPDATE license_keys SET is_active = 0 WHERE key = ?
        ''', (license_key,))
        self.cursor.execute('''
            DELETE FROM reminders WHERE license_key = ?
        ''', (license_key,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def create_refund_request(self, user_id, license_key, stars_amount):
        """Создать запрос на возврат"""
        self.cursor.execute('''
            INSERT INTO refund_requests (user_id, license_key, stars_amount) 
            VALUES (?, ?, ?)
        ''', (user_id, license_key, stars_amount))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_refund_request(self, user_id, license_key):
        """Получить запрос на возврат"""
        self.cursor.execute('''
            SELECT * FROM refund_requests 
            WHERE user_id = ? AND license_key = ? AND status = 'pending'
        ''', (user_id, license_key))
        return self.cursor.fetchone()
    
    def update_refund_status(self, request_id, status):
        """Обновить статус возврата"""
        processed_at = datetime.now().isoformat()
        self.cursor.execute('''
            UPDATE refund_requests 
            SET status = ?, processed_at = ?
            WHERE request_id = ?
        ''', (status, processed_at, request_id))
        self.conn.commit()

    def create_reminders(self, user_id, license_key, expires_at):
        """Создать напоминания о продлении подписки"""
        three_days_before = expires_at - timedelta(days=3)
        one_hour_before = expires_at - timedelta(hours=1)

        self.cursor.execute('''
            DELETE FROM reminders WHERE license_key = ?
        ''', (license_key,))
        
        self.cursor.execute('''
            INSERT INTO reminders (user_id, license_key, reminder_type, scheduled_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, license_key, '3_days', three_days_before.isoformat()))
        
        self.cursor.execute('''
            INSERT INTO reminders (user_id, license_key, reminder_type, scheduled_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, license_key, '1_hour', one_hour_before.isoformat()))
        self.conn.commit()

    def get_due_reminders(self):
        """Получить напоминания, которые нужно отправить"""
        now = datetime.now().isoformat()
        
        self.cursor.execute('''
            SELECT r.*, u.telegram_id, u.username, lk.expires_at, u.subscription_plan
            FROM reminders r
            JOIN users u ON r.user_id = u.user_id
            JOIN license_keys lk ON r.license_key = lk.key
            WHERE r.sent = 0 AND r.scheduled_time <= ? AND lk.is_active = 1
        ''', (now,))
        
        reminders = self.cursor.fetchall()
        return reminders
    
    def mark_reminder_sent(self, reminder_id):
        sent_at = datetime.now().isoformat()
        
        self.cursor.execute('''
            UPDATE reminders SET sent = 1, sent_at = ? WHERE reminder_id = ?
        ''', (sent_at, reminder_id))
        self.conn.commit()
    
    def save_queued_subscription(self, user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id):
        self.cursor.execute('''
            INSERT INTO queued_subscriptions (user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, telegram_id, plan, stars_amount, telegram_payment_charge_id))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_queued_subscription(self, telegram_id):
        self.cursor.execute('''
            SELECT * FROM queued_subscriptions WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (telegram_id,))
        return self.cursor.fetchone()
    
    def delete_queued_subscription(self, telegram_id):
        self.cursor.execute('''
            DELETE FROM queued_subscriptions WHERE telegram_id = ?
        ''', (telegram_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_expired_subscriptions_with_queue(self):
        now = datetime.now().isoformat()
        self.cursor.execute('''
            SELECT u.user_id, u.telegram_id, u.license_key, qs.*
            FROM users u
            JOIN queued_subscriptions qs ON u.telegram_id = qs.telegram_id
            WHERE u.subscription_end_date < ? AND u.license_key IS NOT NULL
        ''', (now,))
        return self.cursor.fetchall()

db = Database()
user_invoice_data = {}
# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.create_user(message.from_user.id, message.from_user.username)
    
    active_license = db.get_active_license(message.from_user.id)
    
    keyboard = []
    if active_license:
        keyboard.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")])
    else:
        keyboard.append([InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")])
    
    keyboard.append([InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")])
    
    if active_license:
        keyboard.append([InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")])
    
    keyboard.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    
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
    await bot.answer_pre_checkout_query(query.id, ok=True)

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
    
    keyboard = [
        [InlineKeyboardButton(text="🔑 Показать лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        f"✅ <b>Оплата успешно завершена!</b>\n\n"
        f"📋 <b>Детали подписки:</b>\n"
        f"• Тариф: {plan['name']}\n"
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
        keyboard = [
            [InlineKeyboardButton(text="✅ Да, отменить", callback_data="cancel_queued")],
            [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            f"⚠️ <b>Отмена подписки в очереди</b>\n\n"
            f"📋 <b>Подписка в очереди:</b>\n"
            f"• Тариф: {queued_plan.get('name', 'Неизвестно')}\n"
            f"• Стоимость: {queued[4]} ⭐\n\n"
            f"При отмене будет выполнен возврат средств.",
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
    
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, отменить подписку", callback_data="cancel_current")],
        [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if callback.from_user.id == ADMIN_ID:
        text = f"⚠️ <b>Отмена подписки (АДМИН)</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: <b>♾️ БЕЗГРАНИЧНО (режим админа)</b>\n\n"
        text += f"Вы хотите отменить подписку?"
    elif has_used_refund:
        text = f"⚠️ <b>Отмена подписки</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: ❌ Уже использован\n\n"
        text += f"❌ <b>Возврат невозможен:</b>\n"
        text += f"• Вы уже использовали свой единственный возврат\n"
        text += f"• При отмене деньги не возвращаются\n\n"
        text += f"Вы все равно хотите отменить подписку?"
    else:
        text = f"⚠️ <b>Отмена подписки</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: ✅ Доступен\n\n"
        text += f"✅ <b>Возврат возможен:</b>\n"
        text += f"• Полный возврат {plan['stars']} ⭐\n"
        text += f"• Только в течение 48 часов после оплаты\n"
        text += f"• ОДИН раз на аккаунт\n\n"
        text += f"Хотите отменить с возвратом?"
    
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
    
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    payment_info = db.get_payment_by_license(license_key)
    
    db.deactivate_license(license_key)
    
    db.cursor.execute('''
        UPDATE users SET 
            subscription_plan = NULL, 
            license_key = NULL, 
            subscription_end_date = NULL
        WHERE telegram_id = ?
    ''', (callback.from_user.id,))
    db.conn.commit()
    
    end_date = datetime.fromisoformat(user[5]) if user[5] else datetime.now()
    days_left = max(0, (end_date - datetime.now()).days)
    
    refund_info = ""
    
    if callback.from_user.id == ADMIN_ID or (not has_used_refund and payment_info):
        try:
            await callback.message.edit_text("🔄 Выполняется возврат средств...", parse_mode=ParseMode.HTML)
            
            refund_success = await refund_star_payment(
                telegram_id=callback.from_user.id,
                payment_id=payment_info[4],
                stars_amount=plan["stars"]
            )
            
            if refund_success:
                refund_info = f"\n💰 <b>Возврат выполнен!</b> {plan['stars']} ⭐ возвращено.\n"
                if callback.from_user.id != ADMIN_ID:
                    db.mark_refund_used(callback.from_user.id)
            else:
                refund_info = f"\n⚠️ <b>Автоматический возврат не удался.</b>\nСвяжитесь с @Dimopster.\n"
        except Exception as e:
            logger.error(f"Ошибка при возврате: {e}")
            refund_info = f"\n⚠️ <b>Ошибка возврата.</b> Свяжитесь с @Dimopster.\n"
    elif has_used_refund:
        refund_info = "\n❌ Возврат недоступен (уже использован).\n"
    
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
    
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    
    db.delete_queued_subscription(callback.from_user.id)
    
    refund_info = ""
    
    if callback.from_user.id == ADMIN_ID or (not has_used_refund and payment_id):
        try:
            await callback.message.edit_text("🔄 Выполняется возврат средств...", parse_mode=ParseMode.HTML)
            
            refund_success = await refund_star_payment(
                telegram_id=callback.from_user.id,
                payment_id=payment_id,
                stars_amount=stars_amount
            )
            
            if refund_success:
                refund_info = f"\n💰 <b>Возврат выполнен!</b> {stars_amount} ⭐ возвращено.\n"
                if callback.from_user.id != ADMIN_ID:
                    db.mark_refund_used(callback.from_user.id)
            else:
                refund_info = f"\n⚠️ <b>Автоматический возврат не удался.</b>\nСвяжитесь с @Dimopster.\nID платежа: <code>{payment_id}</code>\n"
        except Exception as e:
            logger.error(f"Ошибка при возврате очереди: {e}")
            refund_info = f"\n⚠️ <b>Ошибка возврата.</b> Свяжитесь с @Dimopster.\n"
    elif has_used_refund:
        refund_info = "\n❌ Возврат недоступен (уже использован ранее).\n"
    
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
                
                keyboard = [
                    [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")],
                    [InlineKeyboardButton(text="🔑 Проверить лицензию", callback_data="my_license")]
                ]
                reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
                
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=message_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                    
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
    if message.from_user.id != ADMIN_ID:
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
                
                # Обновляем запись пользователя (очищаем данные о подписке)
                db.cursor.execute('''
                    UPDATE users SET 
                        subscription_plan = NULL, 
                        license_key = NULL, 
                        subscription_end_date = NULL
                    WHERE telegram_id = ?
                ''', (telegram_id,))
                db.conn.commit()
                
                # Ищем запрос на возврат для этого пользователя
                db.cursor.execute('''
                    SELECT * FROM refund_requests 
                    WHERE user_id = ? AND license_key = ? AND status = 'pending'
                ''', (telegram_id, user[3]))
                refund_request = db.cursor.fetchone()
                
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

            keyboard = [
                [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            
            # Уведомляем пользователя о возврате
            try:
                await bot.send_message(
                    telegram_id,
                    f"✅ <b>Ваш возврат обработан!</b>\n\n"
                    f"Сумма: {stars_amount or 'полная'} ⭐\n"
                    f"Статус: Возврат успешно выполнен\n"
                    f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"Средства возвращены на ваш счет.\n"
                    f"Ваша подписка отменена.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
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
        keyboard = [[InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")]]
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
        
        has_used_refund = db.has_user_used_refund(callback.from_user.id)
        if callback.from_user.id == ADMIN_ID:
            refund_status = "👑 БЕЗГРАНИЧНО (режим админа)"
        else:
            refund_status = "❌ Использован" if has_used_refund else "✅ Доступен"
        
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
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда только для администратора")
        return
    
    active_license = db.get_active_license(message.from_user.id)
    if not active_license:
        await message.answer("❌ У вас нет активной подписки для сброса")
        return
    
    queued = db.get_queued_subscription(message.from_user.id)
    
    db.cursor.execute('''
        UPDATE users SET subscription_end_date = ? WHERE telegram_id = ?
    ''', ('2020-01-01T00:00:00', message.from_user.id))
    
    db.cursor.execute('''
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    if message.from_user.id != ADMIN_ID:
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
    active_license = db.get_active_license(callback.from_user.id)
    
    keyboard = []
    if active_license:
        keyboard.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")])
    else:
        keyboard.append([InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")])
    
    keyboard.append([InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")])
    
    if active_license:
        keyboard.append([InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")])
    
    keyboard.append([InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup
    )

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
                    keyboard = [
                        [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
                        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
                    ]
                    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
                    
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=f"🎉 <b>Подписка автоматически продлена!</b>\n\n"
                             f"📋 <b>Детали:</b>\n"
                             f"• Тариф: {plan['name']}\n"
                             f"• Срок: {plan['duration_days']} дней\n"
                             f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
                             f"Новый лицензионный ключ сгенерирован.",
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                    logger.info(f"Активирована подписка из очереди для {telegram_id}")
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя {telegram_id}: {e}")
            
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в process_queued_subscriptions: {e}")
            await asyncio.sleep(60)

async def main():
    logger.info("Бот запускается...")
    asyncio.create_task(send_reminder_notifications())
    asyncio.create_task(process_queued_subscriptions())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())