"""Acceso a un local por su slug: el directorio lo resuelve y la unidad del local lo carga."""

from collections.abc import Callable

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import (
    FabricaDeUnidadesDelDirectorio,
    FabricaDeUnidadesDelLocal,
)
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class LocalesPorSlug:
    """Colaborador de los casos de uso que reciben un slug (consola del owner y tienda)."""

    def __init__(
        self,
        crear_unidad_del_directorio: FabricaDeUnidadesDelDirectorio,
        crear_unidad_del_local: FabricaDeUnidadesDelLocal,
    ) -> None:
        self._crear_unidad_del_directorio = crear_unidad_del_directorio
        self._crear_unidad_del_local = crear_unidad_del_local

    async def obtener(self, slug: Slug) -> Local:
        """Resuelve el id por slug y carga el local por id.

        Si el slug cambió entre los dos pasos, devuelve el local con el slug nuevo.
        """
        async with self._crear_unidad_del_local(await self._resolver(slug)) as unidad:
            return await unidad.locales.obtener()

    async def modificar[T](self, slug: Slug, cambio: Callable[[Local], T]) -> T:
        """Aplica el cambio en una transacción del local y devuelve lo que el cambio devuelva."""
        async with self._crear_unidad_del_local(await self._resolver(slug)) as unidad:
            local = await unidad.locales.obtener()
            resultado = cambio(local)
            await unidad.locales.guardar(local)
            await unidad.confirmar()
        return resultado

    async def _resolver(self, slug: Slug) -> LocalId:
        async with self._crear_unidad_del_directorio() as unidad:
            return await unidad.directorio.obtener_local_id_por_slug(slug)
