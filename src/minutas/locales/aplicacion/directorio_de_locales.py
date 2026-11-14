"""Puerto del directorio de locales: resuelve un slug sin tener un local fijado."""

from typing import Protocol

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.slug import Slug


class DirectorioDeLocales(Protocol):
    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        """Lanza `LocalNoEncontrado`."""
        ...
