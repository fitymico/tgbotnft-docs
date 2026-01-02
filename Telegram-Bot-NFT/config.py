"""
Конфигурация проекта Telegram-Bot-NFT
Все секретные данные загружаются из переменных окружения или .env файла
"""
import os
from pathlib import Path

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).parent.resolve()

# ================== Telegram Bot ==================
# Токен бота (из переменных окружения)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ID администратора бота
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ================== Telegram API (MTProto) ==================
# API ID и Hash для MTProto клиента
API_ID = os.getenv("API_ID", "")
API_HASH = os.getenv("API_HASH", "")

# ================== Пути к файлам ==================
DATA_DIR = PROJECT_ROOT / "data"
STATUS_FILE = DATA_DIR / "status.json"
LOG_FILE = DATA_DIR / "bot.log"
SESSION_FILE = DATA_DIR / "session.session"
GIFT_ID_FILE = DATA_DIR / "giftID.json"

# Проверка наличия обязательных переменных
def validate_config():
    """Проверяет наличие обязательных переменных конфигурации"""
    errors = []
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    
    if ADMIN_ID == 0:
        errors.append("ADMIN_ID не задан")
    
    if not API_ID:
        errors.append("API_ID не задан")
    
    if not API_HASH:
        errors.append("API_HASH не задан")
    
    if errors:
        raise ValueError("Ошибки конфигурации:\n" + "\n".join(f"  - {e}" for e in errors))

# Создание директории data если её нет
DATA_DIR.mkdir(parents=True, exist_ok=True)
