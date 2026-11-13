"""Procesamiento de imágenes con Pillow: valida, corrige orientación, achica y pasa a WebP."""

import asyncio
import io
import struct

from PIL import Image, ImageOps, UnidentifiedImageError

from minutas.locales.dominio.errores import ImagenDemasiadoGrande, ImagenInvalida
from minutas.locales.dominio.imagen import TAMANIO_MAXIMO_DE_IMAGEN, Medidas

FORMATOS_ACEPTADOS = ("JPEG", "PNG", "WEBP")
# Tope de píxeles antes de decodificar: protege de las bombas de descompresión.
MAXIMO_DE_PIXELES = 40_000_000
CALIDAD_WEBP = 85


class ProcesadorDeImagenesConPillow:
    def __init__(self, maximo_de_pixeles: int = MAXIMO_DE_PIXELES) -> None:
        self._maximo_de_pixeles = maximo_de_pixeles

    async def procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        """Corre en un hilo aparte: decodificar y codificar bloquearía el loop."""
        return await asyncio.to_thread(self._procesar, contenido, medidas_maximas)

    def _procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        if len(contenido) > TAMANIO_MAXIMO_DE_IMAGEN:
            raise ImagenDemasiadoGrande("La imagen no puede pesar más de 2 MB")
        try:
            # `open` lee solo el encabezado: el tope se controla antes de decodificar.
            with Image.open(io.BytesIO(contenido), formats=FORMATOS_ACEPTADOS) as original:
                if original.width * original.height > self._maximo_de_pixeles:
                    raise ImagenInvalida("La imagen tiene demasiados píxeles")
                imagen = ImageOps.exif_transpose(original)
                imagen.thumbnail((medidas_maximas.ancho, medidas_maximas.alto))
                salida = io.BytesIO()
                # Re-codificar descarta los metadatos (EXIF, GPS) del original.
                imagen.save(salida, format="WEBP", quality=CALIDAD_WEBP)
        # Los archivos corruptos hacen que Pillow lance, según el formato, cualquiera de estos.
        except (
            UnidentifiedImageError,
            OSError,
            EOFError,
            ValueError,
            SyntaxError,
            struct.error,
            Image.DecompressionBombError,
        ) as error:
            raise ImagenInvalida("La imagen tiene que ser un JPEG, PNG o WebP válido") from error
        return salida.getvalue()
