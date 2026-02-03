# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).parent.resolve()
else:
    PROJECT_ROOT = Path(__file__).parent.parent.resolve()

load_dotenv(PROJECT_ROOT / ".env")

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    BOT_TOKEN, ADMIN_ID, LICENSE_KEY,
    API_ID, API_HASH,
    UDP_LISTEN_HOST, UDP_LISTEN_PORT, STATUS_FILE, LOG_FILE,
    load_session, save_session,
)
from Message_Bot.distribution import validate_distribution
from Message_Bot.gift_buyer import GiftBuyer
from Message_Bot.udp_listener import UdpListener

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== Initialization ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_states = {}

# GiftBuyer and UdpListener — created after session is available
buyer: GiftBuyer | None = None
udp: UdpListener | None = None

# Telethon client used during /auth flow (not serializable, so module-level)
_auth_client = None


# ================== Session & buyer init ==================
async def init_buyer():
    """Initialize GiftBuyer and UdpListener with current session."""
    global buyer, udp

    session = load_session()
    if not session:
        return False

    buyer = GiftBuyer(
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session,
        status_file=STATUS_FILE,
        log_file=LOG_FILE,
    )
    await buyer.connect()

    udp = UdpListener(
        license_key=LICENSE_KEY,
        host=UDP_LISTEN_HOST,
        port=UDP_LISTEN_PORT,
    )
    udp.on_gifts(buyer.handle_new_gifts)
    await udp.start()

    logger.info("Buyer and UDP listener started")
    return True


# ================== Auth flow ==================
async def cmd_auth(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    if load_session():
        await message.answer(
            "Сессия уже существует. Бот авторизован.\n"
            "Для повторной авторизации удалите файл data/session.string и перезапустите."
        )
        return

    await message.answer("Введите номер телефона (в формате +7XXXXXXXXXX):")
    user_states[message.from_user.id] = "auth_phone"


async def handle_auth_phone(message: types.Message):
    global _auth_client

    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("Номер должен начинаться с +. Попробуйте снова:")
        return

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    _auth_client = TelegramClient(StringSession(), API_ID, API_HASH)
    await _auth_client.connect()

    try:
        await _auth_client.send_code_request(phone)
        user_states[message.from_user.id] = "auth_code"
        await message.answer(
            "Код отправлен в Telegram. Введите код подтверждения:\n"
            "(если код 12345, отправьте как 1 2 3 4 5 или 1-2-3-4-5 чтобы Telegram не заблокировал)"
        )
    except Exception as e:
        await _auth_client.disconnect()
        _auth_client = None
        user_states.pop(message.from_user.id, None)
        await message.answer(f"Ошибка отправки кода: {e}")


async def handle_auth_code(message: types.Message):
    global _auth_client

    # Parse code — allow spaces, dashes
    code = message.text.strip().replace(" ", "").replace("-", "")

    try:
        await _auth_client.sign_in(code=code)
    except Exception as e:
        err_name = type(e).__name__
        if "SessionPasswordNeeded" in err_name:
            user_states[message.from_user.id] = "auth_2fa"
            await message.answer("Требуется пароль двухфакторной аутентификации. Введите пароль:")
            return
        await _auth_client.disconnect()
        _auth_client = None
        user_states.pop(message.from_user.id, None)
        await message.answer(f"Ошибка авторизации: {e}")
        return

    await _finish_auth(message)


async def handle_auth_2fa(message: types.Message):
    global _auth_client

    password = message.text.strip()

    try:
        await _auth_client.sign_in(password=password)
    except Exception as e:
        await _auth_client.disconnect()
        _auth_client = None
        user_states.pop(message.from_user.id, None)
        await message.answer(f"Ошибка 2FA: {e}")
        return

    await _finish_auth(message)


async def _finish_auth(message: types.Message):
    global _auth_client

    session_str = _auth_client.session.save()
    await _auth_client.disconnect()
    _auth_client = None
    user_states.pop(message.from_user.id, None)

    save_session(session_str)

    ok = await init_buyer()
    if ok:
        await message.answer(
            "Авторизация успешна! Бот готов к работе.\n"
            "Используйте /start для открытия панели управления."
        )
    else:
        await message.answer("Авторизация сохранена, но не удалось запустить покупатель. Перезапустите бот.")


# ================== Status helpers ==================
def read_status() -> dict:
    if buyer:
        return buyer.read_status()
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_status(data: dict):
    if buyer:
        buyer.write_status(data)
        return
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATUS_FILE)


