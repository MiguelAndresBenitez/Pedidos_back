"""Puerto para servir imágenes guardadas en disco: lo usa la API, no los casos de uso."""

from pathlib import Path
from typing import Protocol

from minutas.locales.dominio.imagen import NombreDeImagen


class LectorDeImagenes(Protocol):
    async def obtener_ruta(self, nombre: NombreDeImagen) -> Path:
        """Lanza `ImagenNoEncontrada` si no existe."""
        ...
