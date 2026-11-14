import io
import os
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from minutas.locales.dominio.errores import (
    ImagenDemasiadoGrande,
    ImagenInvalida,
    ImagenNoEncontrada,
)
from minutas.locales.dominio.imagen import (
    TAMANIO_MAXIMO_DE_IMAGEN,
    Medidas,
    NombreDeImagen,
    TipoDeImagen,
)
from minutas.locales.infraestructura.almacen_de_imagenes_en_disco import AlmacenDeImagenesEnDisco
from minutas.locales.infraestructura.procesador_de_imagenes_con_pillow import (
    ProcesadorDeImagenesConPillow,
)

ORIENTACION = 0x0112
GPS = 0x8825


def imagen(ancho: int, alto: int, formato: str = "JPEG", orientacion: int | None = None) -> bytes:
    original = Image.new("RGB", (ancho, alto), "red")
    exif = Image.Exif()
    if orientacion is not None:
        exif[ORIENTACION] = orientacion
    exif[GPS] = {1: "S"}
    salida = io.BytesIO()
    original.save(salida, format=formato, exif=exif)
    return salida.getvalue()


def abrir(contenido: bytes) -> Image.Image:
    return Image.open(io.BytesIO(contenido))


@pytest.fixture
def procesador() -> ProcesadorDeImagenesConPillow:
    return ProcesadorDeImagenesConPillow()


async def test_procesar_achica_el_logo_y_lo_pasa_a_webp(
    procesador: ProcesadorDeImagenesConPillow,
) -> None:
    resultado = abrir(
        await procesador.procesar(imagen(1024, 800), TipoDeImagen.LOGO.medidas_maximas)
    )

    assert resultado.format == "WEBP"
    assert resultado.size == (512, 400)


async def test_procesar_limita_la_portada_por_ancho(
    procesador: ProcesadorDeImagenesConPillow,
) -> None:
    contenido = imagen(3200, 1000, "PNG")

    resultado = abrir(await procesador.procesar(contenido, TipoDeImagen.PORTADA.medidas_maximas))

    assert resultado.size == (1600, 500)


async def test_procesar_no_agranda_una_imagen_chica(
    procesador: ProcesadorDeImagenesConPillow,
) -> None:
    resultado = abrir(await procesador.procesar(imagen(100, 50), Medidas(512, 512)))

    assert resultado.size == (100, 50)


async def test_procesar_corrige_la_orientacion_y_descarta_los_metadatos(
    procesador: ProcesadorDeImagenesConPillow,
) -> None:
    # Orientación 6: la foto se ve rotada 90°, así que 300x100 se muestra como 100x300.
    resultado = abrir(await procesador.procesar(imagen(300, 100, orientacion=6), Medidas(512, 512)))

    assert resultado.size == (100, 300)
    assert dict(resultado.getexif()) == {}


@pytest.mark.parametrize("contenido", [b"<svg></svg>", b"GIF89a" + b"\x00" * 32, b""])
async def test_procesar_algo_que_no_es_una_imagen_aceptada_falla(
    procesador: ProcesadorDeImagenesConPillow, contenido: bytes
) -> None:
    with pytest.raises(ImagenInvalida, match="JPEG, PNG o WebP"):
        await procesador.procesar(contenido, Medidas(512, 512))


async def test_procesar_con_demasiados_pixeles_falla_antes_de_decodificar() -> None:
    procesador = ProcesadorDeImagenesConPillow(maximo_de_pixeles=100)

    with pytest.raises(ImagenInvalida, match="demasiados píxeles"):
        await procesador.procesar(imagen(20, 20), Medidas(512, 512))


async def test_procesar_mas_de_2_mb_falla(procesador: ProcesadorDeImagenesConPillow) -> None:
    with pytest.raises(ImagenDemasiadoGrande, match="2 MB"):
        await procesador.procesar(b"\x00" * (TAMANIO_MAXIMO_DE_IMAGEN + 1), Medidas(512, 512))


async def test_guardar_crea_el_directorio_escribe_el_archivo_y_arma_la_url(
    tmp_path: Path,
) -> None:
    almacen = AlmacenDeImagenesEnDisco(tmp_path / "nuevo" / "imagenes", "/api/v1/imagenes")

    nombre = await almacen.guardar(b"webp")

    assert os.listdir(tmp_path / "nuevo" / "imagenes") == [nombre.valor]
    assert almacen.obtener_url_publica(nombre) == f"/api/v1/imagenes/{nombre}"


async def test_obtener_ruta_de_una_imagen_guardada(tmp_path: Path) -> None:
    almacen = AlmacenDeImagenesEnDisco(tmp_path, "/api/v1/imagenes")
    nombre = await almacen.guardar(b"webp")

    assert await almacen.obtener_ruta(nombre) == tmp_path / nombre.valor


async def test_obtener_ruta_de_una_imagen_inexistente_falla(tmp_path: Path) -> None:
    almacen = AlmacenDeImagenesEnDisco(tmp_path, "/api/v1/imagenes")

    with pytest.raises(ImagenNoEncontrada):
        await almacen.obtener_ruta(NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp"))


def png_con_ihdr_corto() -> bytes:
    """PNG cuyo chunk IHDR (con CRC válido) mide 5 bytes en vez de 13: Pillow lanza ValueError."""
    original = imagen(64, 64, "PNG")
    cuerpo = b"\x00" * 5
    chunk = struct.pack(">I", len(cuerpo)) + b"IHDR" + cuerpo
    chunk += struct.pack(">I", zlib.crc32(b"IHDR" + cuerpo))
    return original[:8] + chunk + original[8 + 25 :]


def png_con_datos_corruptos() -> bytes:
    """PNG con el IDAT lleno de basura (CRC válido): Pillow lanza OSError al decodificar."""
    original = imagen(64, 64, "PNG")
    inicio = original.index(b"IDAT") - 4
    basura = b"basura"
    chunk = struct.pack(">I", len(basura)) + b"IDAT" + basura
    chunk += struct.pack(">I", zlib.crc32(b"IDAT" + basura))
    return original[:inicio] + chunk + original[-12:]


@pytest.mark.parametrize(
    "contenido",
    [
        pytest.param(png_con_ihdr_corto(), id="png-con-ihdr-corto"),
        pytest.param(png_con_datos_corruptos(), id="png-con-datos-corruptos"),
        pytest.param(imagen(64, 64, "PNG")[:40], id="png-truncado-en-el-encabezado"),
        pytest.param(imagen(512, 512, "PNG")[:-200], id="png-truncado-al-final"),
        pytest.param(imagen(512, 512, "JPEG")[:-300], id="jpeg-truncado"),
    ],
)
async def test_procesar_archivo_corrupto_es_imagen_invalida(
    procesador: ProcesadorDeImagenesConPillow, contenido: bytes
) -> None:
    with pytest.raises(ImagenInvalida):
        await procesador.procesar(contenido, TipoDeImagen.LOGO.medidas_maximas)
