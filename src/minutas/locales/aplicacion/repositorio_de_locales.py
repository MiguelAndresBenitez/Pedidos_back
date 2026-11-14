"""Puerto del repositorio de locales. Trabaja sobre el local fijado en la unidad de trabajo."""

from typing import Protocol

from minutas.locales.dominio.local import Local


class RepositorioDeLocales(Protocol):
    async def obtener(self) -> Local:
        """El local fijado, con sus franjas. Lanza `LocalNoEncontrado`.

        Recuerda la versión leída: el bloqueo optimista compara contra ella al guardar.
        """
        ...

    async def agregar(self, local: Local) -> None:
        """Lanza `SlugEnUso` si otro local ya tiene ese slug."""
        ...

    async def guardar(self, local: Local) -> None:
        """Bloqueo optimista: lanza `LocalModificadoEnParalelo` si cambió desde que se leyó.

        Lanza `SlugEnUso` si otro local ya tiene ese slug. Exige haber obtenido o agregado
        el local en la misma unidad de trabajo.
        """
        ...
