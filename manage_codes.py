"""
Скрипт для управления кодами активации
"""
import asyncio
import csv
from decimal import Decimal
from database import async_session_maker, ActivationCode
from sqlalchemy import select, func

async def list_codes():
    """Показать все коды с группировкой по суммам"""
    async with async_session_maker() as session:
        # Получаем статистику по кодам
        query = select(
            ActivationCode.amount,
            func.count(ActivationCode.id).label('total'),
            func.count(ActivationCode.id).filter(ActivationCode.is_used == False).label('available'),
            func.count(ActivationCode.id).filter(ActivationCode.is_used == True).label('used')
        ).group_by(ActivationCode.amount).order_by(ActivationCode.amount)
        
        result = await session.execute(query)
        stats = result.all()
        
        print("📊 Статистика кодов активации:")
        print("-" * 50)
        
        for stat in stats:
            print(f"💰 {stat.amount} USD:")
            print(f"   Всего: {stat.total}")
            print(f"   Доступно: {stat.available}")
            print(f"   Использовано: {stat.used}")
            print()
        
        # Показываем все неиспользованные коды
        unused_query = select(ActivationCode).where(
            ActivationCode.is_used == False
        ).order_by(ActivationCode.amount, ActivationCode.id)
        
        unused_result = await session.execute(unused_query)
        unused_codes = unused_result.scalars().all()
        
        if unused_codes:
            print("🎟️ Доступные коды:")
            print("-" * 50)
            current_amount = None
            for code in unused_codes:
                if code.amount != current_amount:
                    current_amount = code.amount
                    print(f"\n💰 {code.amount} USD:")
                print(f"   {code.code_value}")
        else:
            print("❌ Нет доступных кодов")

async def add_codes_from_csv(filename: str):
    """Добавить коды из CSV файла"""
    try:
        codes_added = 0
        async with async_session_maker() as session:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    code_value = row.get('code_value', '').strip()
                    amount_str = row.get('amount', '').strip()
                    
                    if not code_value or not amount_str:
                        print(f"⚠️ Пропущена строка: {row}")
                        continue
                    
                    try:
                        amount = Decimal(amount_str)
                        
                        # Проверяем, существует ли уже такой код
                        existing_query = select(ActivationCode).where(
                            ActivationCode.code_value == code_value
                        )
                        existing_result = await session.execute(existing_query)
                        existing_code = existing_result.scalar_one_or_none()
                        
                        if existing_code:
                            print(f"⚠️ Код {code_value} уже существует")
                            continue
                        
                        # Создаем новый код
                        code = ActivationCode(
                            code_value=code_value,
                            amount=amount
                        )
                        session.add(code)
                        codes_added += 1
                        
                    except ValueError as e:
                        print(f"⚠️ Ошибка в строке {row}: {e}")
                        continue
                
                await session.commit()
                print(f"✅ Добавлено {codes_added} кодов из файла {filename}")
                
    except FileNotFoundError:
        print(f"❌ Файл {filename} не найден")
    except Exception as e:
        print(f"❌ Ошибка при добавлении кодов: {e}")

async def add_single_code(code_value: str, amount: float):
    """Добавить один код"""
    async with async_session_maker() as session:
        # Проверяем, существует ли уже такой код
        existing_query = select(ActivationCode).where(
            ActivationCode.code_value == code_value
        )
        existing_result = await session.execute(existing_query)
        existing_code = existing_result.scalar_one_or_none()
        
        if existing_code:
            print(f"❌ Код {code_value} уже существует")
            return
        
        # Создаем новый код
        code = ActivationCode(
            code_value=code_value,
            amount=Decimal(str(amount))
        )
        session.add(code)
        await session.commit()
        
        print(f"✅ Код {code_value} для суммы {amount} USD добавлен")

async def delete_code(code_value: str):
    """Удалить код"""
    async with async_session_maker() as session:
        query = select(ActivationCode).where(ActivationCode.code_value == code_value)
        result = await session.execute(query)
        code = result.scalar_one_or_none()
        
        if not code:
            print(f"❌ Код {code_value} не найден")
            return
        
        if code.is_used:
            print(f"⚠️ Код {code_value} уже использован. Удаление невозможно.")
            return
        
        await session.delete(code)
        await session.commit()
        
        print(f"✅ Код {code_value} удален")

async def export_codes_to_csv(filename: str):
    """Экспорт кодов в CSV файл"""
    async with async_session_maker() as session:
        query = select(ActivationCode).order_by(ActivationCode.amount, ActivationCode.id)
        result = await session.execute(query)
        codes = result.scalars().all()
        
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['code_value', 'amount', 'is_used', 'issued_at'])
            
            for code in codes:
                writer.writerow([
                    code.code_value,
                    float(code.amount),
                    code.is_used,
                    code.issued_at.isoformat() if code.issued_at else ''
                ])
        
        print(f"✅ Коды экспортированы в файл {filename}")

def print_help():
    """Показать справку"""
    print("""
🔧 Управление кодами активации

Команды:
  list                    - Показать все коды
  add <code> <amount>     - Добавить один код
  add-csv <filename>      - Добавить коды из CSV файла
  delete <code>           - Удалить код
  export <filename>       - Экспортировать коды в CSV
  help                    - Показать эту справку

Примеры:
  python manage_codes.py list
  python manage_codes.py add "NEW-CODE-123" 50
  python manage_codes.py add-csv codes.csv
  python manage_codes.py delete "OLD-CODE-456"
  python manage_codes.py export backup.csv

Формат CSV файла:
  code_value,amount
  CODE-001,10.00
  CODE-002,25.00
  CODE-003,50.00
""")

async def main():
    """Основная функция"""
    import sys
    
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        await list_codes()
    
    elif command == "add" and len(sys.argv) == 4:
        code_value = sys.argv[2]
        try:
            amount = float(sys.argv[3])
            await add_single_code(code_value, amount)
        except ValueError:
            print("❌ Неверная сумма")
    
    elif command == "add-csv" and len(sys.argv) == 3:
        filename = sys.argv[2]
        await add_codes_from_csv(filename)
    
    elif command == "delete" and len(sys.argv) == 3:
        code_value = sys.argv[2]
        await delete_code(code_value)
    
    elif command == "export" and len(sys.argv) == 3:
        filename = sys.argv[2]
        await export_codes_to_csv(filename)
    
    elif command == "help":
        print_help()
    
    else:
        print("❌ Неверная команда")
        print_help()

if __name__ == "__main__":
    asyncio.run(main())
