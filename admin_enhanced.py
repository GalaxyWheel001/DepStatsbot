"""
Расширенная админ-панель с фильтрами, поиском и аналитикой
"""
from datetime import datetime, timedelta
from typing import Optional, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from config import ADMIN_IDS
from database import DatabaseManager, async_session_maker, Application

router = Router()

# Состояния фильтров для каждого админа
admin_filters = {}

# Состояния для управления администраторами
class AdminManagementStates(StatesGroup):
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()

# Состояния для управления кодами активации
class CodesManagementStates(StatesGroup):
    waiting_for_code_to_add = State()
    waiting_for_amount_for_code = State()
    waiting_for_code_id_to_delete = State()
    waiting_for_csv_file = State()

# Состояния для управления номиналами депозита
class DepositAmountsStates(StatesGroup):
    waiting_for_new_amounts = State()

# ==================== HELPER ФУНКЦИИ ====================

async def check_admin_rights(user_id: int) -> bool:
    """
    Проверка прав администратора через базу данных
    Возвращает True, если пользователь является администратором
    """
    # Сначала проверяем в config.ADMIN_IDS (обратная совместимость)
    if user_id in ADMIN_IDS:
        return True
    
    # Проверяем в базе данных
    async with async_session_maker() as session:
        return await DatabaseManager.is_admin(session, user_id)

async def check_superadmin_rights(user_id: int) -> bool:
    """
    Проверка прав суперадминистратора через базу данных
    Возвращает True, если пользователь является суперадминистратором
    """
    async with async_session_maker() as session:
        return await DatabaseManager.is_superadmin(session, user_id)

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главная админ-панель"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Все заявки", callback_data="admin_all"),
            InlineKeyboardButton(text="⏳ Ожидают", callback_data="admin_pending")
        ],
        [
            InlineKeyboardButton(text="✅ Одобренные", callback_data="admin_approved"),
            InlineKeyboardButton(text="❌ Отклоненные", callback_data="admin_rejected")
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_search"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📥 Экспорт в Google Sheets", callback_data="admin_export_sheets")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_refresh")
        ]
    ])
    return keyboard

def get_application_admin_keyboard(app_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для работы с заявкой"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_{app_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{app_id}")
        ],
        [
            InlineKeyboardButton(text="💬 Запросить инфо", callback_data=f"admin_info_{app_id}"),
            InlineKeyboardButton(text="📋 История", callback_data=f"admin_history_{app_id}")
        ],
        [
            InlineKeyboardButton(text="📎 Файл", callback_data=f"admin_file_{app_id}"),
            InlineKeyboardButton(text="👤 Профиль юзера", callback_data=f"admin_user_{app_id}")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к списку", callback_data="admin_pending")
        ]
    ])
    return keyboard

def get_filter_keyboard(current_filter: str = "all") -> InlineKeyboardMarkup:
    """Клавиатура фильтров"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'✅' if current_filter == 'today' else ''} Сегодня",
                callback_data="filter_today"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if current_filter == 'week' else ''} Неделя",
                callback_data="filter_week"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅' if current_filter == 'month' else ''} Месяц",
                callback_data="filter_month"
            ),
            InlineKeyboardButton(
                text=f"{'✅' if current_filter == 'all' else ''} Все",
                callback_data="filter_all"
            )
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
        ]
    ])
    return keyboard

def format_application(app: Application, detailed: bool = False) -> str:
    """Форматирование информации о заявке"""
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
        "cancelled": "🚫",
        "needs_info": "💬"
    }.get(app.status, "❓")
    
    status_name = {
        "pending": "Ожидает",
        "approved": "Одобрена",
        "rejected": "Отклонена",
        "cancelled": "Отменена",
        "needs_info": "Требует инфо"
    }.get(app.status, "Неизвестно")
    
    text = f"{status_emoji} <b>Заявка #{app.id}</b>\n\n"
    
    if detailed:
        text += (
            f"👤 <b>Пользователь:</b> {app.user_name}\n"
            f"🆔 <b>User ID:</b> <code>{app.user_id}</code>\n"
            f"💰 <b>Сумма:</b> {app.amount} {app.currency}\n"
            f"🔑 <b>Логин:</b> {app.login}\n"
            f"📊 <b>Статус:</b> {status_name}\n"
            f"📅 <b>Создана:</b> {app.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        if app.updated_at and app.updated_at != app.created_at:
            text += f"🔄 <b>Обновлена:</b> {app.updated_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        if app.admin_id:
            text += f"👨‍💼 <b>Обработал админ:</b> {app.admin_id}\n"
        
        if app.admin_comment:
            text += f"💬 <b>Комментарий:</b> {app.admin_comment}\n"
        
        if app.activation_code:
            text += f"🎟️ <b>Код:</b> <code>{app.activation_code.code_value}</code>\n"
        
        # Время ожидания
        if app.status == "pending":
            waiting_time = datetime.utcnow() - app.created_at
            hours = int(waiting_time.total_seconds() // 3600)
            minutes = int((waiting_time.total_seconds() % 3600) // 60)
            text += f"\n⏱️ <b>Ожидает:</b> {hours}ч {minutes}мин\n"
    else:
        # Краткая версия для списка
        text = (
            f"{status_emoji} <b>#{app.id}</b> | "
            f"{app.amount} {app.currency} | "
            f"{app.user_name} | "
            f"{app.created_at.strftime('%d.%m %H:%M')}"
        )
    
    return text

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    """Главная админ-панель"""
    if not await check_admin_rights(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    async with async_session_maker() as session:
        # Быстрая статистика
        stats = await DatabaseManager.get_stats(session, days=1)
        
        pending_count = stats['pending']
        today_count = stats['total']
        
        text = (
            "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            f"📊 <b>Быстрая статистика за сегодня:</b>\n"
            f"• Всего заявок: {today_count}\n"
            f"• Ожидают проверки: <b>{pending_count}</b>\n"
            f"• Одобрено: {stats['confirmed']}\n"
            f"• Отклонено: {stats['rejected']}\n\n"
            f"🎟️ <b>Коды активации:</b>\n"
        )
        
        for amount, count in stats['codes_remaining'].items():
            emoji = "🔴" if count < 3 else "🟡" if count < 5 else "🟢"
            text += f"{emoji} ${amount} USD — {count} шт.\n"
        
        text += "\n💡 Выберите действие:"
    
    await message.answer(text, reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "admin_panel")
async def show_admin_panel(callback: CallbackQuery):
    """Показать админ-панель"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    # Сначала отвечаем на callback, потом обрабатываем
    await callback.answer()
    await cmd_admin_panel(callback.message)

