from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.services.settings.main import settings

engine = create_async_engine(
    settings.DATABASE_ASYNC_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,  # 30 minutes
)
async_session_maker = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
