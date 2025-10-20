"""
Тестовый скрипт для проверки подключения к Google Sheets
"""
import sys
from datetime import datetime
from loguru import logger

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

def test_imports():
    """Проверка установки библиотек"""
    logger.info("🔍 Проверка установленных библиотек...")
    
    try:
        import gspread
        logger.info("✅ gspread установлен")
    except ImportError:
        logger.error("❌ gspread НЕ установлен. Установите: pip install gspread")
        return False
    
    try:
        from google.oauth2.service_account import Credentials
        logger.info("✅ google-auth установлен")
    except ImportError:
        logger.error("❌ google-auth НЕ установлен. Установите: pip install google-auth")
        return False
    
    return True

def test_credentials_file():
    """Проверка наличия credentials.json"""
    logger.info("🔍 Проверка credentials.json...")
    
    import os
    if not os.path.exists("credentials.json"):
        logger.error("❌ Файл credentials.json НЕ найден в корне проекта")
        logger.error("📖 Следуйте инструкции в GOOGLE_SHEETS_SETUP.md для создания файла")
        return False
    
    logger.info("✅ Файл credentials.json найден")
    
    # Проверка содержимого
    try:
        import json
        with open("credentials.json", "r") as f:
            creds = json.load(f)
        
        required_fields = ["type", "project_id", "private_key", "client_email"]
        for field in required_fields:
            if field not in creds:
                logger.error(f"❌ В credentials.json отсутствует поле: {field}")
                return False
        
        logger.info(f"✅ Service Account Email: {creds['client_email']}")
        logger.info(f"✅ Project ID: {creds['project_id']}")
        
    except json.JSONDecodeError:
        logger.error("❌ credentials.json содержит некорректный JSON")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка чтения credentials.json: {e}")
        return False
    
    return True

def test_authentication():
    """Проверка аутентификации"""
    logger.info("🔍 Проверка аутентификации Google Sheets API...")
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
        client = gspread.authorize(creds)
        
        logger.info("✅ Успешная аутентификация в Google Sheets")
        return client
        
    except FileNotFoundError:
        logger.error("❌ Файл credentials.json не найден")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка аутентификации: {e}")
        logger.error("")
        logger.error("💡 Возможные причины:")
        logger.error("   1. Google Sheets API не включен в Google Cloud Console")
        logger.error("   2. Google Drive API не включен")
        logger.error("   3. Неверный формат credentials.json")
        logger.error("")
        logger.error("📖 См. инструкцию: GOOGLE_SHEETS_SETUP.md")
        return None

def test_create_spreadsheet(client):
    """Тест создания тестовой таблицы"""
    logger.info("🔍 Тест создания тестовой таблицы...")
    
    try:
        test_name = f"Test Bot Sheet {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Создаем тестовую таблицу
        spreadsheet = client.create(test_name)
        logger.info(f"✅ Тестовая таблица создана: {test_name}")
        
        # Получаем URL
        url = spreadsheet.url
        logger.info(f"✅ URL таблицы: {url}")
        
        # Добавляем заголовки
        worksheet = spreadsheet.sheet1
        headers = ["ID", "Название", "Дата", "Статус"]
        worksheet.update('A1:D1', [headers])
        logger.info("✅ Заголовки добавлены")
        
        # Добавляем тестовые данные
        test_data = [
            [1, "Тестовая заявка", datetime.now().strftime('%d.%m.%Y %H:%M'), "✅ Успешно"],
            [2, "Проверка связи", datetime.now().strftime('%d.%m.%Y %H:%M'), "✅ OK"]
        ]
        worksheet.update('A2:D3', test_data)
        logger.info("✅ Тестовые данные добавлены")
        
        # Делаем таблицу публичной (только для чтения)
        spreadsheet.share('', perm_type='anyone', role='reader')
        logger.info("✅ Таблица доступна для просмотра по ссылке")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        logger.info("=" * 60)
        logger.info("")
        logger.info(f"📊 Откройте тестовую таблицу: {url}")
        logger.info("")
        logger.info("💡 Вы можете удалить эту таблицу из Google Drive")
        logger.info("💡 Интеграция настроена правильно и готова к работе!")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблицы: {e}")
        logger.error("")
        logger.error("💡 Возможные причины:")
        logger.error("   1. Google Sheets API не включен")
        logger.error("   2. Недостаточно прав у Service Account")
        logger.error("   3. Проблемы с квотами API")
        return False

def main():
    """Основная функция тестирования"""
    logger.info("=" * 60)
    logger.info("🚀 ТЕСТИРОВАНИЕ GOOGLE SHEETS ИНТЕГРАЦИИ")
    logger.info("=" * 60)
    logger.info("")
    
    # Шаг 1: Проверка библиотек
    if not test_imports():
        logger.error("")
        logger.error("❌ Установите необходимые библиотеки:")
        logger.error("   pip install -r requirements.txt")
        return False
    
    logger.info("")
    
    # Шаг 2: Проверка credentials.json
    if not test_credentials_file():
        return False
    
    logger.info("")
    
    # Шаг 3: Проверка аутентификации
    client = test_authentication()
    if not client:
        return False
    
    logger.info("")
    
    # Шаг 4: Тест создания таблицы
    if not test_create_spreadsheet(client):
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            logger.error("")
            logger.error("=" * 60)
            logger.error("❌ ТЕСТЫ НЕ ПРОЙДЕНЫ")
            logger.error("=" * 60)
            logger.error("")
            logger.error("📖 Следуйте инструкции: GOOGLE_SHEETS_SETUP.md")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Тестирование прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)


