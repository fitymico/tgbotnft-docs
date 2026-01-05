import sqlite3
import logging
import uuid
import hashlib
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8547506087:AAE4nn8YmZVpwA5IU3nHU311xrFnKEyCpBw"

SUBSCRIPTION_PLANS = {
    "basic": {"name": "SELF-HOST", "price": 109, "duration_days": 30, "stars": 109},
    "pro": {"name": "HOSTING", "price": 169, "duration_days": 30, "stars": 169},
    "premium": {"name": "HOSTING-PRO", "price": 249, "duration_days": 30, "stars": 249},
    "basic-year": {"name": "SELF-HOST", "price": 1090, "duration_days": 365, "stars": 1090},
    "pro-year": {"name": "HOSTING", "price": 1690, "duration_days": 365, "stars": 1690},
    "premium-year": {"name": "HOSTING-PRO", "price": 2490, "duration_days": 365, "stars": 2490}
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user(user.id, user.username)
    
    keyboard = [
        [InlineKeyboardButton("📦 Выбрать тариф", callback_data="select_plan")],
        [InlineKeyboardButton("🔑 Мой лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data="bot_settings")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Добро пожаловать в Service Bot!\n\n"
        f"Этот бот поможет вам настроить вашего собственного Telegram бота "
        f"с функциями покупки подарков за звезды.\n\n"
        f"Выберите действие ниже:",
        reply_markup=reply_markup
    )

async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    
    # Месячные подписки
    keyboard.append([InlineKeyboardButton("📅 Месячные подписки", callback_data="monthly_plans")])
    
    # Годовые подписки
    keyboard.append([InlineKeyboardButton("📅 Годовые подписки", callback_data="yearly_plans")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 Выберите тип подписки:\n\n"
        "💰 **Годовые подписки** - экономия 2 месяца бесплатно!\n"
        "📅 **Месячные подписки** - гибкий платежный план\n\n"
        "Выберите тип подписки:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_monthly_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    monthly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if not k.endswith('-year')}
    
    for plan_id, plan_info in monthly_plans.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{plan_info['name']} - {plan_info['stars']} ⭐/мес",
                callback_data=f"buy_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="select_plan")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 **Месячные подписки**\n\n"
        "Выберите подходящий тариф:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_yearly_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    yearly_plans = {k: v for k, v in SUBSCRIPTION_PLANS.items() if k.endswith('-year')}
    
    for plan_id, plan_info in yearly_plans.items():
        monthly_equivalent = plan_info['stars'] // 12
        savings = plan_info['stars'] - (monthly_equivalent * 12)
        
        keyboard.append([
            InlineKeyboardButton(
                f"{plan_info['name']} - {plan_info['stars']} ⭐/год",
                callback_data=f"buy_plan_{plan_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="select_plan")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📆 **Годовые подписки**\n\n"
        "💰 Экономия 2 месяца бесплатно!\n"
        "Выберите подходящий тариф:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    plan_id = query.data.replace("buy_plan_", "")
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    
    if not plan:
        await query.edit_message_text("❌ Неверный тарифный план")
        return
    
    invoice_payload = f"plan_{plan_id}_{uuid.uuid4().hex[:8]}"
    
    await query.bot.send_invoice(
        chat_id=query.from_user.id,
        title=f"Подписка {plan['name']}",
        description=f"Доступ к Service Bot на {plan['duration_days']} дней",
        payload=invoice_payload,
        provider_token="",
        currency="XTR",
        prices=[{"label": f"Подписка {plan['name']}", "amount": plan["stars"] * 100}]
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    
    payload_parts = message.successful_payment.invoice_payload.split("_")
    plan_id = payload_parts[1]
    
    plan = SUBSCRIPTION_PLANS.get(plan_id)
    if not plan:
        await message.reply_text("❌ Ошибка обработки платежа")
        return
    
    user = db.get_user(user_id)
    license_key = db.create_license_key(user[0], plan_id, plan["duration_days"])
    end_date = (datetime.now() + timedelta(days=plan["duration_days"])).isoformat()
    
    db.update_user_subscription(user_id, plan_id, license_key, end_date)
    
    keyboard = [
        [InlineKeyboardButton("🔑 Показать лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton("⚙️ Настроить бота", callback_data="bot_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        f"✅ **Оплата успешно завершена!**\n\n"
        f"📋 Детали подписки:\n"
        f"• Тариф: {plan['name']}\n"
        f"• Срок: {plan['duration_days']} дней\n"
        f"• Действует до: {datetime.fromisoformat(end_date).strftime('%d.%m.%Y')}\n\n"
        f"Ваш лицензионный ключ сгенерирован!\n"
        f"Теперь вы можете настроить вашего бота.",
        reply_markup=reply_markup
    )

async def my_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(query.from_user.id)
    
    if not user or not user[4]:  # subscription_plan
        await query.edit_message_text(
            "❌ У вас нет активной подписки.\n\n"
            "Выберите тариф для начала работы:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Выбрать тариф", callback_data="select_plan")
            ]])
        )
        return
    
    plan = SUBSCRIPTION_PLANS.get(user[4])
    end_date = datetime.fromisoformat(user[5]) if user[5] else None
    
    license_info = f"🔑 **Ваш лицензионный ключ:**\n`{user[3]}`\n\n"
    license_info += f"📋 **Информация о подписке:**\n"
    license_info += f"• Тариф: {plan['name'] if plan else 'Неизвестно'}\n"
    license_info += f"• Статус: {'Активна' if end_date and end_date > datetime.now() else 'Истекла'}\n"
    
    if end_date:
        license_info += f"• Действует до: {end_date.strftime('%d.%m.%Y %H:%M')}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="my_license")],
        [InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(license_info, reply_markup=reply_markup)

async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(query.from_user.id)
    
    if not user or not user[4]:
        await query.edit_message_text(
            "❌ Сначала выберите тарифный план!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 Выбрать тариф", callback_data="select_plan")
            ]])
        )
        return
    
    config_status = "✅ Настроено" if user[6] and user[7] and user[8] else "❌ Не настроено"
    
    keyboard = [
        [InlineKeyboardButton(f"🤖 Токен бота: {'✅' if user[6] else '❌'}", callback_data="set_bot_token")],
        [InlineKeyboardButton(f"🔑 API ID: {'✅' if user[7] else '❌'}", callback_data="set_api_id")],
        [InlineKeyboardButton(f"🔐 API Hash: {'✅' if user[8] else '❌'}", callback_data="set_api_hash")],
        [InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚙️ **Настройки бота**\n\n"
        f"Статус конфигурации: {config_status}\n\n"
        f"Для полноценной работы бота необходимо настроить:\n"
        f"• Токен вашего бота (от @BotFather)\n"
        f"• API ID и API Hash (от my.telegram.org)\n\n"
        f"Выберите параметр для настройки:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def set_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🤖 **Настройка токена бота**\n\n"
        "1. Перейдите к @BotFather\n"
        "2. Отправьте команду /newbot\n"
        "3. Создайте бота и скопируйте токен\n"
        "4. Отправьте токен в этот чат\n\n"
        "Токен выглядит так: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789`\n\n"
        "Отправьте токен сообщением в этот чат:",
        parse_mode='Markdown'
    )
    
    context.user_data['awaiting'] = 'bot_token'

async def set_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔑 **Настройка API ID**\n\n"
        "1. Перейдите на my.telegram.org\n"
        "2. Войдите под своим номером телефона\n"
        "3. Перейдите в API development tools\n"
        "4. Скопируйте App api_id\n\n"
        "Отправьте API ID сообщением в этот чат:",
        parse_mode='Markdown'
    )
    
    context.user_data['awaiting'] = 'api_id'

async def set_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔐 **Настройка API Hash**\n\n"
        "1. Перейдите на my.telegram.org\n"
        "2. Войдите под своим номером телефона\n"
        "3. Перейдите в API development tools\n"
        "4. Скопируйте App api_hash\n\n"
        "Отправьте API Hash сообщением в этот чат:",
        parse_mode='Markdown'
    )
    
    context.user_data['awaiting'] = 'api_hash'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.from_user.id
    message_text = update.message.text
    awaiting = context.user_data.get('awaiting')
    
    if awaiting == 'bot_token':
        if len(message_text.split(':')) == 2 and message_text.replace(':', '').replace('_', '').isalnum():
            db.update_user_bot_config(user_id, message_text, None, None)
            await update.message.reply_text("✅ Токен бота сохранен!")
            del context.user_data['awaiting']
        else:
            await update.message.reply_text("❌ Неверный формат токена. Попробуйте еще раз.")
    
    elif awaiting == 'api_id':
        if message_text.isdigit():
            user = db.get_user(user_id)
            db.update_user_bot_config(user_id, user[6], message_text, user[8])
            await update.message.reply_text("✅ API ID сохранен!")
            del context.user_data['awaiting']
        else:
            await update.message.reply_text("❌ API ID должен содержать только цифры. Попробуйте еще раз.")
    
    elif awaiting == 'api_hash':
        if len(message_text) == 32 and message_text.isalnum():
            user = db.get_user(user_id)
            db.update_user_bot_config(user_id, user[6], user[7], message_text)
            await update.message.reply_text("✅ API Hash сохранен!")
            del context.user_data['awaiting']
        else:
            await update.message.reply_text("❌ Неверный формат API Hash. Попробуйте еще раз.")

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📦 Выбрать тариф", callback_data="select_plan")],
        [InlineKeyboardButton("🔑 Мой лицензионный ключ", callback_data="my_license")],
        [InlineKeyboardButton("⚙️ Настройки бота", callback_data="bot_settings")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 Добро пожаловать в Service Bot!\n\n"
        "Выберите действие ниже:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    
    help_text = """
ℹ️ Помощь - Service Bot

📄 **Отправляю файл с инструкциями...**
Прочитайте файл README.md для получения полной информации о настройке бота.

Поддержка:
Если у вас возникли вопросы, свяжитесь с @Dimopster.
    """
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад ⬅️", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сначала отправляем текст
    if query:
        await query.edit_message_text(help_text, reply_markup=reply_markup)
        # Отправляем файл в ответ на callback
        with open("README.md", "rb") as file:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file,
                filename="README_инструкция.md",
                caption="📖 Полная инструкция по настройке бота"
            )
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup)
        # Отправляем файл в ответ на команду
        with open("README.md", "rb") as file:
            await update.message.reply_document(
                document=file,
                filename="README_инструкция.md",
                caption="📖 Полная инструкция по настройке бота"
            )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(select_plan, pattern="^select_plan$"))
    application.add_handler(CallbackQueryHandler(show_monthly_plans, pattern="^monthly_plans$"))
    application.add_handler(CallbackQueryHandler(show_yearly_plans, pattern="^yearly_plans$"))
    application.add_handler(CallbackQueryHandler(buy_plan, pattern="^buy_plan_"))
    application.add_handler(CallbackQueryHandler(my_license, pattern="^my_license$"))
    application.add_handler(CallbackQueryHandler(bot_settings, pattern="^bot_settings$"))
    application.add_handler(CallbackQueryHandler(set_bot_token, pattern="^set_bot_token$"))
    application.add_handler(CallbackQueryHandler(set_api_id, pattern="^set_api_id$"))
    application.add_handler(CallbackQueryHandler(set_api_hash, pattern="^set_api_hash$"))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    print("Service Bot запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()