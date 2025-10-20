"""
Улучшенные обработчики с системой навигации "Назад", индикатором прогресса,
детальным просмотром заявок, FAQ и исправлением загрузки файлов
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from config import ADMIN_IDS, UPLOAD_DIR, MAX_FILE_SIZE
from database import DatabaseManager, async_session_maker

# Google Sheets интеграция (опционально)
try:
    from google_sheets_integration import sync_application_to_sheets
    GOOGLE_SHEETS_ENABLED = True
except ImportError:
    GOOGLE_SHEETS_ENABLED = False
    logger.warning("Google Sheets интеграция недоступна")

from keyboards_enhanced import (
    get_main_menu_keyboard, get_deposit_amount_keyboard,
    get_confirm_data_keyboard, get_admin_keyboard,
    get_retry_keyboard, get_back_button, get_language_keyboard,
    get_faq_keyboard, get_application_details_keyboard,
    get_applications_list_keyboard, get_cancel_application_keyboard,
    get_payment_method_selection_keyboard
)
from localization import get_text, TRANSLATIONS, LANGUAGES

# Состояния для FSM
class DepositStates(StatesGroup):
    waiting_for_deposit_choice = State()
    waiting_for_custom_amount = State()
    waiting_for_login = State()
    waiting_for_confirmation = State()
    waiting_for_payment_file = State()

class AdminStates(StatesGroup):
    waiting_for_codes_amount = State()
    waiting_for_codes_file = State()

# Роутер
router = Router()

# Хранилище временных данных и истории навигации
user_data: Dict[int, Dict[str, Any]] = {}
user_navigation_history: Dict[int, List[str]] = {}
user_timeouts: Dict[int, asyncio.Task] = {}

# Создаем директорию uploads при импорте модуля
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)

def add_to_history(user_id: int, state_name: str):
    """Добавить состояние в историю навигации"""
    if user_id not in user_navigation_history:
        user_navigation_history[user_id] = []
    user_navigation_history[user_id].append(state_name)

def get_previous_state(user_id: int) -> str:
    """Получить предыдущее состояние"""
    if user_id not in user_navigation_history or len(user_navigation_history[user_id]) < 2:
        return "menu"
    # Удаляем текущее состояние
    user_navigation_history[user_id].pop()
    # Возвращаем предыдущее
    return user_navigation_history[user_id].pop() if user_navigation_history[user_id] else "menu"

def clear_history(user_id: int):
    """Очистить историю навигации"""
    if user_id in user_navigation_history:
        user_navigation_history[user_id] = []

def get_progress_indicator(step: int, total: int = 4) -> str:
    """Индикатор прогресса"""
    indicators = ["○"] * total
    for i in range(step):
        indicators[i] = "●"
    return " ".join(indicators) + f" ({step}/{total})"

async def cancel_timeout(user_id: int):
    """Отменить таймаут для пользователя"""
    if user_id in user_timeouts:
        user_timeouts[user_id].cancel()
        del user_timeouts[user_id]

async def timeout_handler(user_id: int, state: FSMContext, bot, lang: str):
    """Обработчик таймаута (15 минут)"""
    await asyncio.sleep(900)  # 15 минут
    
    try:
        await state.clear()
        if user_id in user_data:
            del user_data[user_id]
        clear_history(user_id)
        
        await bot.send_message(
            user_id,
            get_text("timeout_expired", lang),
            reply_markup=get_main_menu_keyboard(lang)
        )
        
        logger.info(f"Таймаут для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка в timeout_handler: {e}")
    finally:
        if user_id in user_timeouts:
            del user_timeouts[user_id]

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start с приветствием и выбором языка для новых пользователей"""
    user_id = message.from_user.id
    user_name = message.from_user.full_name or message.from_user.username or f"User{user_id}"
    
    await state.clear()
    await cancel_timeout(user_id)
    clear_history(user_id)
    
    async with async_session_maker() as session:
        is_first = await DatabaseManager.is_first_time(session, user_id)
        
        if is_first:
            # Первый запуск - показываем приветствие и выбор языка (без кнопки "Назад")
            welcome_text = TRANSLATIONS["first_welcome"]["multi"]
            await message.answer(
                welcome_text,
                reply_markup=get_language_keyboard(show_back=False),
                parse_mode="HTML"
            )
        else:
            # Повторный запуск - показываем главное меню
            lang = await DatabaseManager.get_user_language(session, user_id)
            await message.answer(
                get_text("welcome_message", lang, name=user_name),
                reply_markup=get_main_menu_keyboard(lang)
            )

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """Команда /menu"""
    user_id = message.from_user.id
    
    await state.clear()
    await cancel_timeout(user_id)
    clear_history(user_id)
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    await message.answer(
        get_text("menu_welcome", lang),
        reply_markup=get_main_menu_keyboard(lang)
    )

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    await state.clear()
    await cancel_timeout(user_id)
    clear_history(user_id)
    if user_id in user_data:
        del user_data[user_id]
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    await callback.message.edit_text(
        get_text("menu_welcome", lang),
        reply_markup=get_main_menu_keyboard(lang)
    )

