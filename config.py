"""
Конфигурация бота
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

ADMIN_IDS = [int(admin_id.strip()) for admin_id in os.getenv("ADMIN_IDS", "").split(",") if admin_id.strip()]

# Database Configuration
# По умолчанию используем SQLite для удобства разработки
_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./deposit_bot.db")
# Если в конфиге указан тестовый PostgreSQL, заменяем на SQLite
if "username:password@localhost" in _db_url:
    DATABASE_URL = "sqlite+aiosqlite:///./deposit_bot.db"
else:
    DATABASE_URL = _db_url

# Webhook Configuration
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8443))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

# File Storage
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10485760))  # 10MB

# Rate Limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 1))
MAX_APPLICATIONS_PER_DAY = int(os.getenv("MAX_APPLICATIONS_PER_DAY", 3))

# Proxy Configuration (опционально)
PROXY_URL = os.getenv("PROXY_URL")  # Например: http://proxy:port или socks5://proxy:port

# Supported file types
SUPPORTED_FILE_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "application/pdf": [".pdf"]
}

# Deposit amounts
DEPOSIT_AMOUNTS = [10, 25, 50, 100]

# Application statuses
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_NEEDS_INFO = "needs_info"

# Payment Configuration (SmartGlocal)
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")  # Токен от SmartGlocal
PAYMENT_CURRENCY = os.getenv("PAYMENT_CURRENCY", "USD")  # USD, EUR, RUB и т.д.
PAYMENT_COMMISSION_PERCENT = float(os.getenv("PAYMENT_COMMISSION_PERCENT", "0"))  # 0 = без комиссии