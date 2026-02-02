import os

from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
PORT = int(os.getenv("BACKEND_PORT", "8090"))
UDP_PORT = int(os.getenv("UDP_PORT", "9100"))
SERVER_API_ID = int(os.getenv("SERVER_API_ID", "0"))
SERVER_API_HASH = os.getenv("SERVER_API_HASH", "")
SERVER_SESSION_STRING = os.getenv("SERVER_SESSION_STRING", "")
LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", "https://82.148.18.168:8080")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")
DB_PATH = os.getenv("BACKEND_DB_PATH", "backend.db")
SCAN_INTERVAL = float(os.getenv("SCAN_INTERVAL", "1.0"))
