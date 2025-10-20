#!/bin/bash
# Проверка перед коммитом - блокирует коммит если найдены секреты

echo "🔍 Проверка на секреты..."

# Проверяем credentials.json
if git diff --cached --name-only | grep -E "credentials\.json|token\.json|\.env$"; then
    echo "❌ ОШИБКА: Попытка закоммитить секретные файлы!"
    echo ""
    echo "Найдены:"
    git diff --cached --name-only | grep -E "credentials\.json|token\.json|\.env$"
    echo ""
    echo "Эти файлы НЕ должны попадать в Git!"
    echo ""
    exit 1
fi

# Проверяем приватные ключи в staged файлах
if git diff --cached | grep -E "BEGIN (PRIVATE|RSA) KEY|service_account.*private_key"; then
    echo "❌ ОШИБКА: Найден приватный ключ в staged изменениях!"
    echo ""
    echo "Проверьте файлы на наличие приватных ключей"
    echo ""
    exit 1
fi

echo "✅ Проверка пройдена"
exit 0

