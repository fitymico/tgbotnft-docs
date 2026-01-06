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

db = Database()
user_invoice_messages = {}
# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.create_user(message.from_user.id, message.from_user.username)
    
    keyboard = [
        [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")],
        [InlineKeyboardButton(text="🔑 Мой лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")],
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

        # Создаем или обновляем словарь для хранения ID инвойс-сообщений
        global user_invoice_messages
        user_invoice_messages[callback.from_user.id] = invoice_message.message_id

        declinekeyboard = [
            [InlineKeyboardButton(text="❌ Отмена покупки", callback_data="cancel_invoice")]
        ]
        reply_markup_decline = InlineKeyboardMarkup(inline_keyboard=declinekeyboard)
        
        await callback.message.edit_text(
            f"✅ Инвойс для тарифа <b>{plan['name']}</b> отправлен!\n\n"
            f"Проверьте чат с ботом, вам должно прийти платежное окно.",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup_decline
        )
        
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
        # Пытаемся удалить инвойс, если он есть
        if user_id in user_invoice_messages:
            invoice_message_id = user_invoice_messages[user_id]
            
            try:
                await bot.delete_message(
                    chat_id=user_id,
                    message_id=invoice_message_id
                )
                logger.info(f"Инвойс удален для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить инвойс: {e}")
                # Инвойс мог быть уже удален или оплачен
            
            # Убираем из словаря
            user_invoice_messages.pop(user_id, None)
        
        # Возвращаем к выбору тарифа
        await select_plan(callback)
        
    except Exception as e:
        logger.error(f"Ошибка при отмене инвойса: {e}")
        await callback.answer("❌ Ошибка при отмене", show_alert=True)

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
    
    # Проверяем, есть ли запрос на возврат за старую подписку
    refund_request = db.get_refund_request(user_id, user[3] if user[3] else "")
    if refund_request:
        refund_text = f"\n💰 <b>Возврат:</b> Запрошен возврат {refund_request[3]} ⭐ за предыдущую подписку."
        db.update_refund_status(refund_request[0], "approved")
    else:
        refund_text = ""
    
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
    
    if not user or not user[4]:  # subscription_plan
        await callback.answer("❌ У вас нет активной подписки", show_alert=True)
        return
    
    # Проверяем, активна ли еще лицензия
    active_license = db.get_active_license(callback.from_user.id)
    if not active_license:
        await callback.answer("❌ У вас нет активной подписки", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS.get(user[4])
    end_date = datetime.fromisoformat(user[5]) if user[5] else None
    
    if not end_date or end_date <= datetime.now():
        await callback.answer("❌ Ваша подписка уже истекла", show_alert=True)
        return
    
    # Рассчитываем остаток дней
    days_left = (end_date - datetime.now()).days
    if days_left <= 0:
        await callback.answer("❌ Подписка уже истекла", show_alert=True)
        return
    
    # Рассчитываем возврат (пропорционально оставшимся дням)
    total_days = plan["duration_days"]
    cost_per_day = plan["stars"] / total_days
    refund_amount = cost_per_day * days_left
    refund_amount = max(1, int(refund_amount + 0.5))  # Округление вверх и минимум 1
    refund_amount = min(refund_amount, plan["stars"])  # Не больше чем стоимость подписки
    
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, отменить подписку", callback_data=f"confirm_cancel_{user[3]}")],
        [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"⚠️ <b>Отмена подписки</b>\n\n"
        f"Вы уверены, что хотите отменить подписку?\n\n"
        f"📋 <b>Детали:</b>\n"
        f"• Тариф: {plan['name']}\n"
        f"• Осталось дней: {days_left}\n"
        f"• Возврат: {refund_amount} ⭐\n\n"
        f"После отмены:\n"
        f"• Доступ к сервису прекратится немедленно\n"
        f"• Возврат зачислится в течение 3-5 рабочих дней\n"
        f"• Вы сможете приобрести новую подписку позже",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel(callback: CallbackQuery):
    license_key = callback.data.replace("confirm_cancel_", "")
    
    # Получаем информацию о пользователе и подписке
    user = db.get_user(callback.from_user.id)
    if not user or user[3] != license_key:
        await callback.answer("❌ Ошибка: лицензия не найдена", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS.get(user[4])
    if not plan:
        await callback.answer("❌ Ошибка: план не найден", show_alert=True)
        return
    
    # Деактивируем лицензию
    db.deactivate_license(license_key)
    
    # Обновляем запись пользователя
    db.cursor.execute('''
        UPDATE users SET 
            subscription_plan = NULL, 
            license_key = NULL, 
            subscription_end_date = NULL
        WHERE telegram_id = ?
    ''', (callback.from_user.id,))
    db.conn.commit()
    
    # Создаем запрос на возврат
    end_date = datetime.fromisoformat(user[5]) if user[5] else datetime.now()
    days_left = (end_date - datetime.now()).days
    if days_left > 0:
        refund_amount = int((plan["stars"] * days_left) / plan["duration_days"])
        db.create_refund_request(callback.from_user.id, license_key, refund_amount)
        
        refund_text = f"\n💰 <b>Возврат:</b> {refund_amount} ⭐ будет зачислен в течение 3-5 рабочих дней."
    else:
        refund_text = ""
    
    keyboard = [
        [InlineKeyboardButton(text="📦 Купить новую подписку", callback_data="select_plan")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"✅ <b>Подписка успешно отменена!</b>\n\n"
        f"Тариф: {plan['name']}\n"
        f"Дата отмены: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"{refund_text}\n\n"
        f"Спасибо, что пользовались нашим сервисом!",
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
    
    # Проверяем активность лицензии
    active_license = db.get_active_license(callback.from_user.id)
    status = "✅ Активна" if active_license else "❌ Истекла/Отменена"
    
    license_info = f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{user[3]}</code>\n\n"
    license_info += f"📋 <b>Информация о подписке:</b>\n"
    license_info += f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
    license_info += f"• Статус: {status}\n"
    
    if end_date:
        license_info += f"• Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    # Добавляем информацию о возвратах, если есть
    refund_request = db.get_refund_request(callback.from_user.id, user[3])
    if refund_request:
        license_info += f"\n💰 <b>Ожидает возврата:</b> {refund_request[3]} ⭐\n"
    
    keyboard = [
        [InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_license")],
        [InlineKeyboardButton(text="⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        license_info,
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
        [InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup
    )

async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())