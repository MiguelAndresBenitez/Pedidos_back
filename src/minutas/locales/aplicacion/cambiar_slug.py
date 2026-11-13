"""Caso de uso del owner: cambiar el link de la tienda. Los links viejos dejan de funcionar."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.slug import Slug


class CambiarSlug:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug, nuevo: Slug) -> None:
        await self._locales.modificar(slug, lambda local: local.cambiar_slug(nuevo))
