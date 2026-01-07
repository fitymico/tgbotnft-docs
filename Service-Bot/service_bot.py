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
user_invoice_data = {}
# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.create_user(message.from_user.id, message.from_user.username)
    
    keyboard = [
        [InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")],
        #[InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="")],
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
    
    db.save_payment(
        user_id=user[0],
        license_key=license_key,
        stars_amount=plan["stars"],
        telegram_payment_charge_id=payment.telegram_payment_charge_id
    )

    # Удаляем оба сообщения (инвойс и сообщение с кнопкой отмены)
    global user_invoice_data
    if user_id in user_invoice_data:
        invoice_data = user_invoice_data[user_id]
        
        # Удаляем инвойс
        try:
            await bot.delete_message(
                chat_id=user_id,
                message_id=invoice_data["invoice_id"]
            )
            logger.info(f"Инвойс удален после оплаты для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить инвойс после оплаты: {e}")
            # Инвойс мог быть уже удален автоматически
        
        # Удаляем сообщение с кнопкой отмены
        try:
            await bot.delete_message(
                chat_id=user_id,
                message_id=invoice_data["cancel_message_id"]
            )
            logger.info(f"Сообщение с кнопкой отмены удалено после оплаты для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с кнопкой отмены после оплаты: {e}")
        
        # Убираем из словаря
        user_invoice_data.pop(user_id, None)
    
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
    
    # Проверяем, использовал ли пользователь возврат ранее
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton(text="✅ Да, отменить подписку", callback_data=f"confirm_cancel_{user[3]}")],
        [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Если это админ - показываем особый текст
    if callback.from_user.id == ADMIN_ID:
        text = f"⚠️ <b>Отмена подписки (АДМИН)</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: <b>♾️ БЕЗГРАНИЧНО (режим админа)</b>\n\n"
        text += f"✅ <b>Особые условия:</b>\n"
        text += f"• Как администратор вы можете делать возвраты сколько угодно раз\n"
        text += f"• Эта отмена не будет засчитана как использованный возврат\n\n"
        text += f"Вы хотите отменить подписку?"
    elif has_used_refund:
        text = f"⚠️ <b>Отмена подписки</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: {'❌ Уже использован' if has_used_refund else '✅ Доступен'}\n\n"
        text += f"❌ <b>Возврат невозможен:</b>\n"
        text += f"• Вы уже использовали свой единственный возврат\n"
        text += f"• При отмене деньги не возвращаются\n"
        text += f"• Доступ к сервису прекратится немедленно\n\n"
        text += f"Вы все равно хотите отменить подписку?"
    else:
        text = f"⚠️ <b>Отмена подписки</b>\n\n"
        text += f"📋 <b>Детали подписки:</b>\n"
        text += f"• Тариф: {plan['name']}\n"
        text += f"• Осталось дней: {days_left}\n"
        text += f"• Полная стоимость: {plan['stars']} ⭐\n"
        text += f"• Статус возврата: {'❌ Уже использован' if has_used_refund else '✅ Доступен'}\n\n"
        text += f"✅ <b>Возврат возможен:</b>\n"
        text += f"• Полный возврат {plan['stars']} ⭐\n"
        text += f"• Только в течение 48 часов после оплаты\n"
        text += f"• ОДИН раз на аккаунт\n"
        text += f"После использования этого возврата,\n"
        text += f"следующие отмены будут БЕЗ возврата.\n\n"
        text += f"Хотите отменить с возвратом?"
    
    await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

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
    
    # Проверяем, использовал ли пользователь возврат ранее
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    
    # Получаем информацию о платеже
    payment_info = db.get_payment_by_license(license_key)
    
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
    
    # Рассчитываем оставшиеся дни для информации
    end_date = datetime.fromisoformat(user[5]) if user[5] else datetime.now()
    days_left = max(0, (end_date - datetime.now()).days)
    
    refund_info = ""
    refund_success = False
    
    # Пытаемся выполнить автоматический возврат, если доступно
    if callback.from_user.id == ADMIN_ID or (not has_used_refund and payment_info):
        try:
            # Показываем ожидание
            processing_msg = await callback.message.edit_text(
                "🔄 Выполняется возврат средств...",
                parse_mode=ParseMode.HTML
            )
            
            # Выполняем возврат
            refund_success = await refund_star_payment(
                telegram_id=callback.from_user.id,
                payment_id=payment_info[4],  # telegram_payment_charge_id
                stars_amount=plan["stars"]
            )
            
            if refund_success:
                refund_info = (
                    f"\n💰 <b>Возврат выполнен автоматически!</b>\n"
                    f"Сумма {plan['stars']} ⭐ возвращена на ваш счет.\n"
                )
                
                # Помечаем возврат как использованный (если не админ)
                if callback.from_user.id != ADMIN_ID:
                    db.mark_refund_used(callback.from_user.id)
            else:
                refund_info = (
                    f"\n⚠️ <b>Автоматический возврат не удался</b>\n"
                    f"Причина: прошло более 48 часов или другая ошибка.\n"
                    f"Свяжитесь с @Dimopster для ручного возврата.\n"
                    f"ID платежа: <code>{payment_info[4] if payment_info else 'не найден'}</code>\n\n"
                )
                
        except Exception as e:
            logger.error(f"Ошибка при автоматическом возврате: {e}")
            refund_info = (
                f"\n⚠️ <b>Ошибка автоматического возврата</b>\n"
                f"Причина: {str(e)[:100]}\n"
                f"Свяжитесь с @Dimopster для ручного возврата.\n\n"
            )
    
    elif not has_used_refund and not payment_info:
        # Если возврат доступен, но платеж не найден
        refund_info = (
            f"\n⚠️ <b>Информация о платеже не найдена</b>\n"
            f"Свяжитесь с @Dimopster для ручного возврата.\n"
            f"Укажите лицензию: <code>{license_key}</code>\n\n"
        )
        
        # Помечаем возврат как использованный (если не админ)
        if callback.from_user.id != ADMIN_ID:
            db.mark_refund_used(callback.from_user.id)
    
    elif not has_used_refund:
        # Если возврат доступен, но нет информации о платеже
        refund_info = (
            f"\n💰 <b>Возврат доступен!</b>\n"
            f"Полный возврат {plan['stars']} ⭐ возможен в течение 48 часов.\n\n"
            f"<b>Для возврата:</b>\n"
            f"1. Найдите ID платежа в настройках Telegram\n"
            f"2. Напишите @Dimopster с этим ID\n"
            f"3. Укажите ваш Telegram ID: <code>{callback.from_user.id}</code>\n\n"
            f"⚠️ <b>Внимание:</b> Это ваш ЕДИНСТВЕННЫЙ возврат.\n"
            f"Следующие отмены будут без возврата средств."
        )
        
        # Помечаем возврат как использованный (если не админ)
        if callback.from_user.id != ADMIN_ID:
            db.mark_refund_used(callback.from_user.id)
    
    else:
        # Если возврат уже использовался
        refund_info = (
            f"\n❌ <b>Возврат невозможен</b>\n"
            f"Вы уже использовали свой единственный возврат.\n"
            f"При следующих отменах деньги не возвращаются.\n\n"
            f"<b>Исключения:</b> Технические проблемы сервиса.\n"
            f"В этом случае обратитесь к @Dimopster."
        )
    
    keyboard = [
        [InlineKeyboardButton(text="📦 Купить новую подписку", callback_data="select_plan")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        f"✅ <b>Подписка успешно отменена!</b>\n\n"
        f"Тариф: {plan['name']}\n"
        f"Дата отмены: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"Осталось дней: {days_left}\n"
        f"{refund_info}"
        f"Спасибо, что пользовались нашим сервисом!",
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
    
    # Проверяем наличие активной подписки
    active_license = db.get_active_license(callback.from_user.id)
    
    if not active_license:
        keyboard = [[InlineKeyboardButton(text="📦 Выбрать тариф", callback_data="select_plan")]]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback.message.edit_text(
            "❌ У вас нет активной подписки.\n\n"
            "Выберите тариф для начала работы:",
            reply_markup=reply_markup
        )
        return
    
    # Используем данные из active_license вместо user
    plan = SUBSCRIPTION_PLANS.get(active_license[4])  # subscription_plan
    end_date = datetime.fromisoformat(active_license[5]) if active_license[5] else None
    license_key = active_license[3]  # license_key
    
    # Проверяем статус возврата
    has_used_refund = db.has_user_used_refund(callback.from_user.id)
    if callback.from_user.id == ADMIN_ID:
        refund_status = "👑 БЕЗГРАНИЧНО (режим админа)"
    else:
        refund_status = "❌ Использован" if has_used_refund else "✅ Доступен"
    
    license_info = f"🔑 <b>Ваш лицензионный ключ:</b>\n<code>{license_key}</code>\n\n"
    license_info += f"📋 <b>Информация о подписке:</b>\n"
    license_info += f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
    license_info += f"• Статус: ✅ Активна\n"
    license_info += f"• Стоимость: {plan['stars'] if plan else 0} ⭐\n"
    license_info += f"• Возврат: {refund_status} (один раз на аккаунт)\n"
    
    if end_date:
        license_info += f"• Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    license_info += f"\n<b>Условия возврата:</b>\n"
    
    if has_used_refund:
        license_info += f"• ❌ Вы уже использовали возврат\n"
        license_info += f"• ❌ Следующие отмены без возврата\n"
        license_info += f"• ✅ Исключение: технические проблемы\n"
    else:
        license_info += f"• ✅ ОДИН полный возврат на аккаунт\n"
        license_info += f"• ✅ Только в течение 48 часов после оплаты\n"
        license_info += f"• ❌ После использования возврата - новые возвраты недоступны\n"
    
    keyboard = [
        [InlineKeyboardButton(text="❌ Отменить подписку", callback_data="cancel_subscription")],
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
        #[InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="")],
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