"""Caso de uso del owner: reactivar un local suspendido. Sus datos quedaron intactos."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class ReactivarLocal:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug) -> None:
        await self._locales.modificar(slug, Local.reactivar)
