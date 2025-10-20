"""
Дополнительные функции для админ-панели (часть 2)
Управление номиналами депозита, логи безопасности, настройка языков
"""
import json
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from database import DatabaseManager, async_session_maker
from admin_enhanced import DepositAmountsStates, check_superadmin_rights

router = Router()

# ==================== УПРАВЛЕНИЕ НОМИНАЛАМИ ДЕПОЗИТА ====================

@router.callback_query(F.data == "admin_manage_amounts")
async def manage_deposit_amounts(callback: CallbackQuery):
    """Управление номиналами депозита"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        current_amounts = await DatabaseManager.get_deposit_amounts(session)
    
    amounts_str = ", ".join([f"${a}" for a in current_amounts])
    
    text = (
        "💰 <b>Управление номиналами депозита</b>\n\n"
        f"<b>Текущие номиналы:</b>\n{amounts_str}\n\n"
        "Эти суммы доступны пользователям при создании заявки на депозит.\n\n"
        "💡 Для изменения нажмите кнопку ниже."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить номиналы", callback_data="amounts_edit")],
        [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "amounts_edit")
async def edit_amounts_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования номиналов"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(DepositAmountsStates.waiting_for_new_amounts)
    
    text = (
        "✏️ <b>Изменение номиналов депозита</b>\n\n"
        "Отправьте новые номиналы через запятую.\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>10, 25, 50, 100, 200</code>\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Используйте только числа\n"
        "• Разделяйте запятой\n"
        "• Минимум 1 номинал\n"
        "• Максимум 10 номиналов\n\n"
        "Отправьте /cancel для отмены"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_amounts")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(DepositAmountsStates.waiting_for_new_amounts))
async def edit_amounts_process(message: Message, state: FSMContext):
    """Обработка новых номиналов"""
    user_id = message.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await message.answer("❌ Только для суперадминистратора")
        await state.clear()
        return
    
    try:
        # Парсим номиналы
        amounts_str = message.text.strip()
        amounts = [int(float(x.strip().replace("$", ""))) for x in amounts_str.split(",")]
        
        # Проверки
        if len(amounts) < 1:
            await message.answer("❌ Нужен хотя бы 1 номинал.")
            return
        
        if len(amounts) > 10:
            await message.answer("❌ Максимум 10 номиналов.")
            return
        
        if any(a <= 0 for a in amounts):
            await message.answer("❌ Все номиналы должны быть положительными.")
            return
        
        if any(a > 100000 for a in amounts):
            await message.answer("❌ Максимальный номинал: 100,000 USD")
            return
        
        # Сохраняем в базу данных
        async with async_session_maker() as session:
            await DatabaseManager.set_deposit_amounts(session, amounts, user_id)
            
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session,
                user_id,
                "change_deposit_amounts",
                details=f"Изменены номиналы на: {amounts}"
            )
        
        amounts_display = ", ".join([f"${a}" for a in amounts])
        await message.answer(
            f"✅ <b>Номиналы обновлены!</b>\n\n"
            f"💰 <b>Новые номиналы:</b>\n{amounts_display}\n\n"
            f"Изменения вступят в силу для новых заявок.",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте числа через запятую.")
    except Exception as e:
        logger.error(f"Ошибка изменения номиналов: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

# ==================== ЛОГИ БЕЗОПАСНОСТИ ====================

@router.callback_query(F.data == "admin_security_logs")
async def security_logs_menu(callback: CallbackQuery):
    """Просмотр логов безопасности"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        # Получаем последние логи
        logs = await DatabaseManager.get_admin_logs(session, limit=20, days=7)
    
    if not logs:
        text = "🔐 <b>Логи безопасности</b>\n\n⚠️ Нет записей за последние 7 дней."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    text = f"🔐 <b>Логи безопасности</b>\n\n📊 Последние {len(logs)} действий (за 7 дней):\n\n"
    
    action_names = {
        "add_admin": "➕ Добавлен админ",
        "remove_admin": "➖ Удален админ",
        "add_code": "🎟️ Добавлен код",
        "delete_code": "🗑️ Удален код",
        "import_codes": "📄 Импорт кодов",
        "change_deposit_amounts": "💰 Изменены номиналы",
        "change_language_settings": "🌐 Изменены языки"
    }
    
    for log in logs:
        action_display = action_names.get(log.action, log.action)
        timestamp = log.timestamp.strftime("%d.%m %H:%M")
        
        text += f"• {timestamp} | {action_display}\n"
        text += f"  Админ: {log.admin_id}"
        
        if log.target_id:
            text += f" | Цель: {log.target_id}"
        
        if log.details:
            details_short = log.details[:50] + "..." if len(log.details) > 50 else log.details
            text += f"\n  {details_short}"
        
        text += "\n\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (список обрезан)"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_security_logs"),
            InlineKeyboardButton(text="📅 За месяц", callback_data="security_logs_month")
        ],
        [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "security_logs_month")