def ensure_status():
    if not os.path.exists(STATUS_FILE):
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        write_status({
            "isActive": False,
            "distribution": "",
            "iterations": 0,
            "delay": 1.0,
        })


# ================== Keyboards ==================
def make_kb_grid_minor():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="⭐ Распределение звезд ⭐")],
            [types.KeyboardButton(text="📋 Лог-файл покупок за все время 📋")],
            [types.KeyboardButton(text="⬅️ Назад ⬅️")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def make_kb_grid_main():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔧 Настройки 🔧"), types.KeyboardButton(text="💰 Начать 💰")],
            [types.KeyboardButton(text="📊 Статус 📊"), types.KeyboardButton(text="🛑 Остановить 🛑")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ================== Handlers ==================
async def handle_text_after_buttons(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    text = message.text.strip()
    if not text:
        await message.answer("Пустой ввод. Попробуйте снова.")
        return

    if text == "⬅️ Назад ⬅️":
        user_states.pop(user_id, None)
        await message.answer("Возврат в главное меню 👇", reply_markup=make_kb_grid_main())
        return

    state = user_states.get(user_id)
    if not state:
        return

    if state == "awaiting_distribution":
        is_valid, error_msg = validate_distribution(text)
        if not is_valid:
            await message.answer(f"❌ {error_msg}\n\nПопробуйте снова:")
            return

        status = read_status()
        status["distribution"] = text
        write_status(status)
        user_states.pop(user_id, None)
        await message.answer("✅ Распределение звёзд сохранено!", reply_markup=make_kb_grid_minor())

    elif state == "awaiting_iterations":
        try:
            val = int(text)
        except ValueError:
            await message.answer("❌ Введите число, например: 10")
            return
        status = read_status()
        status["iterations"] = val
        write_status(status)
        user_states.pop(user_id, None)
        await message.answer(f"✅ Количество итераций сохранено: {text}", reply_markup=make_kb_grid_minor())

    elif state == "awaiting_delay":
        try:
            val = float(text)
        except ValueError:
            await message.answer("❌ Введите число, например: 1.5")
            return
        status = read_status()
        status["delay"] = val
        write_status(status)
        user_states.pop(user_id, None)
        await message.answer(f"✅ Задержка сохранена: {text} сек", reply_markup=make_kb_grid_minor())


async def handle_back_button(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    text = message.text.strip()
    if text == "⬅️ Назад ⬅️":
        user_states.pop(user_id, None)
        await message.answer("Возврат в главное меню 👇", reply_markup=make_kb_grid_main())
        return True
    return False


async def handle_settings_buttons(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return False

    text = message.text.strip()

    if text == "🔧 Настройки 🔧":
        await message.answer("Открываю меню настроек 👇", reply_markup=make_kb_grid_minor())
        return True

    elif text == "📊 Статус 📊":
        status = read_status()
        is_active = status.get("isActive", False)
        distribution = status.get("distribution", "")
        has_session = bool(load_session())

        balance = 0
        if buyer and buyer._client and buyer._client.is_connected():
            try:
                from Message_Bot.telegram_api import get_stars_balance
                balance = await get_stars_balance(buyer._client)
            except Exception:
                pass

        auth_line = "✅ авторизован" if has_session else "❌ не авторизован (/auth)"
        reply = (
            f"📈 Статус бота:\n"
            f"• Сессия: {auth_line}\n"
            f"• Активен: {'✅' if is_active else '❌'}\n"
            f"• Баланс: {balance} ⭐\n"
            f"• Текущее распределение звезд:\n{distribution or '— не задано —'}"
        )
        await message.answer(reply)
        return True

    elif text == "💰 Начать 💰":
        if not load_session():
            await message.answer("❌ Сначала авторизуйтесь: /auth")
            return True
        status = read_status()
        if not status.get("distribution"):
            await message.answer("❌ Сначала задайте распределение звёзд!")
            return True
        status["isActive"] = True
        write_status(status)
        await message.answer("💰 Сканирование подарков активировано! Ожидаем данные от сервера...")
        return True

    elif text == "🛑 Остановить 🛑":
        status = read_status()
        status["isActive"] = False
        write_status(status)
        await message.answer("🛑 Сканирование подарков остановлено!")
        return True

    elif text == "⭐ Распределение звезд ⭐":
        await message.answer(
            "Введите распределение (по строкам: условие_цены количество), например:\n"
            "<1000 10\n>=1000 и <5000 5\n\n"
            "Форматы условий:\n"
            "<1000   (меньше 1000)\n"
            "<=1000  (меньше или равно 1000)\n"
            ">1000   (больше 1000)\n"
            ">=1000  (больше или равно 1000)\n"
            "=1000   (равно 1000)\n"
            ">=1000 и <5000 (диапазон от 1000 до 5000; [1000,5000) ])\n\n"
            "Или нажмите '⬅️ Назад ⬅️' для возврата"
        )
        user_states[message.from_user.id] = "awaiting_distribution"
        return True

    elif text == "📋 Лог-файл покупок за все время 📋":
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as f:
                content = f.read()
            if content.strip():
                await message.answer_document(
                    types.BufferedInputFile(content, filename="bot_log.txt"),
                    caption="📋 Лог-файл покупок"
                )
            else:
                await message.answer("📭 Лог-файл пока пуст.")
        else:
            await message.answer("📭 Лог-файл пока не создан.")
        return True

    return False


async def controlUser(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    ensure_status()

    if not load_session():
        await message.answer(
            "Бот запущен, но требуется авторизация Telegram-аккаунта.\n"
            "Отправьте /auth для начала авторизации.",
        )
        return

    await message.answer(
        "🎛️ Перед тобой панель управления ботом\nВыбери нужный раздел: 👇",
        reply_markup=make_kb_grid_main(),
    )


# ================== Predicates ==================
def is_auth_state(message: types.Message) -> bool:
    uid = message.from_user.id if message.from_user else None
    if not uid:
        return False
    return user_states.get(uid, "").startswith("auth_")


def awaiting_input_predicate(message: types.Message) -> bool:
    uid = message.from_user.id if message.from_user else None
    if not uid or uid not in user_states:
        return False
    return user_states[uid] in ("awaiting_distribution", "awaiting_iterations", "awaiting_delay")


def is_back_button_predicate(message: types.Message) -> bool:
    return message.text and message.text.strip() == "⬅️ Назад ⬅️"


def is_settings_button_predicate(message: types.Message) -> bool:
    text = message.text.strip() if message.text else ""
    return text in [
        "🔧 Настройки 🔧", "💰 Начать 💰", "📊 Статус 📊", "🛑 Остановить 🛑",
        "⭐ Распределение звезд ⭐", "📋 Лог-файл покупок за все время 📋"
    ]


# ================== Auth state router ==================
async def auth_router(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    state = user_states.get(message.from_user.id)
    if state == "auth_phone":
        await handle_auth_phone(message)
    elif state == "auth_code":
        await handle_auth_code(message)
    elif state == "auth_2fa":
        await handle_auth_2fa(message)


# ================== Register handlers ==================
dp.message.register(controlUser, Command(commands=["start"]))
dp.message.register(cmd_auth, Command(commands=["auth"]))
dp.message.register(auth_router, is_auth_state)
dp.message.register(handle_back_button, is_back_button_predicate)
dp.message.register(handle_text_after_buttons, awaiting_input_predicate)
dp.message.register(handle_settings_buttons, is_settings_button_predicate)


# ================== Main ==================
async def main():
    ensure_status()

    session = load_session()
    if session:
        await init_buyer()
        logger.info("Session found, buyer started")
    else:
        logger.info("No session — waiting for /auth from user")

    try:
        await dp.start_polling(bot)
    finally:
        if udp:
            udp.stop()
        if buyer:
            await buyer.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
