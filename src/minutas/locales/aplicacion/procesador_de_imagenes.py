"""Puerto del procesador de imágenes: valida, achica y re-codifica lo que sube el local."""

from typing import Protocol

from minutas.locales.dominio.imagen import Medidas


class ProcesadorDeImagenes(Protocol):
    async def procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        """Devuelve un WebP sin metadatos dentro de las medidas.

        Lanza `ImagenInvalida` o `ImagenDemasiadoGrande`.
        """
        ...
