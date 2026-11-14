"""Directorio de locales: resuelve el slug sin local fijado (la lectura de `locales` es abierta)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.errores import LocalNoEncontrado
from minutas.locales.dominio.slug import Slug
from minutas.locales.infraestructura.tablas import LOCALES


class DirectorioDeLocalesSQLAlchemy:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        valor = await self._sesion.scalar(select(LOCALES.c.id).where(LOCALES.c.slug == slug.valor))
        if valor is None:
            raise LocalNoEncontrado(f"No hay un local con el slug '{slug}'")
        return LocalId(valor)
