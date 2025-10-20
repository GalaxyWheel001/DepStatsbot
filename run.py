#!/usr/bin/env python3
"""
Скрипт для быстрого запуска и настройки бота
"""
import os
import sys
import asyncio
import subprocess
from pathlib import Path

def check_requirements():
    """Проверка установленных зависимостей"""
    print("🔍 Проверка зависимостей...")
    
    try:
        import aiogram
        import sqlalchemy
        import loguru
        print("✅ Все зависимости установлены")
        return True
    except ImportError as e:
        print(f"❌ Отсутствует зависимость: {e}")
        print("💡 Установите зависимости: pip install -r requirements.txt")
        return False

def check_env_file():
    """Проверка файла конфигурации"""
    print("🔍 Проверка конфигурации...")
    
    if not os.path.exists('.env'):
        if os.path.exists('env.example'):
            print("📝 Создание файла .env из примера...")
            with open('env.example', 'r', encoding='utf-8') as src:
                content = src.read()
            with open('.env', 'w', encoding='utf-8') as dst:
                dst.write(content)
            print("✅ Файл .env создан. Отредактируйте его перед запуском.")
            return False
        else:
            print("❌ Файл .env не найден и нет примера")
            return False
    
    # Проверяем основные переменные
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'BOT_TOKEN=your_bot_token_here' in content:
        print("⚠️ Необходимо настроить BOT_TOKEN в файле .env")
        return False
    
    if 'ADMIN_IDS=123456789,987654321' in content:
        print("⚠️ Необходимо настроить ADMIN_IDS в файле .env")
        return False
    
    print("✅ Конфигурация проверена")
    return True

def create_directories():
    """Создание необходимых директорий"""
    print("📁 Создание директорий...")
    
    directories = ['uploads', 'logs', 'ssl']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Директория {directory}/ создана")

async def init_database():
    """Инициализация базы данных"""
    print("🗄️ Инициализация базы данных...")
    
    try:
        from init_db import main as init_main
        await init_main()
        print("✅ База данных инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

def show_help():
    """Показать справку"""
    print("""
🤖 Telegram Bot для системы депозитов

Использование:
  python run.py setup    - Первоначальная настройка
  python run.py start    - Запуск бота
  python run.py test     - Запуск тестов
  python run.py codes    - Управление кодами
  python run.py help     - Показать эту справку

Команды настройки:
  python run.py setup    - Полная настройка с нуля
  python run.py init-db  - Только инициализация БД
  python run.py check    - Проверка конфигурации

Команды управления:
  python run.py codes list              - Показать коды
  python run.py codes add "CODE" 50     - Добавить код
  python run.py codes add-csv file.csv  - Добавить из CSV
  python run.py codes export file.csv   - Экспорт в CSV

Примеры:
  python run.py setup
  python run.py start
  python run.py codes list
  python run.py codes add "NEW-CODE-123" 100
""")

async def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "help":
        show_help()
    
    elif command == "setup":
        print("🚀 Настройка бота...")
        
        # Проверяем зависимости
        if not check_requirements():
            return
        
        # Создаем директории
        create_directories()
        
        # Проверяем конфигурацию
        if not check_env_file():
            print("\n📝 Настройте файл .env и запустите снова:")
            print("   python run.py setup")
            return
        
        # Инициализируем базу данных
        if await init_database():
            print("\n🎉 Настройка завершена!")
            print("💡 Теперь можете запустить бота: python run.py start")
        else:
            print("\n❌ Ошибка настройки")
    
    elif command == "start":
        print("🚀 Запуск бота...")
        
        if not check_requirements():
            return
        
        if not check_env_file():
            print("❌ Сначала выполните настройку: python run.py setup")
            return
        
        # Запускаем бота
        try:
            from main import main as bot_main
            await bot_main()
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен")
        except Exception as e:
            print(f"❌ Ошибка запуска: {e}")
    
    elif command == "test":
        print("🧪 Запуск тестов...")
        
        if not check_requirements():
            return
        
        try:
            from test_bot import main as test_main
            await test_main()
        except Exception as e:
            print(f"❌ Ошибка тестирования: {e}")
    
    elif command == "init-db":
        print("🗄️ Инициализация базы данных...")
        await init_database()
    
    elif command == "check":
        print("🔍 Проверка конфигурации...")
        check_requirements()
        check_env_file()
        create_directories()
    
    elif command == "codes":
        if len(sys.argv) < 3:
            print("❌ Укажите команду для управления кодами")
            print("💡 Доступные команды: list, add, add-csv, export, delete")
            return
        
        # Запускаем скрипт управления кодами
        try:
            from manage_codes import main as codes_main
            # Передаем аргументы без первого (run.py)
            sys.argv = sys.argv[1:]
            await codes_main()
        except Exception as e:
            print(f"❌ Ошибка управления кодами: {e}")
    
    else:
        print(f"❌ Неизвестная команда: {command}")
        show_help()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
