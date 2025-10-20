@echo off
cd /d "%~dp0"
echo ==========================================
echo   ЗАПУСК TELEGRAM БОТА (УЛУЧШЕННАЯ ВЕРСИЯ)
echo ==========================================
echo.
echo Директория: %CD%
echo.
python --version
echo.
echo Новые возможности:
echo  - Мультиязычность (RU/EN/UR)
echo  - Главное меню
echo  - Подтверждение данных
echo  - Таймаут 15 минут
echo  - Автоуведомления
echo.
echo Запуск бота...
echo.
python main.py
echo.
echo.
echo Бот остановлен. Нажмите любую клавишу...
pause
