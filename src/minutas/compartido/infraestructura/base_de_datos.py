"""Motor y fábrica de sesiones de SQLAlchemy sobre asyncpg."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def crear_motor(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def crear_fabrica_de_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, expire_on_commit=False)