async def security_logs_month(callback: CallbackQuery):
    """Логи за месяц"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        logs = await DatabaseManager.get_admin_logs(session, limit=50, days=30)
    
    if not logs:
        text = "🔐 <b>Логи безопасности</b>\n\n⚠️ Нет записей за последний месяц."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_security_logs")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Статистика действий
    actions_count = {}
    for log in logs:
        actions_count[log.action] = actions_count.get(log.action, 0) + 1
    
    text = (
        f"🔐 <b>Логи безопасности (30 дней)</b>\n\n"
        f"📊 <b>Всего действий:</b> {len(logs)}\n\n"
        f"<b>По типам:</b>\n"
    )
    
    action_names = {
        "add_admin": "➕ Добавлено админов",
        "remove_admin": "➖ Удалено админов",
        "add_code": "🎟️ Добавлено кодов",
        "delete_code": "🗑️ Удалено кодов",
        "import_codes": "📄 Импортов кодов",
        "change_deposit_amounts": "💰 Изменений номиналов"
    }
    
    for action, count in sorted(actions_count.items(), key=lambda x: x[1], reverse=True):
        action_display = action_names.get(action, action)
        text += f"• {action_display}: {count}\n"
    
    text += f"\n💡 Всего показано последних {len(logs)} записей."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_security_logs")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==================== НАСТРОЙКИ ПЛАТЕЖЕЙ ====================

@router.callback_query(F.data == "admin_payment_settings")
async def payment_settings(callback: CallbackQuery):
    """Настройки платежной системы"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    async with async_session_maker() as session:
        # Получаем токен провайдера
        provider_token = await DatabaseManager.get_setting(session, "payment_provider_token")
        currency = await DatabaseManager.get_setting(session, "payment_currency") or "USD"
        commission = await DatabaseManager.get_setting(session, "payment_commission") or "0"
    
    # Проверяем, настроена ли система
    token_status = "✅ Настроен" if provider_token else "❌ Не настроен"
    
    text = (
        "💳 <b>Настройки платежной системы</b>\n\n"
        "<b>SmartGlocal (Telegram Payments)</b>\n\n"
        f"🔑 <b>Статус:</b> {token_status}\n"
        f"💱 <b>Валюта:</b> {currency}\n"
        f"💼 <b>Комиссия:</b> {commission}%\n\n"
        "<b>Доступные методы оплаты:</b>\n"
        "• 💳 Банковские карты (Visa, MasterCard)\n"
        "• 🟢 Google Pay\n"
        "• 🍎 Apple Pay\n\n"
        "💡 <b>О SmartGlocal:</b>\n"
        "SmartGlocal - официальный партнёр Telegram для приёма платежей. "
        "Поддерживает автоматическое одобрение заявок после успешной оплаты.\n\n"
    )
    
    if not provider_token:
        text += (
            "⚠️ <b>Платежная система не настроена!</b>\n\n"
            "Для настройки:\n"
            "1. Зарегистрируйтесь на https://smart-glocal.com\n"
            "2. Получите Provider Token для Telegram\n"
            "3. Добавьте токен через кнопку ниже\n\n"
            "📖 Подробная инструкция в файле SMARTGLOCAL_SETUP.md"
        )
    else:
        text += "✅ Платежная система активна и готова к приёму платежей!"
    
    buttons = []
    
    if provider_token:
        buttons.append([
            InlineKeyboardButton(text="✏️ Изменить токен", callback_data="payment_change_token")
        ])
        buttons.append([
            InlineKeyboardButton(text="💱 Изменить валюту", callback_data="payment_change_currency"),
            InlineKeyboardButton(text="💼 Комиссия", callback_data="payment_change_commission")
        ])
        buttons.append([
            InlineKeyboardButton(text="🧪 Тестовый платёж", callback_data="payment_test")
        ])
        buttons.append([
            InlineKeyboardButton(text="❌ Удалить токен", callback_data="payment_remove_token")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="➕ Добавить токен", callback_data="payment_add_token")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="📖 Инструкция", callback_data="payment_instructions")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


class PaymentSettingsStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_currency = State()
    waiting_for_commission = State()


@router.callback_query(F.data == "payment_add_token")
async def payment_add_token_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления токена"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(PaymentSettingsStates.waiting_for_token)
    
    text = (
        "🔑 <b>Добавление Provider Token</b>\n\n"
        "Отправьте ваш Provider Token от SmartGlocal.\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Токен должен быть получен через @BotFather\n"
        "• Формат: обычно начинается с цифр\n"
        "• Храните токен в безопасности!\n\n"
        "📖 <b>Как получить токен:</b>\n"
        "1. Зарегистрируйтесь на https://smart-glocal.com\n"
        "2. Получите ключи API\n"
        "3. Настройте через @BotFather → Payments\n"
        "4. Выберите SmartGlocal как провайдера\n\n"
        "Отправьте /cancel для отмены"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(StateFilter(PaymentSettingsStates.waiting_for_token))
async def payment_add_token_process(message: Message, state: FSMContext):
    """Обработка нового токена"""
    user_id = message.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await message.answer("❌ Только для суперадминистратора")
        await state.clear()
        return
    
    token = message.text.strip()
    
    # Базовая валидация токена
    if len(token) < 20:
        await message.answer(
            "❌ Токен слишком короткий. Проверьте правильность.\n"
            "Отправьте корректный токен или /cancel для отмены."
        )
        return
    
    try:
        async with async_session_maker() as session:
            # Сохраняем токен
            await DatabaseManager.set_setting(session, "payment_provider_token", token)
            
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session=session,
                admin_id=user_id,
                action="add_payment_token",
                details=f"Добавлен Provider Token для платёжной системы (длина: {len(token)})"
            )
        
        # Удаляем сообщение с токеном для безопасности
        try:
            await message.delete()
        except:
            pass
        
        await message.answer(
            "✅ <b>Provider Token успешно добавлен!</b>\n\n"
            "Платёжная система SmartGlocal активирована.\n"
            "Пользователи теперь могут оплачивать депозиты онлайн.\n\n"
            "🔒 Ваше сообщение с токеном было удалено из соображений безопасности.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Настройки платежей", callback_data="admin_payment_settings")]
            ])
        )
        
        await state.clear()
        
        logger.info(f"SuperAdmin {user_id} добавил Provider Token")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения токена: {e}")
        await message.answer(
            "❌ Ошибка сохранения токена. Попробуйте снова.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_payment_settings")]
            ])
        )
        await state.clear()


@router.callback_query(F.data == "payment_change_token")
async def payment_change_token(callback: CallbackQuery, state: FSMContext):
    """Изменить токен (аналогично добавлению)"""
    await payment_add_token_start(callback, state)


@router.callback_query(F.data == "payment_remove_token")
async def payment_remove_token(callback: CallbackQuery):
    """Удалить токен"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    text = (
        "⚠️ <b>Удаление Provider Token</b>\n\n"
        "Вы уверены, что хотите удалить токен?\n\n"
        "После удаления:\n"
        "• Онлайн-оплата станет недоступна\n"
        "• Пользователи смогут только загружать чеки\n"
        "• Токен придётся добавлять заново\n\n"
        "Продолжить?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data="payment_remove_token_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_payment_settings")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "payment_remove_token_confirm")
async def payment_remove_token_confirm(callback: CallbackQuery):
    """Подтверждение удаления токена"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    try:
        async with async_session_maker() as session:
            # Удаляем токен
            await DatabaseManager.set_setting(session, "payment_provider_token", "")
            
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session=session,
                admin_id=user_id,
                action="remove_payment_token",
                details="Удалён Provider Token платёжной системы"
            )
        
        await callback.answer("✅ Токен удалён", show_alert=True)
        
        # Возвращаемся к настройкам
        await payment_settings(callback)
        
        logger.info(f"SuperAdmin {user_id} удалил Provider Token")
        
    except Exception as e:
        logger.error(f"Ошибка удаления токена: {e}")
        await callback.answer("❌ Ошибка удаления", show_alert=True)


