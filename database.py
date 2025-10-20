"""
Настройка базы данных и модели
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, 
    Numeric, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import select, func
from loguru import logger
from config import DATABASE_URL

Base = declarative_base()

class Application(Base):
    """Модель заявки на депозит"""
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    login = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default="USD")
    file_id = Column(String(255), nullable=False)
    status = Column(String(20), default="pending", index=True)
    admin_id = Column(BigInteger, nullable=True)
    admin_comment = Column(Text, nullable=True)
    activation_code_id = Column(Integer, ForeignKey("codes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с кодом активации
    activation_code = relationship("ActivationCode", back_populates="application")

class ActivationCode(Base):
    """Модель кода активации"""
    __tablename__ = "codes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code_value = Column(String(50), unique=True, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False, index=True)
    is_used = Column(Boolean, default=False, index=True)
    issued_at = Column(DateTime, nullable=True)
    
    # Связь с заявкой
    application = relationship("Application", back_populates="activation_code")

class UserRateLimit(Base):
    """Модель для отслеживания лимитов пользователей"""
    __tablename__ = "user_rate_limits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    last_request_time = Column(DateTime, nullable=True)
    daily_applications = Column(Integer, default=0)
    last_reset_date = Column(DateTime, default=datetime.utcnow().date)

class UserProfile(Base):
    """Профиль пользователя"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    language = Column(String(5), default="ru")  # ru, en, ur
    first_time = Column(Boolean, default=True)  # первый запуск
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminRole(Base):
    """Роли администраторов"""
    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    role = Column(String(20), nullable=False, default="admin")  # admin, superadmin
    added_by = Column(BigInteger, nullable=True)  # кто добавил
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transaction(Base):
    """История транзакций и действий"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    action = Column(String(50), nullable=False)  # created, approved, rejected, code_issued
    admin_id = Column(BigInteger, nullable=True)
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class AdminLog(Base):
    """Логи действий администраторов (безопасность)"""
    __tablename__ = "admin_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    action = Column(String(100), nullable=False)  # add_admin, remove_admin, add_codes, etc.
    target_id = Column(BigInteger, nullable=True)  # ID цели действия (user_id, code_id и т.д.)
    details = Column(Text, nullable=True)  # Дополнительная информация в JSON
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class BotSettings(Base):
    """Настройки бота"""
    __tablename__ = "bot_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=False)  # JSON для сложных значений
    description = Column(Text, nullable=True)
    updated_by = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Настройка подключения к базе данных
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_tables():
    """Создание таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    """Получение сессии базы данных"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    @staticmethod
    async def create_application(
        session: AsyncSession,
        user_id: int,
        user_name: str,
        login: str,
        amount: float,
        file_id: str
    ) -> Application:
        """Создание новой заявки"""
        application = Application(
            user_id=user_id,
            user_name=user_name,
            login=login,
            amount=amount,
            file_id=file_id,
            status="pending"
        )
        session.add(application)
        await session.commit()
        await session.refresh(application)
        
        # Автосинхронизация с Google Sheets
        try:
            from google_sheets_integration import auto_sync_application
            await auto_sync_application(application, is_new=True)
        except Exception as e:
            logger.warning(f"Не удалось синхронизировать с Google Sheets: {e}")
        
        return application
    
    @staticmethod
    async def get_activation_code(session: AsyncSession, amount: float) -> Optional[ActivationCode]:
        """Получение первого неиспользованного кода для указанной суммы"""
        query = select(ActivationCode).where(
            ActivationCode.amount == amount,
            ActivationCode.is_used == False
        ).order_by(ActivationCode.id).limit(1)
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_code_by_value(session: AsyncSession, code_value: str) -> Optional[ActivationCode]:
        """Получение кода по значению"""
        query = select(ActivationCode).where(ActivationCode.code_value == code_value)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def mark_code_as_used(session: AsyncSession, code_id: int) -> None:
        """Отметить код как использованный"""
        query = select(ActivationCode).where(ActivationCode.id == code_id)
        result = await session.execute(query)
        code = result.scalar_one_or_none()
        
        if code:
            code.is_used = True
            code.issued_at = datetime.utcnow()
            await session.commit()
    
    @staticmethod
    async def update_application_status(
        session: AsyncSession,
        application_id: int,
        status: str,
        admin_id: int = None,
        admin_comment: str = None,
        activation_code_id: int = None
    ) -> Application:
        """Обновление статуса заявки"""
        query = select(Application).where(Application.id == application_id)
        result = await session.execute(query)
        application = result.scalar_one_or_none()
        
        if application:
            application.status = status
            application.updated_at = datetime.utcnow()
            
            if admin_id:
                application.admin_id = admin_id
            if admin_comment:
                application.admin_comment = admin_comment
            if activation_code_id:
                application.activation_code_id = activation_code_id
            
            await session.commit()
            await session.refresh(application)
            
            # Автосинхронизация с Google Sheets
            try:
                from google_sheets_integration import auto_sync_application
                await auto_sync_application(application, is_new=False)
            except Exception as e:
                logger.warning(f"Не удалось синхронизировать с Google Sheets: {e}")
        
        return application
    
    @staticmethod
    async def get_user_applications(session: AsyncSession, user_id: int) -> List[Application]:
        """Получение заявок пользователя"""
        query = select(Application).where(
            Application.user_id == user_id
        ).order_by(Application.created_at.desc())
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_pending_applications(session: AsyncSession) -> List[Application]:
        """Получение всех ожидающих заявок"""
        query = select(Application).where(
            Application.status == "pending"
        ).order_by(Application.created_at)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_application_by_id(session: AsyncSession, application_id: int) -> Optional[Application]:
        """Получение заявки по ID"""
        query = select(Application).where(Application.id == application_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_stats(session: AsyncSession) -> dict:
        """Получение статистики"""
        # Общее количество заявок
        total_apps_query = select(func.count(Application.id))
        total_apps_result = await session.execute(total_apps_query)
        total_apps = total_apps_result.scalar()
        
        # Подтвержденные заявки
        approved_query = select(func.count(Application.id)).where(Application.status == "approved")
        approved_result = await session.execute(approved_query)
        approved = approved_result.scalar()
        
        # Ожидающие заявки
        pending_query = select(func.count(Application.id)).where(Application.status == "pending")
        pending_result = await session.execute(pending_query)
        pending = pending_result.scalar()
        
        # Коды по суммам
        codes_query = select(
            ActivationCode.amount,
            func.count(ActivationCode.id).label('total'),
            func.count(ActivationCode.id).filter(ActivationCode.is_used == False).label('available')
        ).group_by(ActivationCode.amount)
        
        codes_result = await session.execute(codes_query)
        codes_stats = codes_result.all()
        
        return {
            'total_applications': total_apps,
            'approved_applications': approved,
            'pending_applications': pending,
            'codes_by_amount': [
                {
                    'amount': float(row.amount),
                    'total': row.total,
                    'available': row.available
                }
                for row in codes_stats
            ]
        }
    
    @staticmethod
    async def check_user_rate_limit(session: AsyncSession, user_id: int) -> tuple[bool, str]:
        """Проверка лимитов пользователя"""
        now = datetime.utcnow()
        today = now.date()
        
        # Получаем или создаем запись о лимитах пользователя
        query = select(UserRateLimit).where(UserRateLimit.user_id == user_id)
        result = await session.execute(query)
        user_limit = result.scalar_one_or_none()
        
        if not user_limit:
            user_limit = UserRateLimit(
                user_id=user_id,
                last_request_time=None,
                daily_applications=0,
                last_reset_date=today
            )
            session.add(user_limit)
            await session.commit()
        
        # Сброс дневного счетчика если новый день
        # Приводим last_reset_date к типу date для безопасного сравнения
        reset_date = user_limit.last_reset_date
        if isinstance(reset_date, datetime):
            reset_date = reset_date.date()
        
        if reset_date < today:
            user_limit.daily_applications = 0
            user_limit.last_reset_date = today
            await session.commit()
        
        # Проверка лимита заявок в день
        from config import MAX_APPLICATIONS_PER_DAY
        if user_limit.daily_applications >= MAX_APPLICATIONS_PER_DAY:
            return False, f"Вы превысили лимит заявок в день ({MAX_APPLICATIONS_PER_DAY})"
        
        # Проверка rate limit (1 заявка в минуту)
        from config import RATE_LIMIT_PER_MINUTE
        if user_limit.last_request_time:
            time_diff = now - user_limit.last_request_time
            if time_diff < timedelta(minutes=1):
                return False, "Слишком частые запросы. Попробуйте через минуту"
        
        return True, ""
    
    @staticmethod
    async def update_user_rate_limit(session: AsyncSession, user_id: int) -> None:
        """Обновление лимитов пользователя"""
        query = select(UserRateLimit).where(UserRateLimit.user_id == user_id)
        result = await session.execute(query)
        user_limit = result.scalar_one_or_none()
        
        if user_limit:
            user_limit.last_request_time = datetime.utcnow()
            user_limit.daily_applications += 1
            await session.commit()
    
    @staticmethod
    async def get_user_language(session: AsyncSession, user_id: int) -> str:
        """Получение языка пользователя"""
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(query)
        profile = result.scalar_one_or_none()
        
        if profile:
            return profile.language
        
        # Создаем профиль по умолчанию
        profile = UserProfile(user_id=user_id, language="ru", first_time=True)
        session.add(profile)
        await session.commit()
        return "ru"
    
    @staticmethod
    async def is_first_time(session: AsyncSession, user_id: int) -> bool:
        """Проверка первого запуска пользователя"""
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(query)
        profile = result.scalar_one_or_none()
        
        if not profile:
            return True  # Новый пользователь
        
        return profile.first_time
    
    @staticmethod
    async def mark_not_first_time(session: AsyncSession, user_id: int) -> None:
        """Отметить что пользователь уже не первый раз"""
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(query)
        profile = result.scalar_one_or_none()
        
        if profile:
            profile.first_time = False
            profile.updated_at = datetime.utcnow()
            await session.commit()
    
    @staticmethod
    async def set_user_language(session: AsyncSession, user_id: int, language: str) -> None:
        """Установка языка пользователя"""
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(query)
        profile = result.scalar_one_or_none()
        
        if profile:
            profile.language = language
            profile.updated_at = datetime.utcnow()
        else:
            profile = UserProfile(user_id=user_id, language=language)
            session.add(profile)
        
        await session.commit()
    
    @staticmethod
    async def log_transaction(
        session: AsyncSession,
        application_id: int,
        action: str,
        admin_id: int = None,
        comment: str = None
    ) -> None:
        """Логирование транзакции"""
        transaction = Transaction(
            application_id=application_id,
            action=action,
            admin_id=admin_id,
            comment=comment
        )
        session.add(transaction)
        await session.commit()
    
    @staticmethod
    async def get_transaction_history(session: AsyncSession, application_id: int) -> List:
        """Получение истории транзакций для заявки"""
        query = select(Transaction).where(
            Transaction.application_id == application_id
        ).order_by(Transaction.timestamp)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def add_admin(session: AsyncSession, user_id: int, role: str, added_by: int) -> None:
        """Добавление администратора"""
        admin = AdminRole(user_id=user_id, role=role, added_by=added_by)
        session.add(admin)
        await session.commit()
    
    @staticmethod
    async def remove_admin(session: AsyncSession, user_id: int) -> bool:
        """Удаление администратора"""
        query = select(AdminRole).where(AdminRole.user_id == user_id)
        result = await session.execute(query)
        admin = result.scalar_one_or_none()
        
        if admin:
            await session.delete(admin)
            await session.commit()
            return True
        return False
    
    @staticmethod
    async def get_admin_role(session: AsyncSession, user_id: int) -> Optional[str]:
        """Получение роли администратора"""
        query = select(AdminRole).where(AdminRole.user_id == user_id)
        result = await session.execute(query)
        admin = result.scalar_one_or_none()
        
        return admin.role if admin else None
    
    @staticmethod
    async def is_admin(session: AsyncSession, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        role = await DatabaseManager.get_admin_role(session, user_id)
        return role in ["admin", "superadmin"]
    
    @staticmethod
    async def is_superadmin(session: AsyncSession, user_id: int) -> bool:
        """Проверка, является ли пользователь суперадминистратором"""
        role = await DatabaseManager.get_admin_role(session, user_id)
        return role == "superadmin"
    
    @staticmethod
    async def get_all_admins(session: AsyncSession) -> List:
        """Получение списка всех администраторов"""
        query = select(AdminRole).order_by(AdminRole.created_at)
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_stats(session: AsyncSession, days: int = 1) -> dict:
        """Получение статистики по заявкам"""
        from_date = datetime.utcnow() - timedelta(days=days)
        
        # Общее количество заявок
        total_query = select(func.count(Application.id)).where(
            Application.created_at >= from_date
        )
        total_result = await session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Подтвержденные
        confirmed_query = select(func.count(Application.id)).where(
            Application.created_at >= from_date,
            Application.status == "confirmed"
        )
        confirmed_result = await session.execute(confirmed_query)
        confirmed = confirmed_result.scalar() or 0
        
        # Отклоненные
        rejected_query = select(func.count(Application.id)).where(
            Application.created_at >= from_date,
            Application.status == "rejected"
        )
        rejected_result = await session.execute(rejected_query)
        rejected = rejected_result.scalar() or 0
        
        # Ожидают
        pending_query = select(func.count(Application.id)).where(
            Application.created_at >= from_date,
            Application.status == "pending"
        )
        pending_result = await session.execute(pending_query)
        pending = pending_result.scalar() or 0
        
        # Коды по суммам
        codes_by_amount = {}
        for amount in [10, 25, 50, 100]:
            codes_query = select(func.count(ActivationCode.id)).where(
                ActivationCode.amount == amount,
                ActivationCode.is_used == False
            )
            codes_result = await session.execute(codes_query)
            codes_by_amount[amount] = codes_result.scalar() or 0
        
        return {
            "total": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "pending": pending,
            "codes_remaining": codes_by_amount
        }
    
    # ==================== УПРАВЛЕНИЕ КОДАМИ ====================
    
    @staticmethod
    async def add_activation_code(session: AsyncSession, code_value: str, amount: float) -> ActivationCode:
        """Добавление кода активации"""
        code = ActivationCode(code_value=code_value, amount=amount, is_used=False)
        session.add(code)
        await session.commit()
        await session.refresh(code)
        return code
    
    @staticmethod
    async def delete_activation_code(session: AsyncSession, code_id: int) -> bool:
        """Удаление кода активации"""
        query = select(ActivationCode).where(ActivationCode.id == code_id)
        result = await session.execute(query)
        code = result.scalar_one_or_none()
        
        if code:
            await session.delete(code)
            await session.commit()
            return True
        return False
    
    @staticmethod
    async def get_all_codes(session: AsyncSession, only_unused: bool = False) -> List[ActivationCode]:
        """Получение всех кодов активации"""
        if only_unused:
            query = select(ActivationCode).where(ActivationCode.is_used == False).order_by(ActivationCode.amount, ActivationCode.id)
        else:
            query = select(ActivationCode).order_by(ActivationCode.amount, ActivationCode.id)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def import_codes_from_list(session: AsyncSession, codes_data: List[tuple]) -> dict:
        """Импорт кодов из списка [(code_value, amount), ...]"""
        added = 0
        skipped = 0
        errors = []
        
        for code_value, amount in codes_data:
            try:
                # Проверяем, существует ли уже такой код
                existing = await DatabaseManager.get_code_by_value(session, code_value)
                if existing:
                    skipped += 1
                    continue
                
                await DatabaseManager.add_activation_code(session, code_value, float(amount))
                added += 1
            except Exception as e:
                errors.append(f"Ошибка для кода {code_value}: {str(e)}")
        
        return {
            "added": added,
            "skipped": skipped,
            "errors": errors
        }
    
    # ==================== ЛОГИРОВАНИЕ ДЕЙСТВИЙ АДМИНИСТРАТОРОВ ====================
    
    @staticmethod
    async def log_admin_action(
        session: AsyncSession,
        admin_id: int,
        action: str,
        target_id: int = None,
        details: str = None
    ) -> None:
        """Логирование действия администратора"""
        log_entry = AdminLog(
            admin_id=admin_id,
            action=action,
            target_id=target_id,
            details=details
        )
        session.add(log_entry)
        await session.commit()
    
    @staticmethod
    async def get_admin_logs(
        session: AsyncSession,
        admin_id: int = None,
        limit: int = 50,
        days: int = 7
    ) -> List:
        """Получение логов действий администраторов"""
        from_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(AdminLog).where(AdminLog.timestamp >= from_date)
        
        if admin_id:
            query = query.where(AdminLog.admin_id == admin_id)
        
        query = query.order_by(AdminLog.timestamp.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    # ==================== НАСТРОЙКИ БОТА ====================
    
    @staticmethod
    async def get_setting(session: AsyncSession, key: str, default: str = None) -> str:
        """Получение настройки бота"""
        query = select(BotSettings).where(BotSettings.setting_key == key)
        result = await session.execute(query)
        setting = result.scalar_one_or_none()
        
        return setting.setting_value if setting else default
    
    @staticmethod
    async def set_setting(
        session: AsyncSession,
        key: str,
        value: str,
        description: str = None,
        admin_id: int = None
    ) -> None:
        """Установка настройки бота"""
        query = select(BotSettings).where(BotSettings.setting_key == key)
        result = await session.execute(query)
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.setting_value = value
            setting.updated_by = admin_id
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
        else:
            setting = BotSettings(
                setting_key=key,
                setting_value=value,
                description=description,
                updated_by=admin_id
            )
            session.add(setting)
        
        await session.commit()
    
    @staticmethod
    async def get_all_settings(session: AsyncSession) -> List:
        """Получение всех настроек бота"""
        query = select(BotSettings).order_by(BotSettings.setting_key)
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_deposit_amounts(session: AsyncSession) -> List[int]:
        """Получение номиналов депозита из настроек"""
        import json
        amounts_json = await DatabaseManager.get_setting(session, "deposit_amounts")
        
        if amounts_json:
            try:
                return json.loads(amounts_json)
            except:
                pass
        
        # По умолчанию
        from config import DEPOSIT_AMOUNTS
        return DEPOSIT_AMOUNTS
    
    @staticmethod
    async def set_deposit_amounts(session: AsyncSession, amounts: List[int], admin_id: int) -> None:
        """Установка номиналов депозита"""
        import json
        amounts_json = json.dumps(amounts)
        await DatabaseManager.set_setting(
            session,
            "deposit_amounts",
            amounts_json,
            "Доступные номиналы депозита",
            admin_id
        )

# Функция для инициализации базы данных
async def init_database():
    """Инициализация базы данных"""
    await create_tables()
    
    # Создаем директорию для загрузок
    import os
    from config import UPLOAD_DIR
    os.makedirs(UPLOAD_DIR, exist_ok=True)
