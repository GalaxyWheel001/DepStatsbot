# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем директории для логов и загрузок
RUN mkdir -p logs uploads

# Устанавливаем права на запись
RUN chmod 755 logs uploads

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash bot
RUN chown -R bot:bot /app
USER bot

# Открываем порт для webhook (если используется)
EXPOSE 8443

# Команда запуска
CMD ["python", "main.py"]
