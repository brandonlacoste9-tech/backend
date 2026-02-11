"""Database session and engine setup."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base

# Allow Railway (and other hosts) to provide a standard Postgres URL like
# postgresql://user:pass@host:port/dbname and upgrade it to asyncpg when needed.
_database_url = settings.DATABASE_URL
if _database_url.startswith("postgresql://") and "+asyncpg" not in _database_url:
    _database_url = _database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _database_url,
    echo=settings.DEBUG,
    future=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
