"""
Database connection and session management.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Handle SQLite vs Postgres engine arguments
create_args = {"pool_pre_ping": True}
if "sqlite" in settings.database_url:
    create_args["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.database_url, echo=settings.debug, **create_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
