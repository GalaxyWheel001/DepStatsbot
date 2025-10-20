"""
Middleware для бота
"""
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from loguru import logger

class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""
    
    def __init__(self):
        self.user_last_request: Dict[int, float] = {}
        self.user_request_count: Dict[int, int] = {}
        self.user_request_reset: Dict[int, float] = {}
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = time.time()
        
        # Сброс счетчика каждую минуту
        if user_id in self.user_request_reset:
            if current_time - self.user_request_reset[user_id] > 60:
                self.user_request_count[user_id] = 0
                self.user_request_reset[user_id] = current_time
        
        # Инициализация для нового пользователя
        if user_id not in self.user_request_count:
            self.user_request_count[user_id] = 0
            self.user_request_reset[user_id] = current_time
        
        # Проверка лимита (более мягкий) - только для сообщений, не для callback
        if isinstance(event, Message):
            if user_id in self.user_last_request:
                time_diff = current_time - self.user_last_request[user_id]
                if time_diff < 0.5:  # 0.5 секунды для сообщений
                    await event.answer(
                        "⏳ Подождите немного"
                    )
                    return
        else:
            # Для callback - минимальная защита от двойного клика
            if user_id in self.user_last_request:
                time_diff = current_time - self.user_last_request[user_id]
                if time_diff < 0.3:  # 0.3 секунды для кнопок
                    await event.answer(
                        "⏳ Немного медленнее",
                        show_alert=False
                    )
                    return
        
        # Обновляем время последнего запроса
        self.user_last_request[user_id] = current_time
        self.user_request_count[user_id] += 1
        
        # Логируем запрос
        logger.info(f"Пользователь {user_id} сделал запрос #{self.user_request_count[user_id]}")
        
        return await handler(event, data)

class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        username = event.from_user.username or "Unknown"
        
        if isinstance(event, Message):
            text_preview = event.text[:50] if event.text else "[медиа]"
            logger.info(f"Сообщение от {user_id} (@{username}): {text_preview}...")
        else:
            logger.info(f"Callback от {user_id} (@{username}): {event.data}")
        
        return await handler(event, data)

class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""
    
    def __init__(self, admin_ids: list):
        self.admin_ids = admin_ids
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        if user_id not in self.admin_ids:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав для выполнения этой команды")
            else:
                await event.answer("❌ У вас нет прав для выполнения этого действия", show_alert=True)
            return
        
        return await handler(event, data)
