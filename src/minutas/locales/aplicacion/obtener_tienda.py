"""Consulta pública: la tienda detrás de un slug, lista para mostrar."""

from datetime import datetime

from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.aplicacion.vista_de_tienda import VistaDeTienda, crear_vista_de_tienda
from minutas.locales.dominio.slug import Slug


class ObtenerTienda:
    def __init__(self, locales: LocalesPorSlug, almacen: AlmacenDeImagenes) -> None:
        self._locales = locales
        self._almacen = almacen

    async def ejecutar(self, slug: Slug, ahora: datetime) -> VistaDeTienda:
        local = await self._locales.obtener(slug)
        return crear_vista_de_tienda(local, ahora, self._almacen.obtener_url_publica)
