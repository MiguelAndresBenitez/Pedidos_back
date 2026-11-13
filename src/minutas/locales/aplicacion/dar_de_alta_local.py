"""Caso de uso del owner: dar de alta un local."""

from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp


class DarDeAltaLocal:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(
        self, slug: Slug, nombre: str, whatsapp: Whatsapp, modalidades: frozenset[Modalidad]
    ) -> Local:
        """El id se genera en el dominio y se fija antes del INSERT, como pide RLS."""
        local = crear_local(slug, nombre, whatsapp, modalidades)
        async with self._crear_unidad(local.id) as unidad:
            await unidad.locales.agregar(local)
            await unidad.confirmar()
        return local
