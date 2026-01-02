import asyncio, json, os, tempfile, fcntl, re
import subprocess
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from dotenv import load_dotenv

# Загружаем .env из корня проекта
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(PROJECT_ROOT / ".env")

# Добавляем корень проекта в путь для импорта config
sys.path.insert(0, str(PROJECT_ROOT))
from config import BOT_TOKEN, ADMIN_ID, STATUS_FILE, LOG_FILE

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

def validate_distribution(text: str) -> tuple[bool, str]:
    """
    Проверяет правильность формата распределения звезд.
    Формат: <условие> <количество>
    Пример: <1000 10
            >=1000 и <5000 5
            >5000 1
    """
    lines = text.strip().split('\n')
    if not lines:
        return False, "Пустой ввод"
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        # Разделяем строку на части
        parts = line.split()
        if len(parts) < 2:
            return False, f"Ошибка в строке {i}: недостаточно значений"
        
        # Проверяем количество (последний элемент)
        try:
            quantity = int(parts[-1])
            if quantity <= 0:
                return False, f"Ошибка в строке {i}: количество должно быть положительным числом"
        except ValueError:
            return False, f"Ошибка в строке {i}: количество должно быть целым числом"
        
        # Извлекаем условие (все части кроме последней - количества)
        condition_parts = parts[:-1]
        
        # Собираем условие обратно в строку
        condition = ' '.join(condition_parts)
        
        # Проверяем сложные условия с "и"
        if " и " in condition:
            sub_conditions = condition.split(" и ")
            for sub_cond in sub_conditions:
                sub_cond = sub_cond.strip()
                if not re.match(r'^[<>=]=?\d+(\.\d+)?$', sub_cond):
                    return False, f"Ошибка в строке {i}: неверный формат условия '{sub_cond}'"
        else:
            # Простое условие
            if not re.match(r'^[<>=]=?\d+(\.\d+)?$', condition):
                return False, f"Ошибка в строке {i}: неверный формат условия '{condition}'"
    
    return True, ""