@router.callback_query(F.data == "go_back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Возврат на предыдущий шаг"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    previous = get_previous_state(user_id)
    
    if previous == "menu":
        # back_to_menu сам вызовет callback.answer()
        await back_to_menu(callback, state)
    elif previous == "amount_choice":
        await callback.answer()
        await state.set_state(DepositStates.waiting_for_deposit_choice)
        await callback.message.edit_text(
            f"📍 {get_progress_indicator(1)}\n\n" + get_text("choose_amount", lang),
            reply_markup=get_deposit_amount_keyboard(lang)
        )
    elif previous == "login":
        await callback.answer()
        add_to_history(user_id, "amount_choice")
        await state.set_state(DepositStates.waiting_for_login)
        amount = user_data.get(user_id, {}).get("amount", 0)
        await callback.message.edit_text(
            f"📍 {get_progress_indicator(2)}\n\n" + get_text("enter_login", lang, amount=amount)
        )

@router.callback_query(F.data == "menu_deposit")
async def menu_deposit(callback: CallbackQuery, state: FSMContext):
    """Начало процесса депозита - выбор метода оплаты"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        can_proceed, error_message = await DatabaseManager.check_user_rate_limit(session, user_id)
        lang = await DatabaseManager.get_user_language(session, user_id)
        
        if not can_proceed:
            await callback.answer("❌ Лимит достигнут", show_alert=True)
            await callback.message.edit_text(
                f"❌ {error_message}",
                reply_markup=get_back_button(lang)
            )
            return
    
    await callback.answer()
    
    clear_history(user_id)
    add_to_history(user_id, "menu")
    add_to_history(user_id, "payment_method_choice")
    
    # Показываем выбор метода оплаты
    text = get_text("payment_method_selection", lang)
    
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_method_selection_keyboard(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "payment_method_manual")
async def payment_method_manual(callback: CallbackQuery, state: FSMContext):
    """Ручной способ оплаты - загрузка чека"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    await callback.answer()
    add_to_history(user_id, "amount_choice")
    
    await state.set_state(DepositStates.waiting_for_deposit_choice)
    
    await callback.message.edit_text(
        f"📍 {get_progress_indicator(1)}\n\n" + get_text("choose_amount", lang),
        reply_markup=get_deposit_amount_keyboard(lang)
    )

@router.callback_query(F.data == "payment_method_online")
async def payment_method_online(callback: CallbackQuery):
    """Онлайн-оплата через SmartGlocal"""
    # Перенаправляем на обработчик онлайн-оплаты из payments_integration
    from payments_integration import start_payment_deposit
    await start_payment_deposit(callback)

@router.callback_query(F.data == "menu_applications")
async def menu_applications(callback: CallbackQuery):
    """Показать заявки пользователя (с возможностью клика)"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
        applications = await DatabaseManager.get_user_applications(session, user_id)
        
        if not applications:
            await callback.message.edit_text(
                "📋 У вас пока нет заявок на депозит.",
                reply_markup=get_back_button(lang)
            )
            return
        
        await callback.message.edit_text(
            "📋 Ваши заявки:\n\nНажмите на заявку для просмотра деталей:",
            reply_markup=get_applications_list_keyboard(applications[:10], lang)
        )

@router.callback_query(F.data.startswith("view_app_"))
async def view_application_details(callback: CallbackQuery):
    """Просмотр деталей заявки"""
    user_id = callback.from_user.id
    app_id = int(callback.data.split("_")[2])
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
        application = await DatabaseManager.get_application_by_id(session, app_id)
        
        if not application or application.user_id != user_id:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        await callback.answer()  # Отвечаем после проверки
        
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "needs_info": "💬"
        }.get(application.status, "❓")
        
        status_name = {
            "pending": "Ожидает проверки",
            "approved": "Подтверждена",
            "rejected": "Отклонена",
            "needs_info": "Требует доп. информации"
        }.get(application.status, "Неизвестно")
        
        details_text = (
            f"{status_emoji} <b>Заявка #{application.id}</b>\n\n"
            f"💰 <b>Сумма:</b> {application.amount} {application.currency}\n"
            f"👤 <b>Логин:</b> {application.login}\n"
            f"📊 <b>Статус:</b> {status_name}\n"
            f"🕒 <b>Создана:</b> {application.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        if application.updated_at and application.updated_at != application.created_at:
            details_text += f"🔄 <b>Обновлена:</b> {application.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if application.admin_comment:
            details_text += f"\n💬 <b>Комментарий админа:</b>\n{application.admin_comment}\n"
        
        if application.activation_code and application.activation_code.code_value:
            details_text += f"\n🎟️ <b>Код активации:</b> <code>{application.activation_code.code_value}</code>\n"
        
        # Отправляем файл, если есть
        try:
            await callback.bot.send_document(
                user_id,
                application.file_id,
                caption="📎 Ваш загруженный документ"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить файл: {e}")
        
        await callback.message.edit_text(
            details_text,
            reply_markup=get_application_details_keyboard(application, lang),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("cancel_app_"))
async def cancel_application(callback: CallbackQuery):
    """Отмена заявки пользователем"""
    user_id = callback.from_user.id
    app_id = int(callback.data.split("_")[2])
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
        application = await DatabaseManager.get_application_by_id(session, app_id)
        
        if not application or application.user_id != user_id:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        if application.status != "pending":
            await callback.answer("❌ Можно отменить только заявки в статусе 'Ожидает'", show_alert=True)
            return
        
        # Успешная проверка - отвечаем
        
        # Обновляем статус на "cancelled"
        await DatabaseManager.update_application_status(
            session=session,
            application_id=app_id,
            status="cancelled",
            admin_comment="Отменена пользователем"
        )
        
        await DatabaseManager.log_transaction(
            session=session,
            application_id=app_id,
            action="cancelled",
            comment=f"Отменена пользователем {user_id}"
        )
    
    await callback.answer("✅ Заявка отменена", show_alert=True)
    await callback.message.edit_text(
        f"❌ <b>Заявка #{app_id} отменена</b>\n\nВы можете создать новую заявку через главное меню.",
        reply_markup=get_back_button(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_faq")
async def menu_faq(callback: CallbackQuery):
    """FAQ раздел"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    faq_text = (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        
        "<b>1. Как сделать депозит?</b>\n"
        "   • Выберите 'Сделать депозит'\n"
        "   • Укажите сумму и логин\n"
        "   • Загрузите скриншот оплаты\n"
        "   • Дождитесь проверки\n\n"
        
        "<b>2. Сколько времени проверка?</b>\n"
        "   • Обычно 5-30 минут\n"
        "   • В часы пик до 2 часов\n\n"
        
        "<b>3. Какие файлы принимаются?</b>\n"
        "   • JPG, PNG (скриншоты)\n"
        "   • PDF (документы)\n"
        "   • Максимум 10 МБ\n\n"
        
        "<b>4. Что делать если отклонили?</b>\n"
        "   • Проверьте скриншот\n"
        "   • Убедитесь что видны все данные\n"
        "   • Попробуйте снова\n\n"
        
        "<b>5. Лимиты заявок?</b>\n"
        "   • Максимум 3 заявки в день\n"
        "   • 1 заявка в минуту\n\n"
        
        "<b>6. Можно ли отменить заявку?</b>\n"
        "   • Да, пока статус 'Ожидает'\n"
        "   • Зайдите в 'Мои заявки'\n"
        "   • Нажмите на заявку и 'Отменить'\n\n"
    )
    
    await callback.message.edit_text(
        faq_text,
        reply_markup=get_faq_keyboard(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery):
    """Меню поддержки"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    support_text = (
        "💬 <b>Служба поддержки</b>\n\n"
        "📞 <b>Способы связи:</b>\n\n"
        "• Telegram: @support_username\n"
        "• Email: support@example.com\n"
        "• Время работы: 24/7\n\n"
        "⚡ <b>Средний ответ:</b> 15 минут\n\n"
        "💡 <b>Перед обращением:</b>\n"
        "• Проверьте FAQ\n"
        "• Укажите номер заявки\n"
        "• Опишите проблему подробно\n\n"
        "📋 <b>Команды бота:</b>\n"
        "/start - Главное меню\n"
        "/menu - Показать меню\n"
        "/status - Мои заявки\n"
        "/help - Справка\n"
    )
    
    await callback.message.edit_text(
        support_text,
        reply_markup=get_back_button(lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_language")
async def menu_language(callback: CallbackQuery):
    """Меню выбора языка"""
    await callback.answer()  # Отвечаем сразу
    
    await callback.message.edit_text(
        "🌐 Выберите язык / Choose language / زبان منتخب کریں:",
        reply_markup=get_language_keyboard()
    )

@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    """Установка языка"""
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name or callback.from_user.username or f"User{user_id}"
    lang = callback.data.split("_")[1]
    
    # Отвечаем будет в конце с сообщением
    
    async with async_session_maker() as session:
        is_first = await DatabaseManager.is_first_time(session, user_id)
        await DatabaseManager.set_user_language(session, user_id, lang)
        
        if is_first:
            # Первый раз - отмечаем и показываем приветствие с именем
            await DatabaseManager.mark_not_first_time(session, user_id)
            
            welcome_text = get_text("welcome_message", lang, name=user_name)
            await callback.message.edit_text(
                welcome_text,
                reply_markup=get_main_menu_keyboard(lang)
            )
            await callback.answer(f"✅ {LANGUAGES[lang]}")
        else:
            # Смена языка - просто обновляем меню
            await callback.message.edit_text(
                get_text("menu_welcome", lang),
                reply_markup=get_main_menu_keyboard(lang)
            )
            await callback.answer(f"✅ {get_text('menu_change_language', lang)}")

@router.callback_query(F.data.startswith("amount_"))
async def process_amount_selection(callback: CallbackQuery, state: FSMContext):
    """Выбор суммы депозита"""
    user_id = callback.from_user.id
    amount_str = callback.data.split("_")[1]
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    if amount_str == "custom":
        add_to_history(user_id, "custom_amount")
        await state.set_state(DepositStates.waiting_for_custom_amount)
        await callback.message.edit_text(
            f"📍 {get_progress_indicator(1)}\n\n" + get_text("enter_custom_amount", lang),
            reply_markup=get_back_button(lang, show_back=True)
        )
    else:
        try:
            amount = float(amount_str)
            user_data[user_id] = {"amount": amount}
            add_to_history(user_id, "login")
            await state.set_state(DepositStates.waiting_for_login)
            
            await callback.message.edit_text(
                f"📍 {get_progress_indicator(2)}\n\n" + get_text("enter_login", lang, amount=amount)
            )
        except ValueError:
            await callback.answer(get_text("error_invalid_amount", lang), show_alert=True)

@router.message(StateFilter(DepositStates.waiting_for_custom_amount))
async def process_custom_amount(message: Message, state: FSMContext):
    """Обработка пользовательской суммы"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    try:
        amount = float(message.text.strip().replace(",", "."))
        
        if amount <= 0:
            await message.answer(get_text("error_invalid_amount", lang))
            return
        
        if amount > 10000:
            await message.answer("❌ Максимальная сумма: 10,000 USD")
            return
        
        user_data[user_id] = {"amount": amount}
        add_to_history(user_id, "login")
        await state.set_state(DepositStates.waiting_for_login)
        
        await message.answer(
            f"📍 {get_progress_indicator(2)}\n\n" + get_text("enter_login", lang, amount=amount)
        )
        
    except ValueError:
        await message.answer(get_text("error_invalid_amount", lang))

@router.message(StateFilter(DepositStates.waiting_for_login))
async def process_login_input(message: Message, state: FSMContext):
    """Обработка ввода логина"""
    user_id = message.from_user.id
    login = message.text.strip()
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    if len(login) < 3:
        await message.answer("❌ Логин должен содержать минимум 3 символа")
        return
    
    if len(login) > 50:
        await message.answer("❌ Логин слишком длинный (максимум 50 символов)")
        return
    
    user_data[user_id]["login"] = login
    add_to_history(user_id, "confirmation")
    await state.set_state(DepositStates.waiting_for_confirmation)
    
    # Показываем подтверждение данных
    await message.answer(
        f"📍 {get_progress_indicator(3)}\n\n" + 
        get_text("confirm_data", lang,
                amount=user_data[user_id]["amount"],
                login=login),
        reply_markup=get_confirm_data_keyboard(lang)
    )

@router.callback_query(F.data == "confirm_yes")
async def confirm_data_yes(callback: CallbackQuery, state: FSMContext):
    """Подтверждение данных - переход к загрузке файла"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    add_to_history(user_id, "upload")
    await state.set_state(DepositStates.waiting_for_payment_file)
    
    # Запускаем таймаут 15 минут
    timeout_task = asyncio.create_task(
        timeout_handler(user_id, state, callback.bot, lang)
    )
    user_timeouts[user_id] = timeout_task
    
    await callback.message.edit_text(
        f"📍 {get_progress_indicator(4)}\n\n" + get_text("upload_file", lang)
    )

@router.callback_query(F.data == "confirm_change")
async def confirm_data_change(callback: CallbackQuery, state: FSMContext):
    """Изменение данных - возврат к выбору суммы"""
    user_id = callback.from_user.id
    
    await callback.answer()  # Отвечаем сразу
    
    if user_id in user_data:
        del user_data[user_id]
    
    # Очищаем историю до выбора суммы
    clear_history(user_id)
    add_to_history(user_id, "menu")
    add_to_history(user_id, "amount_choice")
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    await state.set_state(DepositStates.waiting_for_deposit_choice)
    
    await callback.message.edit_text(
        f"📍 {get_progress_indicator(1)}\n\n" + get_text("choose_amount", lang),
        reply_markup=get_deposit_amount_keyboard(lang)
    )

@router.message(StateFilter(DepositStates.waiting_for_payment_file))
async def process_payment_file(message: Message, state: FSMContext):
    """Обработка загрузки файла подтверждения"""
    user_id = message.from_user.id
    
    logger.info(f"Пользователь {user_id} отправил файл для заявки")
    
    await cancel_timeout(user_id)
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    # Получаем файл
    file_to_download = None
    file_name = None
    
    if message.document:
        logger.info(f"Получен документ от {user_id}: {message.document.file_name}, размер: {message.document.file_size}")
        
        if message.document.file_size > MAX_FILE_SIZE:
            await message.answer(get_text("error_file_too_large", lang))
            return
        
        file_to_download = message.document
        file_name = message.document.file_name
    elif message.photo:
        largest_photo = max(message.photo, key=lambda x: x.file_size)
        logger.info(f"Получено фото от {user_id}, размер: {largest_photo.file_size}")
        
        if largest_photo.file_size > MAX_FILE_SIZE:
            await message.answer(get_text("error_file_too_large", lang))
            return
        
        file_to_download = largest_photo
        file_name = f"photo_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    else:
        logger.warning(f"Пользователь {user_id} отправил неподдерживаемый тип файла")
        await message.answer(get_text("error_invalid_file", lang))
        return
    
    try:
        # Убедимся что директория существует
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        logger.info(f"Директория {UPLOAD_DIR} создана/проверена")
        
        # Скачиваем файл
        logger.info(f"Начинаем загрузку файла для пользователя {user_id}")
        file_path = os.path.join(UPLOAD_DIR, file_name)
        logger.info(f"Путь для сохранения: {file_path}")
        
        # ИСПРАВЛЕНИЕ: используем правильный метод загрузки для aiogram 3.x
        await message.bot.download(
            file=file_to_download,
            destination=file_path
        )
        
        logger.info(f"✅ Файл успешно загружен: {file_path}")
        
        # Проверяем данные пользователя
        if user_id not in user_data:
            logger.error(f"Данные пользователя {user_id} не найдены в user_data")
            await message.answer(
                "❌ Ошибка: данные заявки не найдены. Пожалуйста, начните заново.",
                reply_markup=get_main_menu_keyboard(lang)
            )
            await state.clear()
            return
        
        logger.info(f"Создаем заявку для пользователя {user_id}")
        
        # Создаем заявку
        async with async_session_maker() as session:
            application = await DatabaseManager.create_application(
                session=session,
                user_id=user_id,
                user_name=message.from_user.full_name or message.from_user.username or f"User{user_id}",
                login=user_data[user_id]["login"],
                amount=user_data[user_id]["amount"],
                file_id=file_to_download.file_id
            )
            
            logger.info(f"✅ Заявка #{application.id} создана в базе данных")
            
            # Логируем создание
            await DatabaseManager.log_transaction(
                session=session,
                application_id=application.id,
                action="created",
                comment=f"Создана пользователем {user_id}"
            )
            
            # Обновляем лимиты
            await DatabaseManager.update_user_rate_limit(session, user_id)
            
            lang = await DatabaseManager.get_user_language(session, user_id)
        
        # Синхронизируем с Google Sheets (если включено)
        if GOOGLE_SHEETS_ENABLED:
            try:
                await sync_application_to_sheets(application, is_new=True)
                logger.info(f"✅ Заявка #{application.id} синхронизирована с Google Sheets")
            except Exception as e:
                logger.error(f"Ошибка синхронизации с Google Sheets: {e}")
        
        logger.info(f"Отправляем уведомления админам о заявке #{application.id}")
        
        # Уведомляем админов
        await notify_admins(message.bot, application, file_to_download.file_id)
        
        # Очищаем данные
        if user_id in user_data:
            del user_data[user_id]
        clear_history(user_id)
        
        await state.clear()
        
        logger.info(f"Отправляем подтверждение пользователю {user_id}")
        
        await message.answer(
            get_text("application_created", lang,
                    app_id=application.id,
                    amount=application.amount,
                    login=application.login),
            reply_markup=get_main_menu_keyboard(lang)
        )
        
        logger.info(f"✅ Заявка #{application.id} успешно обработана для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await message.answer(
            f"❌ Произошла ошибка при загрузке файла.\n\nОшибка: {str(e)}\n\nПопробуйте:\n• Отправить файл как документ\n• Использовать другой формат\n• Уменьшить размер файла",
            reply_markup=get_main_menu_keyboard(lang)
        )

async def notify_admins(bot, application, file_id):
    """Уведомление админов о новой заявке"""
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, application.user_id)
    
    notification_text = get_text("admin_new_application", lang,
                                app_id=application.id,
                                user_name=application.user_name,
                                user_id=application.user_id,
                                amount=application.amount,
                                login=application.login,
                                time=application.created_at.strftime('%d.%m.%Y %H:%M'))
    
    for admin_id in ADMIN_IDS:
        try:
            # Отправляем уведомление с клавиатурой
            msg = await bot.send_message(
                admin_id,
                notification_text,
                reply_markup=get_admin_keyboard(application.id, lang),
                parse_mode="HTML"
            )
            
            # Отправляем файл админу отдельным сообщением
            if file_id:
                try:
                    await bot.send_document(admin_id, file_id)
                    logger.info(f"Файл отправлен админу {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки файла админу {admin_id}: {e}")
                    try:
                        # Попробуем отправить как фото, если это изображение
                        await bot.send_photo(admin_id, file_id)
                        logger.info(f"Фото отправлено админу {admin_id}")
                    except Exception as e2:
                        logger.error(f"Ошибка отправки фото админу {admin_id}: {e2}")
            
            logger.info(f"Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

@router.callback_query(F.data.startswith("admin_"))
async def process_admin_action(callback: CallbackQuery):
    """Обработка админских действий"""
    # Проверяем права администратора через базу данных
    async with async_session_maker() as session:
        is_admin = await DatabaseManager.is_admin(session, callback.from_user.id)
    
    # Также проверяем в config.ADMIN_IDS (обратная совместимость)
    if not is_admin and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    # Отвечаем будет внутри в зависимости от действия
    
    parts = callback.data.split("_")
    
    # Проверяем, что это действие с конкретной заявкой (имеет формат admin_action_id)
    if len(parts) < 3:
        # Это навигационный callback, пропускаем (обрабатывается в admin_enhanced.py)
        return
    
    action = parts[1]
    try:
        application_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный формат callback", show_alert=True)
        return
    
    async with async_session_maker() as session:
        application = await DatabaseManager.get_application_by_id(session, application_id)
        
        if not application:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        user_lang = await DatabaseManager.get_user_language(session, application.user_id)
        
        if action == "approve":
            await callback.answer("✅ Одобряю заявку...")
            
            # Подтверждение
            code = await DatabaseManager.get_activation_code(session, float(application.amount))
            
            if not code:
                await callback.message.edit_text(
                    f"⚠️ Коды для {application.amount} USD закончились!"
                )
                return
            
            await DatabaseManager.update_application_status(
                session=session,
                application_id=application_id,
                status="approved",
                admin_id=callback.from_user.id,
                activation_code_id=code.id
            )
            
            await DatabaseManager.mark_code_as_used(session, code.id)
            
            # Логируем
            await DatabaseManager.log_transaction(
                session=session,
                application_id=application_id,
                action="approved",
                admin_id=callback.from_user.id,
                comment=f"Выдан код {code.code_value}"
            )
            
            # Синхронизируем с Google Sheets
            if GOOGLE_SHEETS_ENABLED:
                try:
                    # Получаем обновленную заявку
                    updated_app = await DatabaseManager.get_application_by_id(session, application_id)
                    await sync_application_to_sheets(updated_app, is_new=False)
                    logger.info(f"✅ Заявка #{application_id} (одобрена) синхронизирована с Google Sheets")
                except Exception as e:
                    logger.error(f"Ошибка синхронизации с Google Sheets: {e}")
            
            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    application.user_id,
                    get_text("status_approved", user_lang,
                            app_id=application_id,
                            code=code.code_value),
                    reply_markup=get_main_menu_keyboard(user_lang)
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя: {e}")
            
            await callback.message.edit_text(
                f"✅ Заявка #{application_id} подтверждена!\n"
                f"🎟️ Код: {code.code_value}"
            )
            
        elif action == "reject":
            await callback.answer("❌ Отклоняю заявку...")
            
            # Отклонение
            await DatabaseManager.update_application_status(
                session=session,
                application_id=application_id,
                status="rejected",
                admin_id=callback.from_user.id,
                admin_comment="Отклонено администратором"
            )
            
            await DatabaseManager.log_transaction(
                session=session,
                application_id=application_id,
                action="rejected",
                admin_id=callback.from_user.id
            )
            
            # Синхронизируем с Google Sheets
            if GOOGLE_SHEETS_ENABLED:
                try:
                    # Получаем обновленную заявку
                    updated_app = await DatabaseManager.get_application_by_id(session, application_id)
                    await sync_application_to_sheets(updated_app, is_new=False)
                    logger.info(f"✅ Заявка #{application_id} (отклонена) синхронизирована с Google Sheets")
                except Exception as e:
                    logger.error(f"Ошибка синхронизации с Google Sheets: {e}")
            
            # Уведомляем пользователя с предложением повторить
            try:
                await callback.bot.send_message(
                    application.user_id,
                    get_text("status_rejected", user_lang,
                            app_id=application_id,
                            reason="Проверка не пройдена"),
                    reply_markup=get_retry_keyboard(user_lang)
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя: {e}")
            
            await callback.message.edit_text(f"❌ Заявка #{application_id} отклонена")
        
        elif action == "history":
            # История заявки
            await callback.answer("📋 Загружаю историю...")
            
            history = await DatabaseManager.get_transaction_history(session, application_id)
            
            history_text = f"📋 История заявки #{application_id}:\n\n"
            
            for transaction in history:
                history_text += (
                    f"• {transaction.action.upper()}\n"
                    f"  Время: {transaction.timestamp.strftime('%d.%m %H:%M')}\n"
                )
                if transaction.admin_id:
                    history_text += f"  Админ: {transaction.admin_id}\n"
                if transaction.comment:
                    history_text += f"  Комментарий: {transaction.comment}\n"
                history_text += "\n"
            
            await callback.answer(history_text[:4000], show_alert=True)
        else:
            # Неизвестное действие
            await callback.answer("❓ Неизвестное действие", show_alert=True)

@router.callback_query(F.data == "retry_yes")
async def retry_application(callback: CallbackQuery, state: FSMContext):
    """Повторная попытка после отклонения"""
    # callback.answer() будет вызван в menu_deposit
    await menu_deposit(callback, state)

@router.callback_query(F.data == "retry_no")
async def retry_no(callback: CallbackQuery, state: FSMContext):
    """Отказ от повторной попытки"""
    # callback.answer() будет вызван в back_to_menu
    await back_to_menu(callback, state)

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
        applications = await DatabaseManager.get_user_applications(session, user_id)
        
        if not applications:
            await message.answer(
                "📋 У вас нет заявок.",
                reply_markup=get_main_menu_keyboard(lang)
            )
            return
        
        for app in applications[:5]:
            if app.status == "approved" and app.activation_code:
                text = get_text("status_approved", lang,
                              app_id=app.id,
                              code=app.activation_code.code_value)
            elif app.status == "rejected":
                text = get_text("status_rejected", lang,
                              app_id=app.id,
                              reason=app.admin_comment or "Не указана")
            else:
                text = get_text("status_pending", lang, app_id=app.id)
            
            await message.answer(text)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    help_text = (
        "🤖 <b>Справка по боту</b>\n\n"
        
        "📋 <b>Команды:</b>\n"
        "/start - Главное меню\n"
        "/menu - Показать меню\n"
        "/status - Мои заявки\n"
        "/help - Эта справка\n\n"
        
        "💡 <b>Как работает бот:</b>\n"
        "1️⃣ Выберите сумму депозита\n"
        "2️⃣ Введите ваш логин\n"
        "3️⃣ Подтвердите данные\n"
        "4️⃣ Загрузите скриншот\n"
        "5️⃣ Дождитесь проверки\n\n"
        
        "⚡ <b>Лимиты:</b>\n"
        "• 3 заявки в день\n"
        "• 1 заявка в минуту\n\n"
        
        "❓ Для FAQ нажмите кнопку в меню"
    )
    
    await message.answer(help_text, parse_mode="HTML")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика для админа"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав")
        return
    
    async with async_session_maker() as session:
        stats = await DatabaseManager.get_stats(session, days=1)
    
    stats_text = (
        "📊 <b>Статистика за сегодня:</b>\n\n"
        f"📋 Всего заявок: <b>{stats['total']}</b>\n"
        f"✅ Подтверждено: <b>{stats['confirmed']}</b>\n"
        f"❌ Отклонено: <b>{stats['rejected']}</b>\n"
        f"⏳ Ожидает: <b>{stats['pending']}</b>\n\n"
        f"🎟️ <b>Осталось кодов:</b>\n"
    )
    
    for amount, count in stats['codes_remaining'].items():
        emoji = "🔴" if count < 3 else "🟡" if count < 5 else "🟢"
        stats_text += f"{emoji} ${amount} USD — <b>{count}</b> шт.\n"
    
    await message.answer(stats_text, parse_mode="HTML")

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("Нечего отменять.")
        return
    
    await state.clear()
    await cancel_timeout(user_id)
    clear_history(user_id)
    if user_id in user_data:
        del user_data[user_id]
    
    async with async_session_maker() as session:
        lang = await DatabaseManager.get_user_language(session, user_id)
    
    await message.answer(
        "❌ Операция отменена.",
        reply_markup=get_main_menu_keyboard(lang)
    )

