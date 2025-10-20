"""
Модуль мультиязычности для бота
Поддержка: Русский, English, اردو (Urdu)
"""

LANGUAGES = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "ur": "🇵🇰 اردو"
}

TRANSLATIONS = {
    # Первое приветствие (без языка)
    "first_welcome": {
        "multi": "👋 <b>Добро пожаловать!</b>\n<b>Welcome!</b>\n<b>خوش آمدید!</b>\n\n🌐 Пожалуйста, выберите язык:\n🌐 Please choose your language:\n🌐 براہ کرم زبان منتخب کریں:"
    },
    
    # Главное меню
    "menu_welcome": {
        "ru": "👋 Главное меню",
        "en": "👋 Main Menu",
        "ur": "👋 مین مینو"
    },
    "menu_make_deposit": {
        "ru": "💰 Сделать депозит",
        "en": "💰 Make Deposit",
        "ur": "💰 ڈپازٹ کریں"
    },
    "menu_my_applications": {
        "ru": "🧾 Мои заявки",
        "en": "🧾 My Applications",
        "ur": "🧾 میری درخواستیں"
    },
    "menu_support": {
        "ru": "💬 Поддержка",
        "en": "💬 Support",
        "ur": "💬 سپورٹ"
    },
    "menu_change_language": {
        "ru": "🌐 Сменить язык",
        "en": "🌐 Change Language",
        "ur": "🌐 زبان تبدیل کریں"
    },
    
    # Приветствие
    "welcome_message": {
        "ru": "👋 Привет, {name}!\n\nДобро пожаловать в систему депозитов!\n\nЯ помогу вам:\n• Сделать депозит\n• Прикрепить подтверждающие документы\n• Получить код активации после проверки\n\nВыберите действие:",
        "en": "👋 Hello, {name}!\n\nWelcome to the deposit system!\n\nI will help you:\n• Make a deposit\n• Attach confirmation documents\n• Get activation code after verification\n\nChoose an action:",
        "ur": "👋 ہیلو، {name}!\n\nڈپازٹ سسٹم میں خوش آمدید!\n\nمیں آپ کی مدد کروں گا:\n• ڈپازٹ کریں\n• تصدیقی دستاویزات منسلک کریں\n• تصدیق کے بعد ایکٹیویشن کوڈ حاصل کریں\n\nایک عمل منتخب کریں:"
    },
    
    # Процесс депозита
    "choose_amount": {
        "ru": "💰 Выберите сумму депозита:",
        "en": "💰 Choose deposit amount:",
        "ur": "💰 ڈپازٹ کی رقم منتخب کریں:"
    },
    "custom_amount": {
        "ru": "💰 Другая сумма",
        "en": "💰 Custom Amount",
        "ur": "💰 دوسری رقم"
    },
    "enter_custom_amount": {
        "ru": "💰 Введите сумму депозита (в USD):\n\nНапример: 150",
        "en": "💰 Enter deposit amount (in USD):\n\nFor example: 150",
        "ur": "💰 ڈپازٹ کی رقم درج کریں (USD میں):\n\nمثال کے طور پر: 150"
    },
    "enter_login": {
        "ru": "💰 Сумма депозита: {amount} USD\n\n👤 Введите ваш ID или логин (на который будет зачислен депозит):",
        "en": "💰 Deposit amount: {amount} USD\n\n👤 Enter your ID or login (for deposit credit):",
        "ur": "💰 ڈپازٹ کی رقم: {amount} USD\n\n👤 اپنی ID یا لاگ ان درج کریں (ڈپازٹ کریڈٹ کے لیے):"
    },
    
    # Подтверждение данных
    "confirm_data": {
        "ru": "📋 Проверьте данные перед отправкой:\n\n💵 Сумма: {amount} USD\n👤 Логин: {login}\n\nВсё верно?",
        "en": "📋 Check data before sending:\n\n💵 Amount: {amount} USD\n👤 Login: {login}\n\nIs everything correct?",
        "ur": "📋 بھیجنے سے پہلے ڈیٹا چیک کریں:\n\n💵 رقم: {amount} USD\n👤 لاگ ان: {login}\n\nکیا سب کچھ ٹھیک ہے؟"
    },
    "yes_correct": {
        "ru": "✅ Да, всё верно",
        "en": "✅ Yes, correct",
        "ur": "✅ ہاں، ٹھیک ہے"
    },
    "change_data": {
        "ru": "✏️ Изменить данные",
        "en": "✏️ Change data",
        "ur": "✏️ ڈیٹا تبدیل کریں"
    },
    
    # Загрузка файла
    "upload_file": {
        "ru": "📎 Отправьте скриншот или PDF подтверждения платежа:\n\n• JPG, PNG, PDF\n• До 10 МБ\n• Файл должен содержать подтверждение перевода\n\n⏰ У вас есть 15 минут на загрузку файла.",
        "en": "📎 Send screenshot or PDF payment confirmation:\n\n• JPG, PNG, PDF\n• Up to 10 MB\n• File must contain transfer confirmation\n\n⏰ You have 15 minutes to upload the file.",
        "ur": "📎 اسکرین شاٹ یا PDF ادائیگی کی تصدیق بھیجیں:\n\n• JPG، PNG، PDF\n• 10 MB تک\n• فائل میں منتقلی کی تصدیق ہونی چاہیے\n\n⏰ آپ کے پاس فائل اپ لوڈ کرنے کے لیے 15 منٹ ہیں۔"
    },
    
    # Успех/Ошибки
    "application_created": {
        "ru": "✅ Заявка успешно создана!\n\n📋 Номер заявки: #{app_id}\n💰 Сумма: {amount} USD\n👤 Логин: {login}\n\n⏳ Ваша заявка отправлена на проверку администратору.\n\n🔔 Вы получите уведомление, когда статус изменится.",
        "en": "✅ Application created successfully!\n\n📋 Application number: #{app_id}\n💰 Amount: {amount} USD\n👤 Login: {login}\n\n⏳ Your application has been sent for admin review.\n\n🔔 You will receive a notification when status changes.",
        "ur": "✅ درخواست کامیابی سے بنائی گئی!\n\n📋 درخواست نمبر: #{app_id}\n💰 رقم: {amount} USD\n👤 لاگ ان: {login}\n\n⏳ آپ کی درخواست ایڈمن کے جائزے کے لیے بھیجی گئی ہے۔\n\n🔔 آپ کو اطلاع ملے گی جب حیثیت تبدیل ہو گی۔"
    },
    "timeout_expired": {
        "ru": "⏰ Время на загрузку скриншота истекло.\n\nСоздайте новую заявку через /start",
        "en": "⏰ Time to upload screenshot has expired.\n\nCreate a new application via /start",
        "ur": "⏰ اسکرین شاٹ اپ لوڈ کرنے کا وقت ختم ہو گیا۔\n\n/start کے ذریعے نئی درخواست بنائیں"
    },
    
    # Статусы
    "status_approved": {
        "ru": "✅ Ваша заявка #{app_id} подтверждена!\n\n🎟️ Ваш код активации: {code}\n\nСпасибо за использование нашего сервиса!",
        "en": "✅ Your application #{app_id} has been approved!\n\n🎟️ Your activation code: {code}\n\nThank you for using our service!",
        "ur": "✅ آپ کی درخواست #{app_id} منظور ہو گئی!\n\n🎟️ آپ کا ایکٹیویشن کوڈ: {code}\n\nہماری سروس استعمال کرنے کا شکریہ!"
    },
    "status_rejected": {
        "ru": "❌ Ваша заявка #{app_id} отклонена.\n\nПричина: {reason}\n\nХотите отправить новый скриншот?",
        "en": "❌ Your application #{app_id} has been rejected.\n\nReason: {reason}\n\nDo you want to send a new screenshot?",
        "ur": "❌ آپ کی درخواست #{app_id} مسترد کر دی گئی۔\n\nوجہ: {reason}\n\nکیا آپ نیا اسکرین شاٹ بھیجنا چاہتے ہیں؟"
    },
    "status_pending": {
        "ru": "🕓 Ваша заявка #{app_id} рассматривается.\n\nПожалуйста, ожидайте.",
        "en": "🕓 Your application #{app_id} is being reviewed.\n\nPlease wait.",
        "ur": "🕓 آپ کی درخواست #{app_id} کا جائزہ لیا جا رہا ہے۔\n\nبراہ کرم انتظار کریں۔"
    },
    
    # Кнопки
    "btn_yes": {
        "ru": "✅ Да",
        "en": "✅ Yes",
        "ur": "✅ ہاں"
    },
    "btn_no": {
        "ru": "❌ Нет",
        "en": "❌ No",
        "ur": "❌ نہیں"
    },
    "btn_cancel": {
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "ur": "❌ منسوخ"
    },
    "btn_back": {
        "ru": "◀️ Назад",
        "en": "◀️ Back",
        "ur": "◀️ واپس"
    },
    "btn_menu": {
        "ru": "🏠 Главное меню",
        "en": "🏠 Main Menu",
        "ur": "🏠 مین مینو"
    },
    
    # Выбор метода оплаты
    "payment_method_selection": {
        "ru": "💰 <b>Выберите способ оплаты</b>\n\n🔹 <b>Онлайн-оплата</b> — мгновенная оплата картой, Google Pay или Apple Pay. Код активации выдаётся автоматически сразу после оплаты.\n\n🔹 <b>Загрузить чек</b> — переведите средства на указанные реквизиты и загрузите скриншот чека. Заявка будет рассмотрена администратором.\n\nВыберите удобный способ:",
        "en": "💰 <b>Choose payment method</b>\n\n🔹 <b>Online payment</b> — instant payment by card, Google Pay or Apple Pay. Activation code is issued automatically immediately after payment.\n\n🔹 <b>Upload receipt</b> — transfer funds to the specified details and upload a screenshot of the receipt. The application will be reviewed by the administrator.\n\nChoose a convenient method:",
        "ur": "💰 <b>ادائیگی کا طریقہ منتخب کریں</b>\n\n🔹 <b>آن لائن ادائیگی</b> — کارڈ، Google Pay یا Apple Pay سے فوری ادائیگی۔ ادائیگی کے فوراً بعد ایکٹیویشن کوڈ خودکار طور پر جاری کیا جاتا ہے۔\n\n🔹 <b>رسید اپ لوڈ کریں</b> — مخصوص تفصیلات میں رقم منتقل کریں اور رسید کا اسکرین شاٹ اپ لوڈ کریں۔ درخواست کا ایڈمنسٹریٹر کے ذریعے جائزہ لیا جائے گا۔\n\nآسان طریقہ منتخب کریں:"
    },
    "btn_payment_online": {
        "ru": "💳 Онлайн-оплата (карта, Google Pay, Apple Pay)",
        "en": "💳 Online payment (card, Google Pay, Apple Pay)",
        "ur": "💳 آن لائن ادائیگی (کارڈ، Google Pay، Apple Pay)"
    },
    "btn_payment_manual": {
        "ru": "📄 Загрузить чек оплаты (Card-to-Card)",
        "en": "📄 Upload payment receipt (Card-to-Card)",
        "ur": "📄 ادائیگی کی رسید اپ لوڈ کریں (Card-to-Card)"
    },
    
    # FAQ
    "menu_faq": {
        "ru": "❓ FAQ",
        "en": "❓ FAQ",
        "ur": "❓ عمومی سوالات"
    },
    
    # Админ
    "admin_new_application": {
        "ru": "🔔 Новая заявка на депозит!\n\n📋 Номер: #{app_id}\n👤 Пользователь: {user_name} (ID: {user_id})\n💰 Сумма: {amount} USD\n🆔 Логин: {login}\n🕒 Время: {time}",
        "en": "🔔 New deposit application!\n\n📋 Number: #{app_id}\n👤 User: {user_name} (ID: {user_id})\n💰 Amount: {amount} USD\n🆔 Login: {login}\n🕒 Time: {time}",
        "ur": "🔔 نیا ڈپازٹ درخواست!\n\n📋 نمبر: #{app_id}\n👤 صارف: {user_name} (ID: {user_id})\n💰 رقم: {amount} USD\n🆔 لاگ ان: {login}\n🕒 وقت: {time}"
    },
    
    # Ошибки
    "error_invalid_amount": {
        "ru": "❌ Неверная сумма. Введите число больше 0.",
        "en": "❌ Invalid amount. Enter a number greater than 0.",
        "ur": "❌ غلط رقم۔ 0 سے زیادہ نمبر درج کریں۔"
    },
    "error_invalid_file": {
        "ru": "❌ Неверный тип файла. Отправьте JPG, PNG или PDF.",
        "en": "❌ Invalid file type. Send JPG, PNG or PDF.",
        "ur": "❌ غلط فائل کی قسم۔ JPG، PNG یا PDF بھیجیں۔"
    },
    "error_file_too_large": {
        "ru": "❌ Файл слишком большой. Максимум 10 МБ.",
        "en": "❌ File is too large. Maximum 10 MB.",
        "ur": "❌ فائل بہت بڑی ہے۔ زیادہ سے زیادہ 10 MB۔"
    }
}

def get_text(key: str, lang: str = "ru", **kwargs) -> str:
    """
    Получить переведенный текст
    
    Args:
        key: Ключ перевода
        lang: Код языка (ru, en, ur)
        **kwargs: Параметры для форматирования строки
    
    Returns:
        Переведенная строка
    """
    if key not in TRANSLATIONS:
        return f"[Missing translation: {key}]"
    
    if lang not in TRANSLATIONS[key]:
        lang = "ru"  # Fallback на русский
    
    text = TRANSLATIONS[key][lang]
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    
    return text

def get_language_keyboard():
    """Получить клавиатуру выбора языка"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANGUAGES["ru"], callback_data="lang_ru")],
        [InlineKeyboardButton(text=LANGUAGES["en"], callback_data="lang_en")],
        [InlineKeyboardButton(text=LANGUAGES["ur"], callback_data="lang_ur")]
    ])
    
    return keyboard
