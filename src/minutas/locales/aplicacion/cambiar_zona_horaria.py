"""Caso de uso del owner: cambiar la zona horaria. Rige desde la próxima jornada."""

from datetime import date, datetime

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.zona_horaria import ZonaHoraria


class CambiarZonaHoraria:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug, zona: ZonaHoraria, ahora: datetime) -> date:
        """Devuelve la jornada desde la que rige la zona nueva."""
        return await self._locales.modificar(
            slug, lambda local: local.cambiar_zona_horaria(zona, ahora)
        )
