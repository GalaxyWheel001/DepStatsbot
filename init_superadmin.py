"""
Скрипт для инициализации суперадминистратора
Запустите один раз после создания базы данных
"""
import asyncio
from database import DatabaseManager, async_session_maker, create_tables
from config import ADMIN_IDS
from loguru import logger

async def main():
    """Инициализация суперадминистраторов из ADMIN_IDS"""
    
    logger.info("🚀 Инициализация суперадминистраторов...")
    
    # Создаем таблицы если их нет
    await create_tables()
    
    if not ADMIN_IDS:
        logger.error("❌ ADMIN_IDS пуст в конфигурации!")
        logger.info("💡 Добавьте ID админов в .env файл: ADMIN_IDS=123456789,987654321")
        return
    
    logger.info(f"📋 Найдено {len(ADMIN_IDS)} ID в ADMIN_IDS: {ADMIN_IDS}")
    
    added_count = 0
    existing_count = 0
    
    for admin_id in ADMIN_IDS:
        async with async_session_maker() as session:
            # Проверяем, существует ли уже
            role = await DatabaseManager.get_admin_role(session, admin_id)
            
            if not role:
                # Добавляем как суперадмина
                await DatabaseManager.add_admin(session, admin_id, "superadmin", added_by=None)
                logger.info(f"✅ Суперадмин {admin_id} добавлен")
                added_count += 1
            else:
                logger.info(f"ℹ️  Админ {admin_id} уже существует с ролью: {role}")
                existing_count += 1
    
    logger.info("")
    logger.info("="*50)
    logger.info("📊 ИТОГИ:")
    logger.info(f"   • Добавлено новых суперадминов: {added_count}")
    logger.info(f"   • Уже существовало: {existing_count}")
    logger.info(f"   • Всего суперадминов: {len(ADMIN_IDS)}")
    logger.info("="*50)
    logger.info("")
    
    if added_count > 0:
        logger.info("🎉 Суперадминистраторы успешно инициализированы!")
        logger.info("")
        logger.info("📝 Теперь эти пользователи могут:")
        logger.info("   • Использовать команду /admin для доступа к админ-панели")
        logger.info("   • Подтверждать/отклонять заявки")
        logger.info("   • Просматривать статистику")
        logger.info("   • Экспортировать данные в Google Sheets")
        logger.info("   • Управлять администраторами (добавлять/удалять)")
        logger.info("   • Видеть список всех администраторов")
        logger.info("")
        logger.info("💡 Для управления администраторами:")
        logger.info("   1. Используйте /admin")
        logger.info("   2. Перейдите в 'Настройки'")
        logger.info("   3. Нажмите 'Управление админами'")
        logger.info("")
        logger.info("🚀 Запустите бота: python main.py")
    else:
        logger.info("✅ Все суперадминистраторы уже настроены!")
        logger.info("💡 Используйте /admin для доступа к админ-панели")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️  Прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