@router.callback_query(F.data == "admin_pending")
async def show_pending_applications(callback: CallbackQuery):
    """Показать заявки в ожидании"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        query = select(Application).where(
            Application.status == "pending"
        ).order_by(Application.created_at)
        
        result = await session.execute(query)
        applications = result.scalars().all()
        
        if not applications:
            await callback.message.edit_text(
                "📋 Нет заявок в ожидании\n\n✅ Все обработано!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
                ])
            )
            return
        
        text = f"⏳ <b>Заявки в ожидании ({len(applications)}):</b>\n\n"
        
        buttons = []
        for app in applications[:10]:  # Показываем первые 10
            waiting_time = datetime.utcnow() - app.created_at
            hours = int(waiting_time.total_seconds() // 3600)
            minutes = int((waiting_time.total_seconds() % 3600) // 60)
            
            button_text = f"⏳ #{app.id} | ${app.amount} | {app.user_name} | {hours}ч {minutes}м"
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_view_{app.id}"
            )])
        
        if len(applications) > 10:
            text += f"<i>Показаны первые 10 из {len(applications)}</i>\n\n"
        
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("admin_view_"))
async def view_application_details(callback: CallbackQuery):
    """Просмотр деталей заявки"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    app_id = int(callback.data.split("_")[2])
    
    async with async_session_maker() as session:
        application = await DatabaseManager.get_application_by_id(session, app_id)
        
        if not application:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        
        await callback.answer()  # Отвечаем после проверки
        
        text = format_application(application, detailed=True)
        
        # Отправляем файл
        try:
            await callback.bot.send_document(
                callback.from_user.id,
                application.file_id,
                caption=f"📎 Файл к заявке #{app_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_application_admin_keyboard(app_id),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "admin_stats")
async def show_detailed_stats(callback: CallbackQuery):
    """Детальная статистика"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        # Статистика за разные периоды
        stats_today = await DatabaseManager.get_stats(session, days=1)
        stats_week = await DatabaseManager.get_stats(session, days=7)
        stats_month = await DatabaseManager.get_stats(session, days=30)
        
        text = (
            "📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>\n\n"
            
            "<b>📅 За сегодня:</b>\n"
            f"• Всего заявок: {stats_today['total']}\n"
            f"• Одобрено: {stats_today['confirmed']} ({stats_today['confirmed']*100//max(stats_today['total'],1)}%)\n"
            f"• Отклонено: {stats_today['rejected']}\n"
            f"• Ожидают: {stats_today['pending']}\n\n"
            
            "<b>📅 За неделю:</b>\n"
            f"• Всего заявок: {stats_week['total']}\n"
            f"• Одобрено: {stats_week['confirmed']} ({stats_week['confirmed']*100//max(stats_week['total'],1)}%)\n"
            f"• Отклонено: {stats_week['rejected']}\n\n"
            
            "<b>📅 За месяц:</b>\n"
            f"• Всего заявок: {stats_month['total']}\n"
            f"• Одобрено: {stats_month['confirmed']} ({stats_month['confirmed']*100//max(stats_month['total'],1)}%)\n"
            f"• Отклонено: {stats_month['rejected']}\n\n"
            
            "<b>🎟️ Остаток кодов:</b>\n"
        )
        
        for amount, count in stats_today['codes_remaining'].items():
            emoji = "🔴" if count < 3 else "🟡" if count < 5 else "🟢"
            text += f"{emoji} ${amount} USD — <b>{count}</b> шт.\n"
        
        # Средняя скорость обработки
        from sqlalchemy import select, func
        query = select(func.avg(
            func.julianday(Application.updated_at) - func.julianday(Application.created_at)
        )).where(
            Application.status.in_(["approved", "rejected"]),
            Application.updated_at.isnot(None),
            Application.created_at >= datetime.utcnow() - timedelta(days=7)
        )
        result = await session.execute(query)
        avg_time_days = result.scalar()
        
        if avg_time_days:
            avg_time_minutes = int(avg_time_days * 24 * 60)
            hours = avg_time_minutes // 60
            minutes = avg_time_minutes % 60
            text += f"\n⏱️ <b>Среднее время обработки:</b> {hours}ч {minutes}мин\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_export_sheets"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("filter_"))
async def apply_filter(callback: CallbackQuery):
    """Применить фильтр"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    filter_type = callback.data.split("_")[1]
    admin_filters[callback.from_user.id] = filter_type
    
    await callback.answer(f"✅ Фильтр '{filter_type}' применен")
    await show_pending_applications(callback)

@router.callback_query(F.data == "admin_all")
async def show_all_applications(callback: CallbackQuery):
    """Показать все заявки"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        
        # Получаем фильтр для админа
        filter_type = admin_filters.get(callback.from_user.id, "today")
        
        date_filter = datetime.utcnow()
        if filter_type == "today":
            date_filter = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        elif filter_type == "week":
            date_filter = datetime.utcnow() - timedelta(days=7)
        elif filter_type == "month":
            date_filter = datetime.utcnow() - timedelta(days=30)
        else:
            date_filter = datetime(2000, 1, 1)  # Все
        
        query = select(Application).where(
            Application.created_at >= date_filter
        ).order_by(Application.created_at.desc()).limit(20)
        
        result = await session.execute(query)
        applications = result.scalars().all()
        
        if not applications:
            await callback.message.edit_text(
                "📋 Нет заявок за выбранный период",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
                ])
            )
            return
        
        filter_names = {
            "today": "сегодня",
            "week": "неделю",
            "month": "месяц",
            "all": "все время"
        }
        
        text = f"📋 <b>Все заявки за {filter_names.get(filter_type, 'период')}:</b>\n\n"
        
        for app in applications[:15]:
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌",
                "cancelled": "🚫"
            }.get(app.status, "❓")
            
            text += f"{status_emoji} #{app.id} | ${app.amount} | {app.user_name} | {app.created_at.strftime('%d.%m %H:%M')}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Фильтры", callback_data="admin_filters"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_all")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_filters")
async def show_filters(callback: CallbackQuery):
    """Показать фильтры"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    current_filter = admin_filters.get(callback.from_user.id, "all")
    
    text = (
        "🔍 <b>Фильтры заявок</b>\n\n"
        "Выберите период:\n"
        f"{'✅' if current_filter == 'today' else '○'} Сегодня\n"
        f"{'✅' if current_filter == 'week' else '○'} Неделя\n"
        f"{'✅' if current_filter == 'month' else '○'} Месяц\n"
        f"{'✅' if current_filter == 'all' else '○'} Все время\n"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_filter_keyboard(current_filter),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_export_sheets")
async def export_to_google_sheets(callback: CallbackQuery):
    """Экспорт в Google Sheets"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer("🔄 Начинаю экспорт...", show_alert=False)
    
    try:
        from google_sheets_integration import export_applications_to_sheets
        
        async with async_session_maker() as session:
            # Получаем все заявки
            from sqlalchemy import select
            query = select(Application).order_by(Application.created_at.desc())
            result = await session.execute(query)
            applications = result.scalars().all()
            
            # Экспортируем
            sheet_url = await export_applications_to_sheets(applications)
            
            text = (
                "✅ <b>Экспорт завершен!</b>\n\n"
                f"📊 Экспортировано заявок: {len(applications)}\n"
                f"📝 Google Sheets: <a href='{sheet_url}'>Открыть</a>\n\n"
                "💡 Таблица автоматически обновляется при новых заявках"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Открыть таблицу", url=sheet_url)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            
    except ImportError:
        text = (
            "⚠️ <b>Google Sheets интеграция не настроена</b>\n\n"
            "Для использования экспорта:\n"
            "1. Установите библиотеку: pip install gspread oauth2client\n"
            "2. Настройте credentials.json\n"
            "3. Смотрите GOOGLE_SHEETS_SETUP.md\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Инструкция", callback_data="admin_sheets_help")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка экспорта в Google Sheets: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка экспорта: {str(e)}\n\nПроверьте настройки Google Sheets API",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
            ])
        )


@router.callback_query(F.data == "admin_settings")
async def show_settings(callback: CallbackQuery):
    """Показать настройки бота"""
    logger.info(f"🔧 show_settings вызвана пользователем {callback.from_user.id}")
    
    has_rights = await check_admin_rights(callback.from_user.id)
    logger.info(f"🔧 Проверка прав для {callback.from_user.id}: {has_rights}")
    
    if not has_rights:
        logger.warning(f"🔧 Отказано в доступе для {callback.from_user.id}")
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    logger.info(f"🔧 Права подтверждены, отвечаем на callback")
    await callback.answer()  # Отвечаем сразу
    
    from config import MAX_APPLICATIONS_PER_DAY, RATE_LIMIT_PER_MINUTE, MAX_FILE_SIZE
    
    async with async_session_maker() as session:
        # Проверяем, является ли пользователь суперадмином
        is_superadmin = await DatabaseManager.is_superadmin(session, callback.from_user.id)
        
        # Получаем статистику кодов
        stats = await DatabaseManager.get_stats(session, days=1)
        
        # Получаем список администраторов
        admins_list = await DatabaseManager.get_all_admins(session)
    
    text = (
        "⚙️ <b>Настройки бота</b>\n\n"
        "<b>📋 Текущие лимиты:</b>\n"
        f"• Заявок в день: {MAX_APPLICATIONS_PER_DAY}\n"
        f"• Минут между заявками: {RATE_LIMIT_PER_MINUTE}\n"
        f"• Макс. размер файла: {MAX_FILE_SIZE // 1024 // 1024} МБ\n\n"
        "<b>📊 Коды активации:</b>\n"
    )
    
    # Показываем остатки кодов
    if stats.get('codes_remaining'):
        for amount, count in stats['codes_remaining'].items():
            emoji = "🔴" if count < 3 else "🟡" if count < 5 else "🟢"
            text += f"{emoji} ${amount} USD — {count} шт.\n"
    else:
        text += "• Нет кодов в системе\n"
    
    # Показываем список администраторов
    text += "\n<b>👥 Администраторы:</b>\n"
    for admin in admins_list:
        role_emoji = "👑" if admin.role == "superadmin" else "👤"
        text += f"{role_emoji} {admin.user_id} ({admin.role})\n"
    
    if not admins_list:
        text += "• Нет администраторов в базе данных\n"
    
    # Кнопки
    buttons = [
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_export_sheets")
        ]
    ]
    
    # Если суперадмин, добавляем дополнительные кнопки управления
    if is_superadmin:
        buttons.append([
            InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage_admins")
        ])
        buttons.append([
            InlineKeyboardButton(text="🎟️ Управление кодами", callback_data="admin_manage_codes"),
            InlineKeyboardButton(text="💰 Номиналы", callback_data="admin_manage_amounts")
        ])
        buttons.append([
            InlineKeyboardButton(text="💳 Платежи", callback_data="admin_payment_settings")
        ])
        buttons.append([
            InlineKeyboardButton(text="🌐 Языки", callback_data="admin_manage_languages"),
            InlineKeyboardButton(text="🔐 Безопасность", callback_data="admin_security_logs")
        ])
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_refresh")
async def refresh_panel(callback: CallbackQuery):
    """Обновить админ-панель"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer("🔄 Обновлено", show_alert=False)
    
    async with async_session_maker() as session:
        stats = await DatabaseManager.get_stats(session, days=1)
    
    text = (
        "👨‍💼 <b>Админ-панель</b>\n\n"
        f"📊 Всего заявок за сегодня: {stats['total']}\n"
        f"⏳ Ожидают: {stats['pending']}\n"
        f"✅ Одобрено: {stats['confirmed']}\n"
        f"❌ Отклонено: {stats['rejected']}\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_approved")
async def show_approved(callback: CallbackQuery):
    """Показать одобренные заявки"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        query = select(Application).where(Application.status == "approved").order_by(Application.updated_at.desc()).limit(10)
        result = await session.execute(query)
        applications = result.scalars().all()
    
    if not applications:
        text = "✅ <b>Одобренные заявки</b>\n\nНет одобренных заявок"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
    else:
        text = f"✅ <b>Одобренные заявки</b>\n\nПоказано последних {len(applications)}:\n\n"
        
        for app in applications:
            text += (
                f"#{app.id} | 👤 {app.user_name} | "
                f"💰 ${app.amount} | 📅 {app.updated_at.strftime('%d.%m %H:%M')}\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_approved")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
            ]
        ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_rejected")
async def show_rejected(callback: CallbackQuery):
    """Показать отклоненные заявки"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    async with async_session_maker() as session:
        from sqlalchemy import select
        query = select(Application).where(Application.status == "rejected").order_by(Application.updated_at.desc()).limit(10)
        result = await session.execute(query)
        applications = result.scalars().all()
    
    if not applications:
        text = "❌ <b>Отклоненные заявки</b>\n\nНет отклоненных заявок"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
        ])
    else:
        text = f"❌ <b>Отклоненные заявки</b>\n\nПоказано последних {len(applications)}:\n\n"
        
        for app in applications:
            text += (
                f"#{app.id} | 👤 {app.user_name} | "
                f"💰 ${app.amount} | 📅 {app.updated_at.strftime('%d.%m %H:%M')}\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_rejected")
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
            ]
        ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_search")
