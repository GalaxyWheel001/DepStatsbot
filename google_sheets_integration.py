"""
Интеграция с Google Sheets для автоматического экспорта данных о депозитах
"""
import asyncio
from datetime import datetime
from typing import List, Optional
from loguru import logger

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    logger.warning("Google Sheets библиотеки не установлены. Установите: pip install gspread google-auth")

from database import Application

# Настройки Google Sheets
SPREADSHEET_NAME = "Bot Deposits Data"
CREDENTIALS_FILE = "credentials.json"  # Файл с credentials от Google Cloud

class GoogleSheetsExporter:
    """Класс для работы с Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
    def authenticate(self):
        """Аутентификация в Google Sheets API"""
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError("Google Sheets библиотеки не установлены")
        
        try:
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_file(
                CREDENTIALS_FILE, 
                scopes=scope
            )
            
            self.client = gspread.authorize(creds)
            logger.info("✅ Успешная аутентификация в Google Sheets")
            return True
            
        except FileNotFoundError:
            logger.error(f"❌ Файл {CREDENTIALS_FILE} не найден")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка аутентификации: {e}")
            raise
    
    def get_or_create_spreadsheet(self) -> str:
        """Получить или создать таблицу"""
        try:
            # Пытаемся открыть существующую таблицу
            self.spreadsheet = self.client.open(SPREADSHEET_NAME)
            logger.info(f"✅ Открыта существующая таблица: {SPREADSHEET_NAME}")
        except gspread.SpreadsheetNotFound:
            # Создаем новую таблицу
            self.spreadsheet = self.client.create(SPREADSHEET_NAME)
            self.spreadsheet.share('', perm_type='anyone', role='reader')
            logger.info(f"✅ Создана новая таблица: {SPREADSHEET_NAME}")
        
        # Получаем первый лист или создаем
        try:
            self.worksheet = self.spreadsheet.worksheet("Заявки")
        except gspread.WorksheetNotFound:
            self.worksheet = self.spreadsheet.add_worksheet(
                title="Заявки", 
                rows=1000, 
                cols=15
            )
        
        return self.spreadsheet.url
    
    def setup_headers(self):
        """Настроить заголовки таблицы"""
        headers = [
            "ID",
            "Дата создания",
            "Пользователь",
            "User ID",
            "Логин",
            "Сумма",
            "Валюта",
            "Статус",
            "Метод оплаты",
            "Обработал",
            "Админ ID",
            "Комментарий",
            "Код активации",
            "Дата обновления",
            "Время обработки (мин)",
            "File ID",
            "Ссылка на файл"
        ]
        
        # Устанавливаем заголовки
        self.worksheet.update('A1:Q1', [headers])
        
        # Форматирование заголовков
        self.worksheet.format('A1:Q1', {
            "backgroundColor": {
                "red": 0.2,
                "green": 0.6,
                "blue": 1.0
            },
            "textFormat": {
                "bold": True,
                "foregroundColor": {
                    "red": 1.0,
                    "green": 1.0,
                    "blue": 1.0
                }
            },
            "horizontalAlignment": "CENTER"
        })
        
        # Замораживаем первую строку
        self.worksheet.freeze(rows=1)
        
        logger.info("✅ Заголовки настроены")
    
    def export_applications(self, applications: List[Application]) -> int:
        """Экспортировать заявки в Google Sheets"""
        if not applications:
            logger.warning("Нет заявок для экспорта")
            return 0
        
        # Очищаем все кроме заголовков
        self.worksheet.resize(rows=1)
        self.worksheet.resize(rows=len(applications) + 1)
        
        # Настраиваем заголовки если их нет
        if not self.worksheet.get('A1'):
            self.setup_headers()
        
        # Подготавливаем данные
        rows = []
        for app in applications:
            # Рассчитываем время обработки
            processing_time = ""
            if app.updated_at and app.updated_at != app.created_at:
                delta = app.updated_at - app.created_at
                processing_time = int(delta.total_seconds() / 60)
            
            # Статус на русском
            status_ru = {
                "pending": "⏳ Ожидает",
                "approved": "✅ Одобрена",
                "rejected": "❌ Отклонена",
                "cancelled": "🚫 Отменена",
                "needs_info": "💬 Требует инфо"
            }.get(app.status, app.status)
            
            # Код активации
            code_value = ""
            if app.activation_code:
                code_value = app.activation_code.code_value
            
            # Ссылка на файл в Telegram
            file_url = f"https://api.telegram.org/file/bot<TOKEN>/{app.file_id}" if app.file_id else ""
            
            # Определяем метод оплаты
            payment_method = ""
            if app.file_id == "payment":
                payment_method = "💳 Онлайн-оплата (автоматически)"
            elif app.file_id:
                payment_method = "📄 Загрузка чека (ручная проверка)"
            else:
                payment_method = "❓ Не указан"
            
            # Определяем кто обработал
            processed_by = ""
            if app.admin_id == 0:
                processed_by = "🤖 Автоматически (SmartGlocal)"
            elif app.admin_id:
                # Можно добавить имя админа, если есть
                processed_by = f"👤 Админ ID: {app.admin_id}"
            else:
                processed_by = "⏳ Не обработана"
            
            row = [
                app.id,
                app.created_at.strftime('%d.%m.%Y %H:%M'),
                app.user_name or "",
                app.user_id,
                app.login,
                float(app.amount),
                app.currency,
                status_ru,
                payment_method,
                processed_by,
                app.admin_id if app.admin_id else "",
                app.admin_comment or "",
                code_value,
                app.updated_at.strftime('%d.%m.%Y %H:%M') if app.updated_at else "",
                processing_time,
                app.file_id or "",
                file_url
            ]
            rows.append(row)
        
        # Загружаем все данные одним запросом (быстрее)
        cell_range = f'A2:Q{len(rows) + 1}'
        self.worksheet.update(cell_range, rows)
        
        # Форматирование столбцов
        self.format_worksheet()
        
        logger.info(f"✅ Экспортировано {len(rows)} заявок")
        return len(rows)
    
    def format_worksheet(self):
        """Форматирование таблицы"""
        # Авторазмер столбцов
        self.worksheet.columns_auto_resize(0, 16)
        
        # Форматирование статусов (цветовое кодирование)
        # Это можно расширить с помощью условного форматирования
        
        # Центрирование ID
        self.worksheet.format('A:A', {"horizontalAlignment": "CENTER"})
        
        # Форматирование суммы
        self.worksheet.format('F:F', {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "$#,##0.00"
            }
        })
    
    def add_application(self, application: Application):
        """Добавить одну заявку (для real-time синхронизации)"""
        # Находим последнюю строку
        values = self.worksheet.get_all_values()
        next_row = len(values) + 1
        
        # Подготавливаем данные
        processing_time = ""
        if application.updated_at and application.updated_at != application.created_at:
            delta = application.updated_at - application.created_at
            processing_time = int(delta.total_seconds() / 60)
        
        status_ru = {
            "pending": "⏳ Ожидает",
            "approved": "✅ Одобрена",
            "rejected": "❌ Отклонена",
            "cancelled": "🚫 Отменена"
        }.get(application.status, application.status)
        
        code_value = ""
        if application.activation_code:
            code_value = application.activation_code.code_value
        
        # Определяем метод оплаты
        payment_method = ""
        if application.file_id == "payment":
            payment_method = "💳 Онлайн-оплата (автоматически)"
        elif application.file_id:
            payment_method = "📄 Загрузка чека (ручная проверка)"
        else:
            payment_method = "❓ Не указан"
        
        # Определяем кто обработал
        processed_by = ""
        if application.admin_id == 0:
            processed_by = "🤖 Автоматически (SmartGlocal)"
        elif application.admin_id:
            processed_by = f"👤 Админ ID: {application.admin_id}"
        else:
            processed_by = "⏳ Не обработана"
        
        row = [
            application.id,
            application.created_at.strftime('%d.%m.%Y %H:%M'),
            application.user_name or "",
            application.user_id,
            application.login,
            float(application.amount),
            application.currency,
            status_ru,
            payment_method,
            processed_by,
            application.admin_id if application.admin_id else "",
            application.admin_comment or "",
            code_value,
            application.updated_at.strftime('%d.%m.%Y %H:%M') if application.updated_at else "",
            processing_time,
            application.file_id or "",
            ""
        ]
        
        # Добавляем строку
        self.worksheet.append_row(row)
        logger.info(f"✅ Добавлена заявка #{application.id} в Google Sheets")
    
    def update_application(self, application: Application):
        """Обновить существующую заявку"""
        # Находим строку с этой заявкой
        cell = self.worksheet.find(str(application.id))
        
        if not cell:
            # Если не найдена, добавляем новую
            self.add_application(application)
            return
        
        row_number = cell.row
        
        # Обновляем данные
        processing_time = ""
        if application.updated_at and application.updated_at != application.created_at:
            delta = application.updated_at - application.created_at
            processing_time = int(delta.total_seconds() / 60)
        
        status_ru = {
            "pending": "⏳ Ожидает",
            "approved": "✅ Одобрена",
            "rejected": "❌ Отклонена",
            "cancelled": "🚫 Отменена"
        }.get(application.status, application.status)
        
        code_value = ""
        if application.activation_code:
            code_value = application.activation_code.code_value
        
        # Обновляем нужные ячейки
        updates = [
            {
                'range': f'H{row_number}',  # Статус
                'values': [[status_ru]]
            },
            {
                'range': f'I{row_number}',  # Админ ID
                'values': [[application.admin_id or ""]]
            },
            {
                'range': f'J{row_number}',  # Комментарий
                'values': [[application.admin_comment or ""]]
            },
            {
                'range': f'K{row_number}',  # Код
                'values': [[code_value]]
            },
            {
                'range': f'L{row_number}',  # Дата обновления
                'values': [[application.updated_at.strftime('%d.%m.%Y %H:%M') if application.updated_at else ""]]
            },
            {
                'range': f'M{row_number}',  # Время обработки
                'values': [[processing_time]]
            }
        ]
        
        self.worksheet.batch_update(updates)
        logger.info(f"✅ Обновлена заявка #{application.id} в Google Sheets")


# Глобальный экземпляр экспортера
_exporter: Optional[GoogleSheetsExporter] = None

def get_exporter() -> GoogleSheetsExporter:
    """Получить экземпляр экспортера"""
    global _exporter
    
    if _exporter is None:
        _exporter = GoogleSheetsExporter()
        _exporter.authenticate()
        _exporter.get_or_create_spreadsheet()
    
    return _exporter


# Асинхронные обертки
async def export_applications_to_sheets(applications: List[Application]) -> str:
    """Асинхронный экспорт заявок"""
    loop = asyncio.get_event_loop()
    
    def _export():
        exporter = get_exporter()
        exporter.export_applications(applications)
        return exporter.spreadsheet.url
    
    return await loop.run_in_executor(None, _export)

async def sync_application_to_sheets(application: Application, is_new: bool = False):
    """Синхронизировать одну заявку"""
    if not GOOGLE_SHEETS_AVAILABLE:
        return
    
    loop = asyncio.get_event_loop()
    
    def _sync():
        try:
            exporter = get_exporter()
            if is_new:
                exporter.add_application(application)
            else:
                exporter.update_application(application)
        except Exception as e:
            logger.error(f"Ошибка синхронизации с Google Sheets: {e}")
    
    await loop.run_in_executor(None, _sync)

async def get_spreadsheet_url() -> Optional[str]:
    """Получить URL таблицы"""
    if not GOOGLE_SHEETS_AVAILABLE:
        return None
    
    loop = asyncio.get_event_loop()
    
    def _get_url():
        try:
            exporter = get_exporter()
            return exporter.spreadsheet.url
        except Exception as e:
            logger.error(f"Ошибка получения URL: {e}")
            return None
    
    return await loop.run_in_executor(None, _get_url)


# Хук для автоматической синхронизации
async def auto_sync_application(application: Application, is_new: bool = False):
    """
    Автоматическая синхронизация при создании/обновлении заявки
    Добавьте этот вызов в database.py после создания/обновления заявки
    """
    try:
        await sync_application_to_sheets(application, is_new)
    except Exception as e:
        logger.error(f"Ошибка автосинхронизации: {e}")

