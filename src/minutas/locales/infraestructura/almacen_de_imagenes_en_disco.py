"""Almacén de imágenes en un directorio (un volumen en Docker), servidas por la API."""

import asyncio
import os
import tempfile
from pathlib import Path

from minutas.compartido.dominio.identificador import Identificador
from minutas.locales.dominio.errores import ImagenNoEncontrada
from minutas.locales.dominio.imagen import NombreDeImagen


class AlmacenDeImagenesEnDisco:
    """Implementa `AlmacenDeImagenes` (casos de uso) y `LectorDeImagenes` (API)."""

    def __init__(self, directorio: Path, url_base: str) -> None:
        """`url_base`: ruta donde la API publica el directorio (`/api/v1/imagenes`)."""
        self._directorio = directorio
        self._url_base = url_base

    async def guardar(self, contenido: bytes) -> NombreDeImagen:
        nombre = NombreDeImagen(f"{Identificador.generar()}.webp")
        await asyncio.to_thread(self._escribir, nombre, contenido)
        return nombre

    def obtener_url_publica(self, nombre: NombreDeImagen) -> str:
        return f"{self._url_base}/{nombre}"

    async def obtener_ruta(self, nombre: NombreDeImagen) -> Path:
        ruta = self._directorio / nombre.valor
        if not await asyncio.to_thread(ruta.is_file):
            raise ImagenNoEncontrada("La imagen no existe")
        return ruta

    def _escribir(self, nombre: NombreDeImagen, contenido: bytes) -> None:
        """Escritura atómica: quien sirve la imagen nunca ve un archivo a medio escribir.

        El directorio se crea recién acá: un comando que no usa imágenes no lo necesita.
        """
        self._directorio.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=self._directorio, suffix=".parcial")
        try:
            with os.fdopen(descriptor, "wb") as archivo:
                archivo.write(contenido)
            os.replace(temporal, self._directorio / nombre.valor)
        except BaseException:
            Path(temporal).unlink(missing_ok=True)
            raise
