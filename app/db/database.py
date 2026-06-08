from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.config import settings


# ─── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,           # verify connections before use
    pool_size=10,
    max_overflow=20,
    connect_args={"ssl": "require"},  # Supabase requires SSL
)

# ─── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ─── Base Model ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─── Dependency ────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Init DB ───────────────────────────────────────────────────────────────────
async def create_tables() -> None:
    """Create all tables if they don't exist (idempotent)."""
    async with engine.begin() as conn:
        from app.db import models  # noqa: F401 — import so models are registered
        await conn.run_sync(Base.metadata.create_all)
