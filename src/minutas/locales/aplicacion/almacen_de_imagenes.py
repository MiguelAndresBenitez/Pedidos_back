"""Puerto del almacén de imágenes de los locales."""

from typing import Protocol

from minutas.locales.dominio.imagen import NombreDeImagen


class AlmacenDeImagenes(Protocol):
    async def guardar(self, contenido: bytes) -> NombreDeImagen:
        """Guarda una imagen WebP con un nombre nuevo y único."""
        ...

    def obtener_url_publica(self, nombre: NombreDeImagen) -> str:
        """URL completa con la que el front muestra la imagen."""
        ...
