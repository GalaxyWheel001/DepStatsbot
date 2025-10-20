"""
Основной файл Telegram-бота для системы депозитов
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from config import BOT_TOKEN, ADMIN_IDS, UPLOAD_DIR
from database import init_database
from handlers_enhanced import router
from middleware import RateLimitMiddleware, LoggingMiddleware
from admin_enhanced import router as admin_router
from admin_extended_features import router as admin_extended_router
from payments_integration import router as payments_router

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Создаем директории
import os
os.makedirs("logs", exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
logger.info(f"Директории созданы: logs, {UPLOAD_DIR}")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрация middleware
dp.message.middleware(RateLimitMiddleware())
dp.callback_query.middleware(RateLimitMiddleware())
dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())

# Регистрация роутера с обработчиками
dp.include_router(router)
dp.include_router(admin_router)
dp.include_router(admin_extended_router)
dp.include_router(payments_router)

async def on_startup():
    """Действия при запуске"""
    await init_database()
    logger.info("✅ База данных инициализирована")
    
    # Уведомление администраторов о запуске
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🤖 Бот запущен и готов к работе!")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
    
    logger.info("✅ Бот успешно запущен!")

async def on_shutdown():
    """Действия при остановке"""
    logger.info("🛑 Бот остановлен")
    await bot.session.close()

async def main():
    """Основная функция"""
    try:
        logger.info("🚀 Запуск бота в режиме polling...")
        await on_startup()
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        sys.exit(1)
