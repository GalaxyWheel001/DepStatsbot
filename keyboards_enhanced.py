"""
Улучшенные клавиатуры с поддержкой навигации "Назад",
детального просмотра заявок, FAQ и поддержки
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import DEPOSIT_AMOUNTS
from localization import get_text

def get_main_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text("menu_make_deposit", lang), 
            callback_data="menu_deposit"
        )],
        [InlineKeyboardButton(
            text=get_text("menu_my_applications", lang), 
            callback_data="menu_applications"
        )],
        [InlineKeyboardButton(
            text="❓ FAQ",
            callback_data="menu_faq"
        )],
        [InlineKeyboardButton(
            text=get_text("menu_support", lang), 
            callback_data="menu_support"
        )],
        [InlineKeyboardButton(
            text=get_text("menu_change_language", lang), 
            callback_data="menu_language"
        )]
    ])
    return keyboard

def get_deposit_amount_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура выбора суммы депозита"""
    keyboard_buttons = []
    
    # Добавляем стандартные суммы по 2 в ряд
    for i in range(0, len(DEPOSIT_AMOUNTS), 2):
        row = []
        for j in range(2):
            if i + j < len(DEPOSIT_AMOUNTS):
                amount = DEPOSIT_AMOUNTS[i + j]
                row.append(
                    InlineKeyboardButton(
                        text=f"💰 {amount} USD", 
                        callback_data=f"amount_{amount}"
                    )
                )
        keyboard_buttons.append(row)
    
    # Добавляем кнопку "Другая сумма"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text=get_text("custom_amount", lang), 
            callback_data="amount_custom"
        )
    ])
    
    # Добавляем кнопки навигации
    keyboard_buttons.append([
        InlineKeyboardButton(
            text=get_text("btn_menu", lang), 
            callback_data="back_to_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

def get_confirm_data_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения данных"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text("yes_correct", lang), 
            callback_data="confirm_yes"
        )],
        [InlineKeyboardButton(
            text=get_text("change_data", lang), 
            callback_data="confirm_change"
        )],
        [InlineKeyboardButton(
            text=get_text("btn_cancel", lang), 
            callback_data="back_to_menu"
        )]
    ])
    return keyboard

def get_admin_keyboard(application_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура для администратора"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data=f"admin_approve_{application_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить", 
                callback_data=f"admin_reject_{application_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 История", 
                callback_data=f"admin_history_{application_id}"
            )
        ]
    ])
    return keyboard

def get_retry_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура для повторной отправки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Попробовать снова", 
                callback_data="retry_yes"
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_menu", lang), 
                callback_data="back_to_menu"
            )
        ]
    ])
    return keyboard

def get_back_button(lang: str = "ru", show_back: bool = False) -> InlineKeyboardMarkup:
    """Кнопка возврата в меню (с опциональной кнопкой Назад)"""
    buttons = []
    
    if show_back:
        buttons.append([InlineKeyboardButton(
            text=get_text("btn_back", lang), 
            callback_data="go_back"
        )])
    
    buttons.append([InlineKeyboardButton(
        text=get_text("btn_menu", lang), 
        callback_data="back_to_menu"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_language_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура выбора языка"""
    from localization import LANGUAGES
    
    buttons = [
        [InlineKeyboardButton(
            text=LANGUAGES["ru"], 
            callback_data="lang_ru"
        )],
        [InlineKeyboardButton(
            text=LANGUAGES["en"], 
            callback_data="lang_en"
        )],
        [InlineKeyboardButton(
            text=LANGUAGES["ur"], 
            callback_data="lang_ur"
        )]
    ]
    
    # Добавляем кнопку "Назад" только если это не первый запуск
    if show_back:
        buttons.append([InlineKeyboardButton(
            text="◀️ Назад / Back / واپس", 
            callback_data="back_to_menu"
        )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_faq_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура для FAQ"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text("btn_menu", lang),
            callback_data="back_to_menu"
        )]
    ])
    return keyboard

def get_applications_list_keyboard(applications: list, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура со списком заявок (кликабельные)"""
    buttons = []
    
    for app in applications:
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "cancelled": "🚫",
            "needs_info": "💬"
        }.get(app.status, "❓")
        
        button_text = f"{status_emoji} #{app.id} • {app.amount} USD • {app.created_at.strftime('%d.%m')}"
        
        buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"view_app_{app.id}"
        )])
    
    # Добавляем кнопку возврата
    buttons.append([InlineKeyboardButton(
        text=get_text("btn_menu", lang),
        callback_data="back_to_menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_application_details_keyboard(application, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура для деталей заявки"""
    buttons = []
    
    # Если заявка в статусе pending, можно отменить
    if application.status == "pending":
        buttons.append([InlineKeyboardButton(
            text="🚫 Отменить заявку",
            callback_data=f"cancel_app_{application.id}"
        )])
    
    # Кнопка возврата к списку заявок
    buttons.append([InlineKeyboardButton(
        text="◀️ К списку заявок",
        callback_data="menu_applications"
    )])
    
    # Кнопка в главное меню
    buttons.append([InlineKeyboardButton(
        text=get_text("btn_menu", lang),
        callback_data="back_to_menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_selection_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура выбора метода оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text("btn_payment_online", lang),
            callback_data="payment_method_online"
        )],
        [InlineKeyboardButton(
            text=get_text("btn_payment_manual", lang),
            callback_data="payment_method_manual"
        )],
        [InlineKeyboardButton(
            text=get_text("btn_menu", lang),
            callback_data="back_to_menu"
        )]
    ])
    return keyboard

def get_cancel_application_keyboard(application_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отмены заявки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, отменить",
                callback_data=f"confirm_cancel_{application_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Нет, вернуться",
                callback_data=f"view_app_{application_id}"
            )
        ]
    ])
    return keyboard

