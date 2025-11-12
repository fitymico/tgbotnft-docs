import asyncio
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================== Настройки ==================
BOT_TOKEN = "***REDACTED_BOT_TOKEN***"
ADMIN_ID = ***REDACTED_ADMIN_ID***

# ================== Инициализация бота ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== Функция создания клавиатуры ==================
def make_kb_grid_minor():
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="⭐ Распределение звезд ⭐")],
            [types.KeyboardButton(text="🔁 Кол-во итераций 🔁")],
            [types.KeyboardButton(text="⏰ Задержка ⏰")],
            [types.KeyboardButton(text="⬅️ Назад ⬅️")],
        ],
        resize_keyboard=True,      # подгонять размер под устройство
        one_time_keyboard=False    # False -> клавиатура остаётся видимой после нажатия
    )
    return kb

def make_kb_grid_main():
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔧 Настройки 🔧"), types.KeyboardButton(text="💰 Начать 💰")],
            [types.KeyboardButton(text="📊 Статус 📊"), types.KeyboardButton(text="🛑 Остановить 🛑")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return kb

async def pushed_button(message: types.Message):
    text = message.text

    if text == "🔧 Настройки 🔧":
        kb = make_kb_grid_minor()
        await message.answer("Открываю меню настроек 👇", reply_markup=kb)
    elif text == "📊 Статус 📊":
        await message.answer("Button 2 pushed")
    elif text == "💰 Начать 💰":
        await message.answer("💰 Сканирование подарков началось!")
        subprocess.Popen(["bash", "../scripts/startbot.sh"])
    elif text == "🛑 Остановить 🛑":
        await message.answer("🛑 Сканирование подарков остановлено!")
        subprocess.Popen(["bash", "../scripts/stopbot.sh"])
    elif text == "⭐ Распределение звезд ⭐":
        await message.answer("Введите распределение звезд для закупки:")
    elif text == "🔁 Кол-во итераций 🔁":
        await message.answer("Введите количество итераций:")
    elif text == "⏰ Задержка ⏰":
        await message.answer("Введите задержку между покупками (в секундах):")
    elif text == "⬅️ Назад ⬅️":
        kb_main = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🔧 Настройки 🔧"), types.KeyboardButton(text="💰 Начать 💰")],
                [types.KeyboardButton(text="📊 Статус 📊"), types.KeyboardButton(text="🛑 Остановить 🛑")]
            ],
            resize_keyboard=True
        )
        await message.answer("Возврат в главное меню 👇", reply_markup=kb_main)

# ================== Функция проверки админа ==================
# Проверяем, что сообщение пришло именно от нас
async def is_admin(message: types.Message) -> bool:
    return message.from_user.id == ADMIN_ID

async def controlUser(message: types.Message):
    if not await is_admin(message):
        return
    kb = make_kb_grid_main()
    await message.answer(
        "🎛️ Перед тобой панель управления ботом\nВыбери нужный раздел: 👇",
        reply_markup=kb
    )

# ================== Запуск бота ==================
dp.message.register(controlUser, Command(commands=["start"]))
dp.message.register(pushed_button)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())