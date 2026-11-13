"""Puertos de unidad de trabajo: una transacción, de plataforma o atada a un local."""

from types import TracebackType
from typing import Protocol, Self

from minutas.compartido.dominio.local_id import LocalId


class UnidadDeTrabajoDePlataforma(Protocol):
    """Transacción sin tenant, para las tablas de plataforma (locales, usuarios, sesiones)."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    async def confirmar(self) -> None: ...


class UnidadDeTrabajo(UnidadDeTrabajoDePlataforma, Protocol):
    """Transacción atada a un local: base de las unidades de trabajo con RLS."""

    @property
    def local_id(self) -> LocalId: ...
