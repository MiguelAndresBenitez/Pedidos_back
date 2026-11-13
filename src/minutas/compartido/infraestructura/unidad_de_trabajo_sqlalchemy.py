"""Unidades de trabajo sobre SQLAlchemy. Son de un solo uso."""

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId

FIJAR_LOCAL = text("SELECT set_config('app.local_id', :local_id, true)")


class UnidadDeTrabajoDePlataformaSQLAlchemy:
    """Transacción sin tenant: solo ve las tablas de plataforma, que no tienen RLS."""

    def __init__(self, fabrica_de_sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesion = fabrica_de_sesiones()

    @property
    def sesion(self) -> AsyncSession:
        return self._sesion

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            await self._sesion.rollback()
        finally:
            await self._sesion.close()

    async def confirmar(self) -> None:
        await self._sesion.commit()


class UnidadDeTrabajoSQLAlchemy(UnidadDeTrabajoDePlataformaSQLAlchemy):
    """Transacción que fija el tenant para RLS al entrar."""

    def __init__(
        self, fabrica_de_sesiones: async_sessionmaker[AsyncSession], local_id: LocalId
    ) -> None:
        super().__init__(fabrica_de_sesiones)
        self._local_id = local_id

    @property
    def local_id(self) -> LocalId:
        return self._local_id

    async def __aenter__(self) -> Self:
        try:
            await self._sesion.execute(FIJAR_LOCAL, {"local_id": str(self._local_id)})
        except BaseException:
            await self._sesion.close()
            raise
        return self
