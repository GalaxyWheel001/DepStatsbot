"""
Интеграция платежной системы Telegram Payments с SmartGlocal
Поддержка: Card-to-Card, Google Pay, Apple Pay
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, 
    PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from loguru import logger

from database import DatabaseManager, async_session_maker
from config import ADMIN_IDS

router = Router()

# ==================== КОНФИГУРАЦИЯ ПЛАТЕЖЕЙ ====================

class PaymentConfig:
    """Конфигурация платежной системы"""
    
    # SmartGlocal Provider Token (получить на https://smart-glocal.com)
    # Для тестирования используйте тестовый токен
    PROVIDER_TOKEN = None  # Устанавливается через админ-панель или .env
    
    # Валюта (ISO 4217)
    CURRENCY = "USD"  # USD, EUR, RUB и т.д.
    
    # Поддерживаемые методы оплаты
    PAYMENT_METHODS = {
        "card": "💳 Банковская карта",
        "google_pay": "🟢 Google Pay",
        "apple_pay": "🍎 Apple Pay"
    }
    
    # Минимальная и максимальная сумма
    MIN_AMOUNT = 10
    MAX_AMOUNT = 10000
    
    # Комиссия (если есть)
    COMMISSION_PERCENT = 0  # 0% - без комиссии, 3.5 для 3.5%
    
    # Описание для чека
    PAYMENT_DESCRIPTION = "Депозит в систему"
    
    @classmethod
    def get_provider_token(cls) -> Optional[str]:
        """Получить токен провайдера"""
        if cls.PROVIDER_TOKEN:
            return cls.PROVIDER_TOKEN
        
        # Пытаемся получить из переменных окружения
        import os
        token = os.getenv("PAYMENT_PROVIDER_TOKEN")
        if token:
            cls.PROVIDER_TOKEN = token
            return token
        
        return None
    
    @classmethod
    async def get_token_from_db(cls):
        """Получить токен из базы данных"""
        async with async_session_maker() as session:
            token = await DatabaseManager.get_setting(session, "payment_provider_token")
            if token:
                cls.PROVIDER_TOKEN = token
                return token
        return None
    
    @classmethod
    def is_configured(cls) -> bool:
        """Проверка, настроена ли платежная система"""
        return cls.get_provider_token() is not None
    
    @classmethod
    def calculate_amount(cls, base_amount: float) -> int:
        """
        Рассчитать финальную сумму с комиссией
        Возвращает сумму в минимальных единицах (копейки, центы)
        """
        if cls.COMMISSION_PERCENT > 0:
            total = base_amount * (1 + cls.COMMISSION_PERCENT / 100)
        else:
            total = base_amount
        
        # Telegram требует сумму в минимальных единицах (центы для USD)
        return int(total * 100)
    
    @classmethod
    def format_amount(cls, amount_cents: int) -> str:
        """Форматировать сумму для отображения"""
        amount_dollars = amount_cents / 100
        return f"${amount_dollars:.2f}"


# ==================== КЛАВИАТУРЫ ====================

def get_payment_method_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура выбора метода оплаты"""
    buttons = [
        [InlineKeyboardButton(
            text="💳 Банковская карта",
            callback_data="payment_method_card"
        )],
        [InlineKeyboardButton(
            text="🟢 Google Pay",
            callback_data="payment_method_google_pay"
        )],
        [InlineKeyboardButton(
            text="🍎 Apple Pay",
            callback_data="payment_method_apple_pay"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="back_to_menu"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_confirm_keyboard(amount: float, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения оплаты"""
    buttons = [
        [InlineKeyboardButton(
            text=f"💰 Оплатить ${amount}",
            pay=True  # Специальная кнопка для оплаты
        )],
        [InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="back_to_menu"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОБРАБОТЧИКИ ПЛАТЕЖЕЙ ====================

@router.callback_query(F.data == "menu_deposit_payment")
async def start_payment_deposit(callback: CallbackQuery):
    """Начало процесса оплаты депозита"""
    user_id = callback.from_user.id
    
    await callback.answer()
    
    # Проверяем, настроена ли платежная система
    if not PaymentConfig.is_configured():
        await PaymentConfig.get_token_from_db()
    
    if not PaymentConfig.is_configured():
        await callback.message.edit_text(
            "⚠️ <b>Платежная система временно недоступна</b>\n\n"
            "Извините, онлайн-оплата сейчас не настроена.\n"
            "Пожалуйста, используйте стандартный метод депозита "
            "или обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )
        return
    
    async with async_session_maker() as session:
        # Проверяем лимиты
        can_proceed, error_message = await DatabaseManager.check_user_rate_limit(session, user_id)
        lang = await DatabaseManager.get_user_language(session, user_id)
        
        if not can_proceed:
            await callback.answer("❌ Лимит достигнут", show_alert=True)
            await callback.message.edit_text(
                f"❌ {error_message}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        # Получаем доступные номиналы
        amounts = await DatabaseManager.get_deposit_amounts(session)
    
    # Показываем доступные суммы для оплаты
    text = (
        "💳 <b>Онлайн-оплата депозита</b>\n\n"
        "Вы можете оплатить депозит:\n"
        "• 💳 Банковской картой\n"
        "• 🟢 Google Pay\n"
        "• 🍎 Apple Pay\n\n"
        "Выберите сумму депозита:"
    )
    
    buttons = []
    for amount in amounts:
        buttons.append([InlineKeyboardButton(
            text=f"💰 ${amount}",
            callback_data=f"payment_amount_{amount}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="back_to_menu"
    )])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("payment_amount_"))
async def select_payment_amount(callback: CallbackQuery):
    """Выбор суммы для оплаты"""
    user_id = callback.from_user.id
    amount = float(callback.data.split("_")[2])
    
    await callback.answer()
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    # Рассчитываем финальную сумму
    amount_cents = PaymentConfig.calculate_amount(amount)
    final_amount = amount_cents / 100
    
    commission_text = ""
    if PaymentConfig.COMMISSION_PERCENT > 0:
        commission = amount * PaymentConfig.COMMISSION_PERCENT / 100
        commission_text = f"\n💼 Комиссия: ${commission:.2f} ({PaymentConfig.COMMISSION_PERCENT}%)"
    
    text = (
        "💳 <b>Подтверждение оплаты</b>\n\n"
        f"💰 Сумма депозита: ${amount}\n"
        f"{commission_text}"
        f"\n<b>Итого к оплате: ${final_amount:.2f}</b>\n\n"
        "Нажмите кнопку ниже для оплаты.\n"
        "Вы будете перенаправлены на безопасную страницу оплаты."
    )
    
    # Создаем инвойс для оплаты
    try:
        provider_token = PaymentConfig.get_provider_token()
        
        # Создаем invoice
        prices = [LabeledPrice(label=f"Депозит ${amount}", amount=amount_cents)]
        
        await callback.message.delete()
        
        # Отправляем invoice
        await callback.message.answer_invoice(
            title=f"Депозит ${amount}",
            description=f"{PaymentConfig.PAYMENT_DESCRIPTION}\n\nСумма: ${amount}",
            payload=f"deposit_{user_id}_{amount}_{int(datetime.utcnow().timestamp())}",
            provider_token=provider_token,
            currency=PaymentConfig.CURRENCY,
            prices=prices,
            start_parameter="deposit",
            reply_markup=get_payment_confirm_keyboard(final_amount, lang)
        )
        
        logger.info(f"Invoice отправлен пользователю {user_id} на сумму ${amount}")
        
    except Exception as e:
        logger.error(f"Ошибка создания invoice: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            f"Произошла ошибка при создании счета.\n"
            f"Пожалуйста, попробуйте позже или обратитесь к администратору.\n\n"
            f"Код ошибки: {str(e)[:50]}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
            ])
        )

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """
    Обработка pre-checkout запроса
    Здесь можно проверить доступность товара, корректность данных и т.д.
    """
    user_id = pre_checkout_query.from_user.id
    
    logger.info(f"Pre-checkout от пользователя {user_id}")
    logger.info(f"Payload: {pre_checkout_query.invoice_payload}")
    logger.info(f"Сумма: {pre_checkout_query.total_amount} {pre_checkout_query.currency}")
    
    try:
        # Парсим payload
        payload_parts = pre_checkout_query.invoice_payload.split("_")
        if len(payload_parts) >= 3:
            deposit_type = payload_parts[0]
            payload_user_id = int(payload_parts[1])
            amount = float(payload_parts[2])
            
            # Проверяем, что user_id совпадает
            if payload_user_id != user_id:
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Ошибка: несоответствие пользователя"
                )
                return
            
            # Проверяем лимиты
            async with async_session_maker() as session:
                can_proceed, error_message = await DatabaseManager.check_user_rate_limit(session, user_id)
                
                if not can_proceed:
                    await pre_checkout_query.answer(
                        ok=False,
                        error_message=f"Превышен лимит: {error_message}"
                    )
                    return
        
        # Все проверки пройдены - разрешаем оплату
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout одобрен для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в pre-checkout: {e}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="Произошла ошибка. Попробуйте позже."
        )

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """
    Обработка успешной оплаты
    Вызывается после того, как платеж прошел успешно
    """
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    logger.info(f"✅ Успешная оплата от пользователя {user_id}")
    logger.info(f"Сумма: {payment_info.total_amount} {payment_info.currency}")
    logger.info(f"Payload: {payment_info.invoice_payload}")
    logger.info(f"Provider payment charge ID: {payment_info.provider_payment_charge_id}")
    logger.info(f"Telegram payment charge ID: {payment_info.telegram_payment_charge_id}")
    
    try:
        # Парсим payload
        payload_parts = payment_info.invoice_payload.split("_")
        amount = float(payload_parts[2]) if len(payload_parts) >= 3 else 0
        
        async with async_session_maker() as session:
            # Создаем заявку с автоматическим одобрением
            application = await DatabaseManager.create_application(
                session=session,
                user_id=user_id,
                user_name=message.from_user.full_name or message.from_user.username or f"User{user_id}",
                login=f"payment_{payment_info.telegram_payment_charge_id[:10]}",
                amount=amount,
                file_id="payment"  # Специальный маркер для платежей
            )
            
            # Сразу одобряем заявку (оплата уже прошла)
            code = await DatabaseManager.get_activation_code(session, amount)
            
            if code:
                await DatabaseManager.update_application_status(
                    session=session,
                    application_id=application.id,
                    status="approved",
                    admin_id=0,  # 0 = автоматическое одобрение
                    activation_code_id=code.id,
                    admin_comment=f"Оплачено онлайн. TG Charge ID: {payment_info.telegram_payment_charge_id}"
                )
                
                await DatabaseManager.mark_code_as_used(session, code.id)
                
                # Логируем транзакцию
                await DatabaseManager.log_transaction(
                    session=session,
                    application_id=application.id,
                    action="approved",
                    admin_id=0,
                    comment=f"Автоматическое одобрение после онлайн-оплаты. Provider ID: {payment_info.provider_payment_charge_id}"
                )
                
                # Логируем действие администратора (автоматическое)
                await DatabaseManager.log_admin_action(
                    session=session,
                    admin_id=0,
                    action="auto_approve_payment",
                    target_id=application.id,
                    details=f"Автоодобрение заявки #{application.id} после оплаты ${amount}. Код: {code.code_value}"
                )
                
                # Обновляем лимиты пользователя
                await DatabaseManager.update_user_rate_limit(session, user_id)
                
                lang = await DatabaseManager.get_user_language(session, user_id)
                
                # Отправляем пользователю код активации
                success_text = (
                    "✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"💰 Сумма: ${amount}\n"
                    f"🎟️ <b>Ваш код активации:</b>\n"
                    f"<code>{code.code_value}</code>\n\n"
                    f"📋 Заявка #{application.id} автоматически одобрена.\n\n"
                    "Используйте этот код для активации вашей подписки.\n"
                    "Спасибо за оплату! 🎉"
                )
                
                await message.answer(
                    success_text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                    ])
                )
                
                # Уведомляем админов о платеже
                await notify_admins_payment(message.bot, application, payment_info)
                
            else:
                # Нет доступных кодов - создаем заявку в ожидании
                await DatabaseManager.log_transaction(
                    session=session,
                    application_id=application.id,
                    action="created",
                    comment=f"Оплачено онлайн, но нет кодов. Provider ID: {payment_info.provider_payment_charge_id}"
                )
                
                lang = await DatabaseManager.get_user_language(session, user_id)
                
                await message.answer(
                    "✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"💰 Сумма: ${amount}\n"
                    f"📋 Заявка #{application.id} создана.\n\n"
                    "⏳ Ваша заявка обрабатывается администратором.\n"
                    "Код активации будет выдан в ближайшее время.\n\n"
                    "Спасибо за оплату! 🎉",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                    ])
                )
                
                # Уведомляем админов (срочно - нужны коды!)
                await notify_admins_payment(message.bot, application, payment_info, urgent=True)
        
    except Exception as e:
        logger.error(f"Ошибка обработки успешной оплаты: {e}", exc_info=True)
        await message.answer(
            "⚠️ <b>Оплата прошла, но возникла ошибка</b>\n\n"
            "Ваш платеж принят, но произошла ошибка при обработке.\n"
            "Пожалуйста, обратитесь к администратору с этим сообщением.\n\n"
            f"ID транзакции: {payment_info.telegram_payment_charge_id}\n\n"
            "Мы решим проблему в ближайшее время.",
            parse_mode="HTML"
        )


async def notify_admins_payment(bot, application, payment_info, urgent: bool = False):
    """Уведомление администраторов о платеже"""
    urgent_marker = "🚨 СРОЧНО - НЕТ КОДОВ! " if urgent else ""
    
    text = (
        f"{urgent_marker}<b>💳 Новая онлайн-оплата!</b>\n\n"
        f"📋 Заявка: #{application.id}\n"
        f"👤 Пользователь: {application.user_name}\n"
        f"🆔 User ID: <code>{application.user_id}</code>\n"
        f"💰 Сумма: ${application.amount}\n"
        f"💳 Метод: Онлайн-оплата (SmartGlocal)\n"
        f"✅ Статус: {'Автоодобрена' if not urgent else 'Ожидает (нет кодов!)'}\n\n"
        f"🔑 Provider Charge ID:\n<code>{payment_info.provider_payment_charge_id}</code>\n"
        f"🔑 Telegram Charge ID:\n<code>{payment_info.telegram_payment_charge_id}</code>\n\n"
        f"🕐 Время: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")


# ==================== ТЕСТОВЫЙ ПЛАТЕЖ ====================

@router.message(Command("test_payment"))
async def test_payment(message: Message):
    """Тестовый платеж (только для разработки)"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await message.answer("❌ Эта команда доступна только администраторам")
        return
    
    if not PaymentConfig.is_configured():
        await message.answer(
            "⚠️ Платежная система не настроена.\n"
            "Установите PAYMENT_PROVIDER_TOKEN в .env или через админ-панель."
        )
        return
    
    # Тестовый инвойс
    amount = 10
    amount_cents = PaymentConfig.calculate_amount(amount)
    
    try:
        await message.answer_invoice(
            title="Тестовый платеж",
            description="Это тестовый платеж для проверки интеграции",
            payload=f"test_{user_id}_{int(datetime.utcnow().timestamp())}",
            provider_token=PaymentConfig.get_provider_token(),
            currency=PaymentConfig.CURRENCY,
            prices=[LabeledPrice(label="Тест", amount=amount_cents)],
            start_parameter="test"
        )
        
        await message.answer(
            "✅ Тестовый invoice отправлен\n\n"
            "Для тестирования используйте тестовые карты:\n"
            "• 4242 4242 4242 4242 (успешная оплата)\n"
            "• 4000 0000 0000 0002 (отклонена)\n\n"
            "Любая дата истечения в будущем и любой CVC"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка создания тестового платежа:\n{str(e)}")

