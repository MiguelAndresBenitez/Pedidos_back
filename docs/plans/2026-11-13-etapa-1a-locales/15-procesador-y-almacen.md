# Tarea 15: Procesador de imágenes con Pillow y almacén en disco

**Archivos:**
- Crear: `src/minutas/locales/infraestructura/procesador_de_imagenes_con_pillow.py`
- Crear: `src/minutas/locales/infraestructura/almacen_de_imagenes_en_disco.py`
- Test: `tests/unitarios/locales/test_procesador_y_almacen.py`

---

## Decisiones de diseño

**¿Qué hace el procesador, y en qué orden?**
1. Rechaza más de 2 MB.
2. Abre con Pillow solo como JPEG, PNG o WebP (`formats=`), lo que valida que sea una imagen real.
3. Controla el tope de píxeles con el encabezado, antes de decodificar: protege de las bombas de descompresión.
4. Corrige la orientación EXIF, achica a las medidas del tipo y re-codifica a WebP, lo que descarta los metadatos (incluido el GPS).
- Corre en un hilo aparte: decodificar bloquearía el loop.

**¿Y el almacén?**
- Nombre `<uuid7>.webp`, escritura atómica (temporal y `os.replace`) y la URL pública armada con la ruta donde la API publica el directorio. Crea el directorio en el primer `guardar`: un comando que no usa imágenes no lo necesita.
- También implementa `LectorDeImagenes.obtener_ruta`, que la API usa para servir el archivo (tarea 18): quién sabe dónde están los archivos es solo el almacén. Con S3 + CDN entra otro adaptador con su propia URL y la ruta de la API se va.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_procesador_y_almacen.py`:

```python
import io
import os
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
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_procesador_y_almacen.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.infraestructura.almacen_de_imagenes_en_disco'`

## Paso 3: Implementación

`src/minutas/locales/infraestructura/procesador_de_imagenes_con_pillow.py`:

```python
"""Procesamiento de imágenes con Pillow: valida, corrige orientación, achica y pasa a WebP."""

import asyncio
import io

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
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise ImagenInvalida("La imagen tiene que ser un JPEG, PNG o WebP válido") from error
        return salida.getvalue()
```

`src/minutas/locales/infraestructura/almacen_de_imagenes_en_disco.py`:

```python
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
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_procesador_y_almacen.py -v && uv run mypy`
Expected: PASS (12 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/infraestructura/procesador_de_imagenes_con_pillow.py src/minutas/locales/infraestructura/almacen_de_imagenes_en_disco.py tests/unitarios/locales/test_procesador_y_almacen.py
git commit -m "feat(locales): procesamiento de imágenes a webp y almacén en disco" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
