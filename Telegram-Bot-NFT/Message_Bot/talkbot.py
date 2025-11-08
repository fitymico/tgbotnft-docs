import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================== Настройки ==================
BOT_TOKEN = "***REDACTED_BOT_TOKEN***"
ADMIN_ID = ***REDACTED_ADMIN_ID***

# ================== Инициализация бота ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== Функция проверки админа ==================
# Проверяем, что сообщение пришло именно от нас
async def is_admin(message: types.Message) -> bool:
    return message.from_user.id == ADMIN_ID

async def controlUser(message: types.Message):
    if not await is_admin(message):
        return
    await message.answer(f"Привет! Твой user_id = {message.from_user.id}\nТы единственный, кто может использовать этого бота!")

dp.message.register(controlUser, Command(commands=["me"]))
dp.message.register(controlUser, Command(commands=["start"]))


# ================== Запуск бота ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())