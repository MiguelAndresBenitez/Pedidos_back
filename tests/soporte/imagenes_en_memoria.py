"""Dobles del procesador, el almacén y el lector de imágenes."""

from pathlib import Path

from minutas.compartido.dominio.identificador import Identificador
from minutas.locales.dominio.errores import ImagenNoEncontrada
from minutas.locales.dominio.imagen import Medidas, NombreDeImagen


class ProcesadorDeImagenesFalso:
    """Devuelve el contenido marcado con las medidas pedidas, sin procesar nada."""

    async def procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        return f"webp {medidas_maximas.ancho}x{medidas_maximas.alto}:".encode() + contenido


class AlmacenDeImagenesEnMemoria:
    def __init__(self) -> None:
        self.imagenes: dict[NombreDeImagen, bytes] = {}

    async def guardar(self, contenido: bytes) -> NombreDeImagen:
        nombre = NombreDeImagen(f"{Identificador.generar()}.webp")
        self.imagenes[nombre] = contenido
        return nombre

    def obtener_url_publica(self, nombre: NombreDeImagen) -> str:
        return f"/api/v1/imagenes/{nombre}"


class LectorSinImagenes:
    """Para los tests que no sirven archivos: ninguna imagen existe."""

    async def obtener_ruta(self, nombre: NombreDeImagen) -> Path:
        raise ImagenNoEncontrada("La imagen no existe")
