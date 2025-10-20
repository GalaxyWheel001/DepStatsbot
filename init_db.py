"""
Скрипт для инициализации базы данных с тестовыми данными
"""
import asyncio
from decimal import Decimal
from database import init_database, async_session_maker, ActivationCode

async def add_test_codes():
    """Добавление тестовых кодов активации"""
    test_codes = [
        # Коды для 10 USD
        {"code_value": "ACT10-001", "amount": Decimal("10.00")},
        {"code_value": "ACT10-002", "amount": Decimal("10.00")},
        {"code_value": "ACT10-003", "amount": Decimal("10.00")},
        {"code_value": "ACT10-004", "amount": Decimal("10.00")},
        {"code_value": "ACT10-005", "amount": Decimal("10.00")},
        
        # Коды для 25 USD
        {"code_value": "ACT25-001", "amount": Decimal("25.00")},
        {"code_value": "ACT25-002", "amount": Decimal("25.00")},
        {"code_value": "ACT25-003", "amount": Decimal("25.00")},
        {"code_value": "ACT25-004", "amount": Decimal("25.00")},
        {"code_value": "ACT25-005", "amount": Decimal("25.00")},
        
        # Коды для 50 USD
        {"code_value": "ACT50-001", "amount": Decimal("50.00")},
        {"code_value": "ACT50-002", "amount": Decimal("50.00")},
        {"code_value": "ACT50-003", "amount": Decimal("50.00")},
        {"code_value": "ACT50-004", "amount": Decimal("50.00")},
        {"code_value": "ACT50-005", "amount": Decimal("50.00")},
        
        # Коды для 100 USD
        {"code_value": "ACT100-001", "amount": Decimal("100.00")},
        {"code_value": "ACT100-002", "amount": Decimal("100.00")},
        {"code_value": "ACT100-003", "amount": Decimal("100.00")},
        {"code_value": "ACT100-004", "amount": Decimal("100.00")},
        {"code_value": "ACT100-005", "amount": Decimal("100.00")},
        
        # Дополнительные коды для разных сумм
        {"code_value": "CUSTOM-150-001", "amount": Decimal("150.00")},
        {"code_value": "CUSTOM-150-002", "amount": Decimal("150.00")},
        {"code_value": "CUSTOM-200-001", "amount": Decimal("200.00")},
        {"code_value": "CUSTOM-200-002", "amount": Decimal("200.00")},
        {"code_value": "CUSTOM-500-001", "amount": Decimal("500.00")},
    ]
    
    async with async_session_maker() as session:
        # Проверяем, есть ли уже коды
        from sqlalchemy import select
        result = await session.execute(select(ActivationCode))
        existing_codes = result.scalars().all()
        
        if existing_codes:
            print(f"В базе уже есть {len(existing_codes)} кодов. Пропускаем добавление.")
            return
        
        # Добавляем тестовые коды
        for code_data in test_codes:
            code = ActivationCode(**code_data)
            session.add(code)
        
        await session.commit()
        print(f"✅ Добавлено {len(test_codes)} тестовых кодов активации")

async def main():
    """Основная функция инициализации"""
    print("🚀 Инициализация базы данных...")
    
    # Создаем таблицы
    await init_database()
    print("✅ Таблицы созданы")
    
    # Добавляем тестовые коды
    await add_test_codes()
    
    print("🎉 Инициализация завершена!")
    print("\nДоступные команды для тестирования:")
    print("• /start - Начать процесс депозита")
    print("• /status - Проверить статус заявок")
    print("• /help - Справка")
    print("• /stats - Статистика (только для админов)")

if __name__ == "__main__":
    asyncio.run(main())
