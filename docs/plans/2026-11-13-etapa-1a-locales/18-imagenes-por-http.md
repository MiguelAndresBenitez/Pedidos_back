# Tarea 18: Imágenes servidas por la API

**Archivos:**
- Crear: `src/minutas/api/rutas_de_imagenes.py`
- Modificar: `src/minutas/api/app.py`
- Test: `tests/api/test_imagenes.py`

---

## Decisiones de diseño

**¿Por qué una ruta y no `StaticFiles`?**
- El diseño pide validar el nombre antes de tocar el disco. Con `NombreDeImagen` solo pasa `<uuid7>.webp`: no hay forma de armar una ruta fuera del directorio. Un nombre inválido o inexistente responde `404 imagen_no_encontrada`, sin distinguirlos.
- El archivo lo ubica el `LectorDeImagenes` (el almacén en disco), sin bloquear el loop: la ruta no sabe dónde están los archivos.

**¿Por qué caché de un año?**
- Cada subida genera un nombre nuevo y nunca se reutiliza: `Cache-Control: public, max-age=31536000, immutable`.

**Con S3 + CDN** esta ruta se va: el almacén devuelve la URL del bucket.

---

## Paso 1: Escribir el test que falla

`tests/api/test_imagenes.py`:

```python
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.locales.infraestructura.almacen_de_imagenes_en_disco import AlmacenDeImagenesEnDisco
from soporte.servicios_en_memoria import ServiciosEnMemoria

NOMBRE = "01a18e9b-3c49-75a8-a745-cbce398ad79a.webp"


@pytest.fixture
async def cliente(
    configuracion: Configuracion, memoria: ServiciosEnMemoria, tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    """La app con el lector de disco real sobre una carpeta con una imagen."""
    (tmp_path / NOMBRE).write_bytes(b"RIFF....WEBP")
    lector = AlmacenDeImagenesEnDisco(tmp_path, "/api/v1/imagenes")
    app = crear_app(configuracion, replace(memoria.servicios, lector_de_imagenes=lector))
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


async def test_obtener_imagen_la_sirve_con_cache_de_un_anio(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get(f"/api/v1/imagenes/{NOMBRE}")

    assert respuesta.status_code == 200
    assert respuesta.content == b"RIFF....WEBP"
    assert respuesta.headers["content-type"] == "image/webp"
    assert respuesta.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize(
    "nombre", ["..%2F..%2Fetc%2Fpasswd", "logo.png", "01a18e9b-3c49-75a8-a745-cbce398ad79b.webp"]
)
async def test_obtener_imagen_invalida_o_inexistente_responde_404(
    cliente: httpx.AsyncClient, nombre: str
) -> None:
    respuesta = await cliente.get(f"/api/v1/imagenes/{nombre}")

    assert respuesta.status_code == 404
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/api/test_imagenes.py -v`
Expected: FAIL en el primer test: `assert 404 == 200`

## Paso 3: Implementación

`src/minutas/api/rutas_de_imagenes.py`:

```python
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
```

`src/minutas/api/app.py` queda en su versión final:

`src/minutas/api/app.py`:

```python
"""Fábrica de la aplicación FastAPI: raíz de composición HTTP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from minutas import __version__
from minutas.api.errores_http import registrar_manejadores_de_errores
from minutas.api.middleware_de_solicitud import MiddlewareDeSolicitud
from minutas.api.rutas_de_imagenes import router_de_imagenes
from minutas.api.rutas_de_tiendas import router_de_tiendas
from minutas.api.salud import router_de_salud
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios


def crear_app(configuracion: Configuracion, servicios: Servicios) -> FastAPI:
    configurar_registro(configuracion.nivel_de_registro)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        yield
        await servicios.cerrar()

    app = FastAPI(title="Minutas", version=__version__, lifespan=ciclo_de_vida)
    app.state.configuracion = configuracion
    app.state.servicios = servicios
    app.state.casos_de_uso = crear_casos_de_uso(servicios)
    app.add_middleware(MiddlewareDeSolicitud)
    app.include_router(router_de_salud)
    app.include_router(router_de_tiendas)
    app.include_router(router_de_imagenes)
    registrar_manejadores_de_errores(app)
    return app


def crear_app_desde_entorno() -> FastAPI:
    """Entrada para uvicorn: `uvicorn --factory minutas.api.app:crear_app_desde_entorno`."""
    configuracion = Configuracion()
    return crear_app(configuracion, crear_servicios(configuracion))
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/api -v && uv run mypy`
Expected: PASS (4 passed en `test_imagenes.py`) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/api/rutas_de_imagenes.py src/minutas/api/app.py tests/api/test_imagenes.py
git commit -m "feat(api): servir imágenes con caché permanente" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
