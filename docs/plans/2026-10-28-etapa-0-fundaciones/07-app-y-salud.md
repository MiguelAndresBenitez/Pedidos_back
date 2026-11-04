# Tarea 7: App FastAPI, salud e id de solicitud

**Archivos:**
- Crear: `src/minutas/api/app.py`
- Crear: `src/minutas/api/salud.py`
- Crear: `src/minutas/api/middleware_de_solicitud.py`
- Crear: `tests/api/conftest.py`
- Test: `tests/api/test_salud.py`

---

## Decisiones de diseño

**¿Por qué una fábrica `crear_app(configuracion)` en lugar de un `app` global?**
- Los tests arman la app con una configuración propia, sin variables de entorno.
- `crear_app_desde_entorno()` es la única entrada que lee el entorno; uvicorn la usa con `--factory`.

**¿Por qué `/salud` fuera de `/api/v1`?**
- La usan el balanceador y Docker, no los clientes: no se versiona con la API.
- Es un chequeo de vida (liveness): no consulta la base. La disponibilidad de la base la garantiza el orden de arranque de Compose.

**¿Por qué un middleware ASGI puro y no `@app.middleware("http")`?**
- `@app.middleware("http")` usa `BaseHTTPMiddleware`, que corre la app en otra tarea: lo que se vincule al registro después (como `local_id` en la etapa 1) no vuelve al middleware. Además no es buena base para las respuestas en streaming del SSE (etapa 4).
- El middleware ASGI corre en la misma tarea y agrega la cabecera al mensaje `http.response.start`, sin envolver la respuesta.
- Los condicionales del método son el protocolo ASGI (tipo de scope y de mensaje), código de adaptador.

**¿Por qué se valida el `X-Request-ID` entrante?**
- Si un proxy ya asignó un id, el mismo valor sigue la solicitud en los logs. Pero va a cada línea de log y a la respuesta: solo se acepta hasta 64 caracteres de `[A-Za-z0-9._-]`. Cualquier otro valor se reemplaza.
- El id nuevo sale de `Identificador.generar()`: un UUIDv7, generado en el único lugar del proyecto que conoce la librería (tarea 4).

---

## Paso 1: Escribir el test que falla

`tests/api/conftest.py`:

```python
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion

URL_APP = "postgresql+asyncpg://minutas_app:clave@localhost:5432/minutas"


@pytest.fixture
def configuracion() -> Configuracion:
    return Configuracion(url_base_de_datos=URL_APP, entorno="pruebas")


@pytest.fixture
def app(configuracion: Configuracion) -> FastAPI:
    return crear_app(configuracion)


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
```

`tests/api/test_salud.py`:

```python
from uuid import UUID

import httpx
import pytest


async def test_consultar_salud_responde_ok(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


async def test_consultar_salud_genera_id_de_solicitud_uuid7(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud")

    assert UUID(respuesta.headers["X-Request-ID"]).version == 7


async def test_consultar_salud_respeta_id_de_solicitud_valido(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/salud", headers={"X-Request-ID": "pedido-123"})

    assert respuesta.headers["X-Request-ID"] == "pedido-123"


@pytest.mark.parametrize("recibido", ["x" * 65, "con espacios", "comillas'raras"])
async def test_consultar_salud_reemplaza_id_de_solicitud_invalido(
    cliente: httpx.AsyncClient, recibido: str
) -> None:
    respuesta = await cliente.get("/salud", headers={"X-Request-ID": recibido})

    assert UUID(respuesta.headers["X-Request-ID"]).version == 7
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/api/test_salud.py -v`
Expected: ERROR en la colección de `tests/api/conftest.py` con `ModuleNotFoundError: No module named 'minutas.api.app'`

## Paso 3: Implementación mínima

`src/minutas/api/salud.py`:

```python
"""Chequeo de vida para Docker y el balanceador."""

from fastapi import APIRouter

router_de_salud = APIRouter()


@router_de_salud.get("/salud")
async def consultar_salud() -> dict[str, str]:
    return {"estado": "ok"}
```

`src/minutas/api/middleware_de_solicitud.py`:

```python
"""Asigna un id a cada solicitud, lo vincula al registro y lo devuelve en la respuesta."""

import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from minutas.compartido.dominio.identificador import Identificador
from minutas.compartido.infraestructura.registro import limpiar_contexto, vincular_contexto

CABECERA_ID_DE_SOLICITUD = "X-Request-ID"
PATRON_ID_DE_SOLICITUD = re.compile(r"[A-Za-z0-9._-]{1,64}")


def obtener_id_de_solicitud(cabeceras: Headers) -> str:
    recibido = cabeceras.get(CABECERA_ID_DE_SOLICITUD, "")
    if PATRON_ID_DE_SOLICITUD.fullmatch(recibido):
        return recibido
    return str(Identificador.generar())


class MiddlewareDeSolicitud:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        id_de_solicitud = obtener_id_de_solicitud(Headers(scope=scope))
        limpiar_contexto()
        vincular_contexto(request_id=id_de_solicitud)

        async def enviar_con_id(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                MutableHeaders(scope=mensaje).append(CABECERA_ID_DE_SOLICITUD, id_de_solicitud)
            await send(mensaje)

        await self._app(scope, receive, enviar_con_id)
```

`src/minutas/api/app.py`:

```python
"""Fábrica de la aplicación FastAPI: raíz de composición HTTP."""

from fastapi import FastAPI

from minutas import __version__
from minutas.api.middleware_de_solicitud import MiddlewareDeSolicitud
from minutas.api.salud import router_de_salud
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro


def crear_app(configuracion: Configuracion) -> FastAPI:
    configurar_registro(configuracion.nivel_de_registro)
    app = FastAPI(title="Minutas", version=__version__)
    app.add_middleware(MiddlewareDeSolicitud)
    app.include_router(router_de_salud)
    return app


def crear_app_desde_entorno() -> FastAPI:
    """Entrada para uvicorn: `uvicorn --factory minutas.api.app:crear_app_desde_entorno`."""
    return crear_app(Configuracion())
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/api/test_salud.py -v`
Expected: PASS (6 passed)

## Paso 5: Commit

```bash
git add src/minutas/api tests/api
git commit -m "feat(api): fábrica de la app, chequeo de salud e id de solicitud" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