# ================== Функция создания клавиатуры ==================
def make_kb_grid_minor():
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="⭐ Распределение звезд ⭐")],
            [types.KeyboardButton(text="📋 Лог-файл покупок за все время 📋")],
            [types.KeyboardButton(text="⬅️ Назад ⬅️")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
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

# ================== Обработчики ==================
async def handle_text_after_buttons(message: types.Message):
    """Обработка текста после нажатия кнопок настроек"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    text = message.text.strip()
    if not text:
        await message.answer("Пустой ввод. Попробуйте снова.")
        return
    
    # Проверяем, не нажата ли кнопка "Назад" в тексте
    if text == "⬅️ Назад ⬅️":
        # Удаляем состояние пользователя
        user_states.pop(user_id, None)
        # Показываем главное меню
        await message.answer("Возврат в главное меню 👇", reply_markup=make_kb_grid_main())
        return
    
    state = user_states.get(user_id)
    if not state:
        return

    s = read_status()

    if state == "awaiting_distribution":
        # Проверяем валидность распределения
        is_valid, error_msg = validate_distribution(text)
        if not is_valid:
            await message.answer(f"❌ {error_msg}\n\nПопробуйте снова:")
            return
            
        s["distribution"] = text
        write_status_atomic(s)
        user_states.pop(user_id, None)
        await message.answer("✅ Распределение звёзд сохранено!", reply_markup=make_kb_grid_minor())
        
    elif state == "awaiting_iterations":
        try:
            s["iterations_total"] = int(text)
            write_status_atomic(s)
            user_states.pop(user_id, None)
            await message.answer(f"✅ Количество итераций сохранено: {text}", reply_markup=make_kb_grid_minor())
        except ValueError:
            await message.answer("❌ Введите число, например: 10")
            return
            
    elif state == "awaiting_delay":
        try:
            s["delay"] = float(text)
            write_status_atomic(s)
            user_states.pop(user_id, None)
            await message.answer(f"✅ Задержка сохранена: {text} сек", reply_markup=make_kb_grid_minor())
        except ValueError:
            await message.answer("❌ Введите число, например: 1.5")
            return

async def handle_back_button(message: types.Message):
    """Обработка кнопки Назад"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    
    text = message.text.strip()
    if text == "⬅️ Назад ⬅️":
        # Очищаем состояние пользователя
        user_states.pop(user_id, None)
        # Показываем главное меню
        await message.answer("Возврат в главное меню 👇", reply_markup=make_kb_grid_main())
        return True
    return False

async def handle_settings_buttons(message: types.Message):
    """Обработка кнопок настроек"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return False
    
    text = message.text.strip()
    
    if text == "🔧 Настройки 🔧":
        kb = make_kb_grid_minor()
        await message.answer("Открываю меню настроек 👇", reply_markup=kb)
        return True
        
    elif text == "📊 Статус 📊":
        s = read_status()
        reply = (
            f"📈 Статус бота:\n"
            f"• Активен: {'✅' if s.get('is_running') else '❌'}\n"
            f"• Текущее распределение звезд:\n{s.get('distribution') or '— не задано —'}"
        )
        await message.answer(reply)
        return True
        
    elif text == "💰 Начать 💰":
        s = read_status()
        s["is_running"] = True
        s["status_text"] = "running"
        write_status_atomic(s)
        subprocess.Popen(["bash", str(PROJECT_ROOT / "scripts" / "startbot.sh")])
        await message.answer("💰 Сканирование подарков началось!")
        return True
        
    elif text == "🛑 Остановить 🛑":
        s = read_status()
        s["is_running"] = False
        s["status_text"] = "stopped"
        write_status_atomic(s)
        subprocess.Popen(["bash", str(PROJECT_ROOT / "scripts" / "stopbot.sh")])
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
            try:
                with open(LOG_FILE, 'rb') as log_file:
                    await message.answer_document(
                        types.BufferedInputFile(
                            log_file.read(),
                            filename="bot_log.txt"
                        ),
                        caption="📋 Лог-файл покупок"
                    )
            except Exception as e:
                await message.answer(f"❌ Ошибка при чтении лог-файла: {str(e)}")
        else:
            await message.answer("📭 Лог-файл пока пуст или не создан.")
        return True
    
    return False

async def controlUser(message: types.Message):
    """Обработка команды /start"""
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = make_kb_grid_main()
    await message.answer(
        "🎛️ Перед тобой панель управления ботом\nВыбери нужный раздел: 👇",
        reply_markup=kb
    )

# ================== Предикаты ==================
def awaiting_input_predicate(message: types.Message) -> bool:
    """Проверяет, ожидает ли бот ввода от пользователя"""
    uid = message.from_user.id if message.from_user else None
    if not uid or uid not in user_states:
        return False
    return user_states[uid] in ("awaiting_distribution", "awaiting_iterations", "awaiting_delay")

def is_back_button_predicate(message: types.Message) -> bool:
    """Проверяет, нажата ли кнопка Назад"""
    return message.text and message.text.strip() == "⬅️ Назад ⬅️"

def is_settings_button_predicate(message: types.Message) -> bool:
    """Проверяет, нажата ли одна из кнопок управления"""
    text = message.text.strip() if message.text else ""
    return text in [
        "🔧 Настройки 🔧", "💰 Начать 💰", "📊 Статус 📊", "🛑 Остановить 🛑",
        "⭐ Распределение звезд ⭐", "📋 Лог-файл покупок за все время 📋"
    ]

# ================== Регистрация обработчиков ==================
# Важен порядок: сначала специфичные обработчики, потом общие
dp.message.register(controlUser, Command(commands=["start"]))
dp.message.register(handle_back_button, is_back_button_predicate)
dp.message.register(handle_text_after_buttons, awaiting_input_predicate)
dp.message.register(handle_settings_buttons, is_settings_button_predicate)

# ================== Запуск бота ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())