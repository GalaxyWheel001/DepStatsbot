"""
Проверка проекта на случайно оставленные секреты
Запускайте перед git push!
"""
import os
import re
from pathlib import Path

# Опасные паттерны
DANGEROUS_PATTERNS = [
    (r'"private_key":\s*"-----BEGIN PRIVATE KEY-----', "Приватный ключ Google"),
    (r'BOT_TOKEN\s*=\s*["\'][0-9]+:[A-Za-z0-9_-]{35}', "Токен бота Telegram"),
    (r'[0-9]{10,}:[A-Z]+:[A-Za-z0-9_-]+', "Payment Provider Token"),
    (r'"client_email":\s*"[^@]+@[^"]+\.iam\.gserviceaccount\.com"', "Service Account Email (проверьте контекст)"),
]

# Файлы которые НЕ должны существовать в репозитории
FORBIDDEN_FILES = [
    'credentials.json',
    'token.json',
    'token.pickle',
    '.env',
]

# Исключения (эти файлы можно)
ALLOWED_FILES = [
    'example-credentials.json',
    'env.example',
    '.env.example',
]

def check_file_content(file_path):
    """Проверка содержимого файла на секреты"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        found_secrets = []
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, content):
                found_secrets.append((file_path, description))
        
        return found_secrets
    except:
        return []

def main():
    print("\n" + "="*70)
    print("🔍 ПРОВЕРКА НА УТЕЧКИ СЕКРЕТОВ")
    print("="*70 + "\n")
    
    errors = []
    warnings = []
    
    # Проверка 1: Запрещенные файлы
    print("1️⃣ Проверка запрещенных файлов...")
    for forbidden_file in FORBIDDEN_FILES:
        if os.path.exists(forbidden_file) and forbidden_file not in ALLOWED_FILES:
            # Проверяем что файл в .gitignore
            try:
                with open('.gitignore', 'r') as f:
                    gitignore = f.read()
                if forbidden_file in gitignore:
                    print(f"   ⚠️  {forbidden_file} существует (но в .gitignore ✅)")
                else:
                    errors.append(f"❌ {forbidden_file} НЕ В .gitignore!")
            except:
                errors.append(f"❌ {forbidden_file} найден и .gitignore не читается!")
    
    # Проверка 2: Сканирование содержимого файлов
    print("\n2️⃣ Сканирование .py и .json файлов...")
    
    python_files = list(Path('.').glob('*.py'))
    json_files = list(Path('.').glob('*.json'))
    
    for file_path in python_files + json_files:
        if file_path.name in ALLOWED_FILES:
            continue
        
        secrets = check_file_content(file_path)
        if secrets:
            for fp, desc in secrets:
                # Проверяем что это не example файл
                if 'example' not in str(fp).lower():
                    errors.append(f"❌ {fp}: найден {desc}")
                else:
                    warnings.append(f"⚠️  {fp}: найден {desc} (но это example файл)")
    
    # Проверка 3: .gitignore настроен
    print("\n3️⃣ Проверка .gitignore...")
    try:
        with open('.gitignore', 'r') as f:
            gitignore = f.read()
        
        required_entries = ['credentials.json', '.env', 'token.json']
        missing = []
        
        for entry in required_entries:
            if entry not in gitignore:
                missing.append(entry)
        
        if missing:
            errors.append(f"❌ .gitignore не содержит: {', '.join(missing)}")
        else:
            print("   ✅ .gitignore настроен правильно")
    except:
        errors.append("❌ .gitignore не найден!")
    
    # Результаты
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ")
    print("="*70 + "\n")
    
    if errors:
        print("🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:\n")
        for error in errors:
            print(f"   {error}")
        print()
    
    if warnings:
        print("⚠️  ПРЕДУПРЕЖДЕНИЯ:\n")
        for warning in warnings:
            print(f"   {warning}")
        print()
    
    if not errors and not warnings:
        print("✅ Проверка пройдена! Секретов не найдено.")
        print("\n💡 Можно безопасно делать git push")
    elif not errors:
        print("✅ Критических проблем не найдено")
        print("⚠️  Есть предупреждения, но они не критичны")
    else:
        print("❌ НАЙДЕНЫ ПРОБЛЕМЫ!")
        print("\n🚫 НЕ ДЕЛАЙТЕ git push до исправления!")
        print("\n💡 Исправьте проблемы и запустите проверку снова:")
        print("   python check_secrets.py")
    
    print("\n" + "="*70 + "\n")
    
    return 0 if not errors else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

