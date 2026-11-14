"""Caso de uso del owner: suspender un local, por ejemplo por falta de pago."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class SuspenderLocal:
    """Los datos no se tocan: reactivar lo deja como estaba."""

    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug) -> None:
        await self._locales.modificar(slug, Local.suspender)
