# -*- coding: utf-8 -*-
import asyncio
import json
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
    API_ID, API_HASH, SESSION_STRING,
    UDP_LISTEN_HOST, UDP_LISTEN_PORT,
    STATUS_FILE, LOG_FILE,
)
from Message_Bot.distribution import validate_distribution
from Message_Bot.gift_buyer import GiftBuyer
from Message_Bot.udp_listener import UdpListener

import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== Initialization ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_states = {}

buyer = GiftBuyer(
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    status_file=STATUS_FILE,
    log_file=LOG_FILE,
)

udp = UdpListener(
    license_key=LICENSE_KEY,
    host=UDP_LISTEN_HOST,
    port=UDP_LISTEN_PORT,
)
udp.on_gifts(buyer.handle_new_gifts)


# ================== Status helpers ==================
def read_status() -> dict:
    return buyer.read_status()


def write_status(data: dict):
    buyer.write_status(data)


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

        balance = 0
        if buyer._client and buyer._client.is_connected():
            try:
                from Message_Bot.telegram_api import get_stars_balance
                balance = await get_stars_balance(buyer._client)
            except Exception:
                pass

        reply = (
            f"📈 Статус бота:\n"
            f"• Активен: {'✅' if is_active else '❌'}\n"
            f"• Баланс: {balance} ⭐\n"
            f"• Текущее распределение звезд:\n{distribution or '— не задано —'}"
        )
        await message.answer(reply)
        return True

    elif text == "💰 Начать 💰":
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
    await message.answer(
        "🎛️ Перед тобой панель управления ботом\nВыбери нужный раздел: 👇",
        reply_markup=make_kb_grid_main(),
    )


# ================== Predicates ==================
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


# ================== Register handlers ==================
dp.message.register(controlUser, Command(commands=["start"]))
dp.message.register(handle_back_button, is_back_button_predicate)
dp.message.register(handle_text_after_buttons, awaiting_input_predicate)
dp.message.register(handle_settings_buttons, is_settings_button_predicate)


# ================== Main ==================
async def main():
    ensure_status()

    # Connect Telethon client for purchasing
    await buyer.connect()

    # Start UDP listener for receiving gifts from Backend
    await udp.start()

    try:
        await dp.start_polling(bot)
    finally:
        udp.stop()
        await buyer.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
