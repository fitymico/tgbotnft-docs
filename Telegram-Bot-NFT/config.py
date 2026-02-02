import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    # Running as PyInstaller binary — use directory containing the executable
    PROJECT_ROOT = Path(sys.executable).parent.resolve()
else:
    PROJECT_ROOT = Path(__file__).parent.resolve()

load_dotenv(PROJECT_ROOT / ".env")

# ================== Telegram Bot ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ================== License ==================
LICENSE_KEY = os.getenv("LICENSE_KEY", "")

# ================== Telethon (user session) ==================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# ================== UDP listener ==================
UDP_LISTEN_HOST = os.getenv("UDP_LISTEN_HOST", "0.0.0.0")
UDP_LISTEN_PORT = int(os.getenv("UDP_LISTEN_PORT", "9200"))

# ================== Data paths ==================
STATUS_FILE = str(PROJECT_ROOT / "data" / "status.json")
LOG_FILE = str(PROJECT_ROOT / "data" / "bot.log")


def validate_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN not set")
    if ADMIN_ID == 0:
        errors.append("ADMIN_ID not set")
    if not LICENSE_KEY:
        errors.append("LICENSE_KEY not set")
    if not API_ID:
        errors.append("API_ID not set")
    if not API_HASH:
        errors.append("API_HASH not set")
    if not SESSION_STRING:
        errors.append("SESSION_STRING not set")
    if errors:
        raise ValueError("Config errors:\n" + "\n".join(f"  - {e}" for e in errors))
