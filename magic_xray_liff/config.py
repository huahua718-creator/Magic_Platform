import os
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "YOUR_LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_LINE_CHANNEL_ACCESS_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "YOUR_ADMIN_LINE_USER_ID")
LIFF_URL = os.getenv("LIFF_URL", f"{BASE_URL}/magic-app")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