@router.callback_query(F.data == "payment_test")
async def payment_test(callback: CallbackQuery):
    """Отправить тестовый платёж"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    text = (
        "🧪 <b>Тестовый платёж</b>\n\n"
        "Для тестирования платёжной системы используйте команду:\n"
        "<code>/test_payment</code>\n\n"
        "Вы получите тестовый invoice с суммой $10.\n\n"
        "📝 <b>Тестовые карты:</b>\n"
        "• 4242 4242 4242 4242 - успешная оплата\n"
        "• 4000 0000 0000 0002 - отклонена\n\n"
        "Любая дата истечения в будущем и любой CVC.\n\n"
        "⚠️ Тестовые платежи не создают реальных заявок."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "payment_instructions")
async def payment_instructions(callback: CallbackQuery):
    """Показать инструкцию по настройке"""
    await callback.answer()
    
    text = (
        "📖 <b>Инструкция по настройке SmartGlocal</b>\n\n"
        "<b>Шаг 1: Регистрация</b>\n"
        "• Перейдите на https://smart-glocal.com\n"
        "• Зарегистрируйте аккаунт\n"
        "• Подтвердите email и пройдите верификацию\n\n"
        "<b>Шаг 2: Получение ключей API</b>\n"
        "• В личном кабинете найдите раздел API\n"
        "• Создайте новый API ключ\n"
        "• Сохраните Public Key и Secret Key\n\n"
        "<b>Шаг 3: Настройка в Telegram</b>\n"
        "• Откройте диалог с @BotFather\n"
        "• Отправьте команду /mybots\n"
        "• Выберите вашего бота\n"
        "• Payments → SmartGlocal\n"
        "• Введите ваши ключи API\n"
        "• Получите Provider Token\n\n"
        "<b>Шаг 4: Добавление в бот</b>\n"
        "• Скопируйте Provider Token\n"
        "• Добавьте через эту админ-панель\n"
        "• Протестируйте платёж\n\n"
        "✅ Готово! Платёжная система активна.\n\n"
        "📄 Подробная инструкция: SMARTGLOCAL_SETUP.md"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть SmartGlocal", url="https://smart-glocal.com")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_payment_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


# ==================== НАСТРОЙКА ЯЗЫКОВ ====================

@router.callback_query(F.data == "admin_manage_languages")
async def manage_languages(callback: CallbackQuery):
    """Настройка доступных языков"""
    user_id = callback.from_user.id
    
    if not await check_superadmin_rights(user_id):
        await callback.answer("❌ Только для суперадминистратора", show_alert=True)
        return
    
    await callback.answer()
    
    from localization import LANGUAGES
    
    async with async_session_maker() as session:
        # Получаем настройки активных языков
        enabled_langs_json = await DatabaseManager.get_setting(session, "enabled_languages")
        
        if enabled_langs_json:
            try:
                enabled_langs = json.loads(enabled_langs_json)
            except:
                enabled_langs = list(LANGUAGES.keys())
        else:
            enabled_langs = list(LANGUAGES.keys())
    
    text = (
        "🌐 <b>Настройка языков</b>\n\n"
        "<b>Доступные языки в системе:</b>\n\n"
    )
    
    for lang_code, lang_name in LANGUAGES.items():
        status = "✅ Включен" if lang_code in enabled_langs else "❌ Выключен"
        text += f"• {lang_name} ({lang_code}): {status}\n"
    
    text += (
        "\n💡 <b>Информация:</b>\n"
        "Управление языками временно недоступно через интерфейс.\n"
        "Все языки активны по умолчанию.\n\n"
        "Для изменения обратитесь к разработчику."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

