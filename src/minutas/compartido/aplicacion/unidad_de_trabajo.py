"""Puerto de unidad de trabajo: una transacción atada a un local."""

from types import TracebackType
from typing import Protocol, Self

from minutas.compartido.dominio.local_id import LocalId


class UnidadDeTrabajo(Protocol):
    """Base de las unidades de trabajo de cada contexto, que suman sus repositorios."""

    @property
    def local_id(self) -> LocalId: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    async def confirmar(self) -> None: ...
