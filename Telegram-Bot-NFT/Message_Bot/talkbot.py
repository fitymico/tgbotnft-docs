import asyncio, json, os, tempfile, fcntl
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================== Настройки ==================
BOT_TOKEN = "***REDACTED_BOT_TOKEN***"
ADMIN_ID = ***REDACTED_ADMIN_ID***
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/status.json")

# ================== Инициализация бота ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_states = {}

# ================== Функция работы с json ==================
def ensure_dir_for_file(path):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)

def read_status():
    """Вернуть словарь состояния. Если файла нет — вернуть дефолт."""
    ensure_dir_for_file(STATUS_FILE)
    default = {
        "is_running": False,
        "status_text": "stopped",
        "distribution": "",
        "iterations_total": 0,
        "iteration_current": 0,
        "delay": 1.0
    }
    if not os.path.exists(STATUS_FILE):
        return default
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                return json.load(f)
            finally:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except:
                    pass
    except Exception:
        return default

def write_status_atomic(data: dict):
    """Безопасная атомарная запись JSON: write->fsync->replace."""
    ensure_dir_for_file(STATUS_FILE)
    dirpath = os.path.dirname(STATUS_FILE)
    fd, tmp_path = tempfile.mkstemp(prefix="status.", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            fcntl.flock(tmpf.fileno(), fcntl.LOCK_EX)
            json.dump(data, tmpf, ensure_ascii=False, indent=2)
            tmpf.flush()
            os.fsync(tmpf.fileno())
            fcntl.flock(tmpf.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, STATUS_FILE)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass

async def handle_text_after_buttons(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    state = user_states.get(user_id)
    if not state:
        return

    text = message.text.strip()
    if not text:
        await message.answer("Пустой ввод. Попробуйте снова.")
        return

    s = read_status()

    if state == "awaiting_distribution":
        s["distribution"] = text
        await message.answer("✅ Распределение звёзд сохранено!", reply_markup=make_kb_grid_minor())
    elif state == "awaiting_iterations":
        try:
            s["iterations_total"] = int(text)
            await message.answer(f"✅ Количество итераций сохранено: {text}", reply_markup=make_kb_grid_minor())
        except ValueError:
            await message.answer("❌ Введите число, например: 10")
            return
    elif state == "awaiting_delay":
        try:
            s["delay"] = float(text)
            await message.answer(f"✅ Задержка сохранена: {text} сек", reply_markup=make_kb_grid_minor())
        except ValueError:
            await message.answer("❌ Введите число, например: 1.5")
            return

    write_status_atomic(s)
    user_states.pop(user_id, None)

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
        s = read_status()
        reply = (
            f"📈 Статус бота:\n"
            f"• Активен: {'✅' if s.get('is_running') else '❌'}\n"
            f"• Статус: {s.get('status_text')}\n"
            f"• Итерация: {s.get('iteration_current',0)}/{s.get('iterations_total',0)}\n"
            f"• Задержка: {s.get('delay', 1.0)} сек\n"
            f"• Распределение (строки):\n{s.get('distribution') or '— не задано —'}"
        )
        await message.answer(reply)

    elif text == "💰 Начать 💰":
        s = read_status()
        s["is_running"] = True
        s["status_text"] = "running"
        write_status_atomic(s)
        subprocess.Popen(["bash", "../scripts/startbot.sh"])
        await message.answer("💰 Сканирование подарков началось!")

    elif text == "🛑 Остановить 🛑":
        s = read_status()
        s["is_running"] = False
        s["status_text"] = "stopped"
        write_status_atomic(s)
        subprocess.Popen(["bash", "../scripts/stopbot.sh"])
        await message.answer("🛑 Сканирование подарков остановлено!")

    elif text == "⭐ Распределение звезд ⭐":
        await message.answer(
            "Введите распределение (по строкам: условие_цены количество), например:\n"
            "<1000 10\n>=1000 и <5000 5"
        )
        user_states[message.from_user.id] = "awaiting_distribution"

    elif text == "🔁 Кол-во итераций 🔁":
        await message.answer("Введите количество итераций:")
        user_states[message.from_user.id] = "awaiting_iterations"

    elif text == "⏰ Задержка ⏰":
        await message.answer("Введите задержку между покупками (в секундах):")
        user_states[message.from_user.id] = "awaiting_delay"

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

def awaiting_input_predicate(message: types.Message) -> bool:
    uid = message.from_user.id if message.from_user else None
    if not uid or uid not in user_states:
        return False
    return user_states[uid] in ("awaiting_distribution", "awaiting_iterations", "awaiting_delay")

# ================== Запуск бота ==================
dp.message.register(controlUser, Command(commands=["start"]))
dp.message.register(handle_text_after_buttons, awaiting_input_predicate)
dp.message.register(pushed_button)


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())