async def show_search(callback: CallbackQuery):
    """Показать поиск"""
    if not await check_admin_rights(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.answer()  # Отвечаем сразу
    
    text = (
        "🔍 <b>Поиск заявок</b>\n\n"
        "Отправьте мне:\n"
        "• Номер заявки (например: 123)\n"
        "• User ID (например: 987654321)\n"
        "• Логин (например: user123)\n\n"
        "Я найду соответствующие заявки"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# ==================== УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ====================

@router.callback_query(F.data == "admin_manage_admins")
async def manage_admins(callback: CallbackQuery):
    """Меню управления администраторами (только для суперадмина)"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
        
        await callback.answer()
        
        # Получаем список всех администраторов
        admins_list = await DatabaseManager.get_all_admins(session)
    
    text = "👥 <b>Управление администраторами</b>\n\n"
    
    if admins_list:
        text += "<b>Список администраторов:</b>\n\n"
        for admin in admins_list:
            role_emoji = "👑" if admin.role == "superadmin" else "👤"
            role_name = "Суперадмин" if admin.role == "superadmin" else "Администратор"
            added_date = admin.created_at.strftime('%d.%m.%Y')
            text += f"{role_emoji} <code>{admin.user_id}</code> - {role_name}\n"
            text += f"   Добавлен: {added_date}\n"
            if admin.added_by:
                text += f"   Добавил: {admin.added_by}\n"
            text += "\n"
    else:
        text += "⚠️ В базе данных нет администраторов.\n"
        text += "Используйте кнопку ниже для добавления.\n\n"
    
    text += "\n💡 <b>Доступные действия:</b>\n"
    text += "• Добавить нового администратора\n"
    text += "• Удалить администратора\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_admin"),
            InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove_admin")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_add_admin")
async def add_admin_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления администратора"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
    
    await callback.answer()
    
    await state.set_state(AdminManagementStates.waiting_for_admin_id_to_add)
    
    text = (
        "➕ <b>Добавление администратора</b>\n\n"
        "Отправьте User ID пользователя, которого хотите сделать администратором.\n\n"
        "💡 <b>Как узнать User ID:</b>\n"
        "1. Попросите пользователя написать боту @userinfobot\n"
        "2. Или найдите его ID в логах бота\n\n"
        "Отправьте /cancel для отмены"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_admins")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(AdminManagementStates.waiting_for_admin_id_to_add))
async def add_admin_process(message: Message, state: FSMContext):
    """Обработка добавления администратора"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        try:
            new_admin_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Неверный формат User ID. Отправьте число.")
            return
        
        # Проверяем, не является ли пользователь уже администратором
        existing_role = await DatabaseManager.get_admin_role(session, new_admin_id)
        
        if existing_role:
            await message.answer(
                f"⚠️ Пользователь <code>{new_admin_id}</code> уже является администратором ({existing_role}).",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Добавляем администратора
        try:
            await DatabaseManager.add_admin(session, new_admin_id, "admin", user_id)
            
            await message.answer(
                f"✅ <b>Администратор добавлен!</b>\n\n"
                f"👤 User ID: <code>{new_admin_id}</code>\n"
                f"📋 Роль: Администратор\n\n"
                f"Пользователь теперь имеет доступ к админ-панели.",
                parse_mode="HTML"
            )
            
            # Пытаемся уведомить нового администратора
            try:
                await message.bot.send_message(
                    new_admin_id,
                    "🎉 <b>Поздравляем!</b>\n\n"
                    "Вам предоставлены права администратора.\n"
                    "Используйте команду /admin для доступа к админ-панели.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить нового админа {new_admin_id}: {e}")
                await message.answer(
                    "⚠️ Не удалось отправить уведомление новому администратору. "
                    "Возможно, он еще не начинал диалог с ботом."
                )
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка добавления администратора: {e}")
            await message.answer(f"❌ Ошибка при добавлении: {str(e)}")
            await state.clear()

@router.callback_query(F.data == "admin_remove_admin")
async def remove_admin_start(callback: CallbackQuery, state: FSMContext):
    """Начало удаления администратора"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
        
        # Получаем список администраторов
        admins_list = await DatabaseManager.get_all_admins(session)
    
    await callback.answer()
    
    if not admins_list:
        await callback.message.edit_text(
            "⚠️ Нет администраторов для удаления.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_admins")]
            ])
        )
        return
    
    await state.set_state(AdminManagementStates.waiting_for_admin_id_to_remove)
    
    text = "➖ <b>Удаление администратора</b>\n\n"
    text += "<b>Текущие администраторы:</b>\n\n"
    
    for admin in admins_list:
        role_emoji = "👑" if admin.role == "superadmin" else "👤"
        role_name = "Суперадмин" if admin.role == "superadmin" else "Администратор"
        text += f"{role_emoji} <code>{admin.user_id}</code> - {role_name}\n"
    
    text += "\n💡 Отправьте User ID администратора для удаления.\n"
    text += "⚠️ <b>Внимание:</b> Нельзя удалить суперадминистратора!\n\n"
    text += "Отправьте /cancel для отмены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_admins")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(AdminManagementStates.waiting_for_admin_id_to_remove))
async def remove_admin_process(message: Message, state: FSMContext):
    """Обработка удаления администратора"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        try:
            admin_id_to_remove = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Неверный формат User ID. Отправьте число.")
            return
        
        # Проверяем роль удаляемого администратора
        admin_role = await DatabaseManager.get_admin_role(session, admin_id_to_remove)
        
        if not admin_role:
            await message.answer(
                f"⚠️ Пользователь <code>{admin_id_to_remove}</code> не является администратором.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Нельзя удалить суперадминистратора
        if admin_role == "superadmin":
            await message.answer(
                "❌ Нельзя удалить суперадминистратора!\n"
                "Суперадминистратор может быть изменен только через базу данных."
            )
            await state.clear()
            return
        
        # Удаляем администратора
        try:
            success = await DatabaseManager.remove_admin(session, admin_id_to_remove)
            
            if success:
                await message.answer(
                    f"✅ <b>Администратор удален!</b>\n\n"
                    f"👤 User ID: <code>{admin_id_to_remove}</code>\n\n"
                    f"Пользователь больше не имеет доступа к админ-панели.",
                    parse_mode="HTML"
                )
                
                # Пытаемся уведомить удаленного администратора
                try:
                    await message.bot.send_message(
                        admin_id_to_remove,
                        "⚠️ <b>Уведомление</b>\n\n"
                        "Ваши права администратора были отозваны.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить удаленного админа {admin_id_to_remove}: {e}")
            else:
                await message.answer("❌ Ошибка при удалении администратора.")
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка удаления администратора: {e}")
            await message.answer(f"❌ Ошибка при удалении: {str(e)}")
            await state.clear()

# ==================== УПРАВЛЕНИЕ КОДАМИ АКТИВАЦИИ ====================

@router.callback_query(F.data == "admin_manage_codes")
async def manage_codes_menu(callback: CallbackQuery):
    """Меню управления кодами активации"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
        
        await callback.answer()
        
        # Получаем статистику кодов
        codes = await DatabaseManager.get_all_codes(session)
        unused_codes = [c for c in codes if not c.is_used]
        used_codes = [c for c in codes if c.is_used]
        
        # Группируем по суммам
        codes_by_amount = {}
        for code in unused_codes:
            amount = float(code.amount)
            if amount not in codes_by_amount:
                codes_by_amount[amount] = 0
            codes_by_amount[amount] += 1
    
    text = (
        "🎟️ <b>Управление кодами активации</b>\n\n"
        "<b>📊 Статистика:</b>\n"
        f"• Всего кодов: {len(codes)}\n"
        f"• Доступно: {len(unused_codes)}\n"
        f"• Использовано: {len(used_codes)}\n\n"
        "<b>💰 По номиналам (доступно):</b>\n"
    )
    
    for amount in sorted(codes_by_amount.keys()):
        emoji = "🔴" if codes_by_amount[amount] < 3 else "🟡" if codes_by_amount[amount] < 5 else "🟢"
        text += f"{emoji} ${int(amount)} USD — {codes_by_amount[amount]} шт.\n"
    
    if not codes_by_amount:
        text += "⚠️ Нет доступных кодов!\n"
    
    text += "\n💡 <b>Доступные действия:</b>\n"
    text += "• Добавить новый код вручную\n"
    text += "• Импортировать коды из CSV файла\n"
    text += "• Просмотреть все коды\n"
    text += "• Удалить код\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить код", callback_data="codes_add_single"),
            InlineKeyboardButton(text="📄 Импорт CSV", callback_data="codes_import_csv")
        ],
        [
            InlineKeyboardButton(text="📋 Все коды", callback_data="codes_view_all"),
            InlineKeyboardButton(text="🗑️ Удалить код", callback_data="codes_delete")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад к настройкам", callback_data="admin_settings")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "codes_add_single")
async def add_single_code_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления одного кода"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
    
    await callback.answer()
    await state.set_state(CodesManagementStates.waiting_for_code_to_add)
    
    text = (
        "➕ <b>Добавление кода активации</b>\n\n"
        "Отправьте значение кода (любая строка).\n\n"
        "💡 <b>Примеры:</b>\n"
        "• ABC123-XYZ789\n"
        "• PROMO2024\n"
        "• 123456789\n\n"
        "⚠️ Код должен быть уникальным!\n\n"
        "Отправьте /cancel для отмены"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_codes")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(CodesManagementStates.waiting_for_code_to_add))
async def add_single_code_value(message: Message, state: FSMContext):
    """Получение значения кода"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        code_value = message.text.strip()
        
        if len(code_value) < 3:
            await message.answer("❌ Код должен содержать минимум 3 символа.")
            return
        
        # Проверяем уникальность
        existing = await DatabaseManager.get_code_by_value(session, code_value)
        if existing:
            await message.answer(
                f"❌ Код <code>{code_value}</code> уже существует в системе!",
                parse_mode="HTML"
            )
            return
        
        # Сохраняем код и переходим к запросу суммы
        await state.update_data(code_value=code_value)
        await state.set_state(CodesManagementStates.waiting_for_amount_for_code)
        
        await message.answer(
            f"✅ Код: <code>{code_value}</code>\n\n"
            "Теперь введите номинал (сумму) для этого кода.\n\n"
            "💡 <b>Примеры:</b> 10, 25, 50, 100\n\n"
            "Отправьте /cancel для отмены",
            parse_mode="HTML"
        )

@router.message(StateFilter(CodesManagementStates.waiting_for_amount_for_code))
async def add_single_code_amount(message: Message, state: FSMContext):
    """Получение суммы для кода"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        try:
            amount = float(message.text.strip().replace(",", "."))
            
            if amount <= 0:
                await message.answer("❌ Сумма должна быть положительной.")
                return
            
            if amount > 10000:
                await message.answer("❌ Максимальная сумма: 10,000 USD")
                return
            
        except ValueError:
            await message.answer("❌ Неверный формат суммы. Введите число.")
            return
        
        # Получаем сохраненное значение кода
        data = await state.get_data()
        code_value = data.get("code_value")
        
        if not code_value:
            await message.answer("❌ Ошибка: код не найден. Начните заново.")
            await state.clear()
            return
        
        # Добавляем код в базу данных
        try:
            await DatabaseManager.add_activation_code(session, code_value, amount)
            
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session,
                user_id,
                "add_code",
                details=f"Добавлен код {code_value} на сумму ${amount}"
            )
            
            await message.answer(
                f"✅ <b>Код успешно добавлен!</b>\n\n"
                f"🎟️ <b>Код:</b> <code>{code_value}</code>\n"
                f"💰 <b>Номинал:</b> ${amount} USD\n\n"
                f"Код готов к использованию.",
                parse_mode="HTML"
            )
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка добавления кода: {e}")
            await message.answer(f"❌ Ошибка при добавлении кода: {str(e)}")
            await state.clear()

@router.callback_query(F.data == "codes_import_csv")
async def import_codes_csv_start(callback: CallbackQuery, state: FSMContext):
    """Начало импорта кодов из CSV"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
    
    await callback.answer()
    await state.set_state(CodesManagementStates.waiting_for_csv_file)
    
    text = (
        "📄 <b>Импорт кодов из CSV</b>\n\n"
        "Отправьте CSV файл в формате:\n"
        "<code>код,сумма</code>\n\n"
        "💡 <b>Пример содержимого файла:</b>\n"
        "<code>ABC123,10\n"
        "XYZ789,25\n"
        "PROMO2024,50</code>\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Первая строка - заголовок (пропускается)\n"
        "• Разделитель: запятая или точка с запятой\n"
        "• Дубликаты будут пропущены\n\n"
        "Отправьте /cancel для отмены"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_codes")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(CodesManagementStates.waiting_for_csv_file))
async def import_codes_csv_process(message: Message, state: FSMContext):
    """Обработка CSV файла с кодами"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        # Проверяем, что это документ
        if not message.document:
            await message.answer("❌ Пожалуйста, отправьте CSV файл как документ.")
            return
        
        # Проверяем расширение
        filename = message.document.file_name
        if not filename.lower().endswith('.csv'):
            await message.answer("❌ Файл должен иметь расширение .csv")
            return
        
        try:
            # Скачиваем файл
            import tempfile
            import csv
            import os
            
            file_info = await message.bot.get_file(message.document.file_id)
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.csv') as tmp_file:
                tmp_path = tmp_file.name
                await message.bot.download(file=message.document.file_id, destination=tmp_path)
            
            # Читаем CSV
            codes_data = []
            with open(tmp_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Пропускаем заголовок
                
                for row in reader:
                    if len(row) >= 2:
                        code_value = row[0].strip()
                        try:
                            amount = float(row[1].strip().replace(",", "."))
                            codes_data.append((code_value, amount))
                        except ValueError:
                            logger.warning(f"Пропущена строка с неверной суммой: {row}")
            
            # Удаляем временный файл
            os.unlink(tmp_path)
            
            if not codes_data:
                await message.answer("❌ В файле не найдено корректных данных.")
                await state.clear()
                return
            
            # Импортируем коды
            result = await DatabaseManager.import_codes_from_list(session, codes_data)
            
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session,
                user_id,
                "import_codes",
                details=f"Импортировано {result['added']} кодов из CSV"
            )
            
            text = (
                f"✅ <b>Импорт завершен!</b>\n\n"
                f"📊 <b>Результаты:</b>\n"
                f"• Добавлено новых: <b>{result['added']}</b>\n"
                f"• Пропущено (дубликаты): {result['skipped']}\n"
            )
            
            if result['errors']:
                text += f"\n⚠️ <b>Ошибки:</b>\n"
                for error in result['errors'][:5]:
                    text += f"• {error}\n"
                if len(result['errors']) > 5:
                    text += f"• ... и еще {len(result['errors']) - 5}\n"
            
            await message.answer(text, parse_mode="HTML")
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка импорта CSV: {e}")
            await message.answer(f"❌ Ошибка при импорте: {str(e)}")
            await state.clear()

@router.callback_query(F.data == "codes_view_all")
async def view_all_codes(callback: CallbackQuery):
    """Просмотр всех кодов"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
        
        await callback.answer()
        
        codes = await DatabaseManager.get_all_codes(session)
    
    if not codes:
        text = "📋 <b>Коды активации</b>\n\n⚠️ В системе нет кодов активации."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_codes")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Группируем по суммам
    codes_by_amount = {}
    for code in codes:
        amount = float(code.amount)
        if amount not in codes_by_amount:
            codes_by_amount[amount] = []
        codes_by_amount[amount].append(code)
    
    text = f"📋 <b>Все коды активации ({len(codes)} шт.)</b>\n\n"
    
    for amount in sorted(codes_by_amount.keys()):
        codes_list = codes_by_amount[amount]
        unused = [c for c in codes_list if not c.is_used]
        used = [c for c in codes_list if c.is_used]
        
        text += f"💰 <b>${int(amount)} USD</b> ({len(unused)} доступно / {len(used)} использовано)\n"
        
        # Показываем первые 5 доступных кодов
        for code in unused[:5]:
            text += f"  🟢 <code>{code.code_value}</code> (ID: {code.id})\n"
        
        if len(unused) > 5:
            text += f"  ... и еще {len(unused) - 5}\n"
        
        text += "\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (список слишком длинный)"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_codes")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "codes_delete")
async def delete_code_start(callback: CallbackQuery, state: FSMContext):
    """Начало удаления кода"""
    user_id = callback.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await callback.answer("❌ Только для суперадминистратора", show_alert=True)
            return
        
        codes = await DatabaseManager.get_all_codes(session, only_unused=True)
    
    await callback.answer()
    
    if not codes:
        await callback.message.edit_text(
            "⚠️ Нет доступных кодов для удаления.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_manage_codes")]
            ])
        )
        return
    
    await state.set_state(CodesManagementStates.waiting_for_code_id_to_delete)
    
    text = "🗑️ <b>Удаление кода активации</b>\n\n"
    text += "<b>Доступные коды:</b>\n\n"
    
    for code in codes[:20]:
        text += f"• ID: {code.id} | <code>{code.code_value}</code> | ${code.amount}\n"
    
    if len(codes) > 20:
        text += f"\n... и еще {len(codes) - 20} кодов\n"
    
    text += "\n💡 Отправьте ID кода для удаления.\n"
    text += "Отправьте /cancel для отмены"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_manage_codes")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(StateFilter(CodesManagementStates.waiting_for_code_id_to_delete))
async def delete_code_process(message: Message, state: FSMContext):
    """Обработка удаления кода"""
    user_id = message.from_user.id
    
    async with async_session_maker() as session:
        is_superadmin = await DatabaseManager.is_superadmin(session, user_id)
        
        if not is_superadmin:
            await message.answer("❌ Только для суперадминистратора")
            await state.clear()
            return
        
        try:
            code_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Неверный формат ID. Введите число.")
            return
        
        # Получаем информацию о коде перед удалением
        query = select(ActivationCode).where(ActivationCode.id == code_id)
        result = await session.execute(query)
        code = result.scalar_one_or_none()
        
        if not code:
            await message.answer(f"❌ Код с ID {code_id} не найден.")
            await state.clear()
            return
        
        if code.is_used:
            await message.answer(
                f"❌ Код <code>{code.code_value}</code> уже использован и не может быть удален!",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Удаляем код
        success = await DatabaseManager.delete_activation_code(session, code_id)
        
        if success:
            # Логируем действие
            await DatabaseManager.log_admin_action(
                session,
                user_id,
                "delete_code",
                target_id=code_id,
                details=f"Удален код {code.code_value} на сумму ${code.amount}"
            )
            
            await message.answer(
                f"✅ <b>Код удален!</b>\n\n"
                f"🗑️ ID: {code_id}\n"
                f"🎟️ Код: <code>{code.code_value}</code>\n"
                f"💰 Номинал: ${code.amount} USD",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при удалении кода.")
        
        await state.clear()
