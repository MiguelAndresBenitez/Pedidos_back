"""Sirve las imágenes del almacén en disco. El nombre nunca se repite: caché de un año."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from minutas.api.dependencias import LectorInyectado
from minutas.api.rutas_publicas import RUTA_DE_IMAGENES
from minutas.locales.dominio.errores import ImagenInvalida, ImagenNoEncontrada
from minutas.locales.dominio.imagen import NombreDeImagen

router_de_imagenes = APIRouter(prefix=RUTA_DE_IMAGENES, tags=["imagenes"])

CACHE_DE_IMAGENES = "public, max-age=31536000, immutable"


@router_de_imagenes.get("/{nombre}")
async def obtener_imagen(nombre: str, lector: LectorInyectado) -> FileResponse:
    """El nombre se valida antes de tocar el disco: no se puede salir del directorio.

    Con S3 + CDN esta ruta se va: el almacén devuelve la URL del bucket.
    """
    try:
        valido = NombreDeImagen(nombre)
    except ImagenInvalida as error:
        raise ImagenNoEncontrada("La imagen no existe") from error
    ruta = await lector.obtener_ruta(valido)
    return FileResponse(ruta, media_type="image/webp", headers={"Cache-Control": CACHE_DE_IMAGENES})
