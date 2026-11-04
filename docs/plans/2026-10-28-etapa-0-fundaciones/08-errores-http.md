# Tarea 8: Errores HTTP en `problem+json`

**Archivos:**
- Crear: `src/minutas/api/errores_http.py`
- Modificar: `src/minutas/api/app.py` (función `crear_app`)
- Test: `tests/api/test_errores_http.py`

---

## Decisiones de diseño

**¿Por qué una tabla `ESTADOS_POR_CATEGORIA` recorrida por el MRO en lugar de `if isinstance`?**
- Un error concreto (`TiendaCerrada`) no figura en la tabla: se busca su primera clase ancestro que sí figure.
- Sumar una categoría es agregar una entrada, sin tocar la lógica. Patrón "Tabla de despacho" de `docs/plans/00-conventions.md`.
- `ErrorDeDominio` está en la tabla (400), así que la búsqueda siempre encuentra un estado.

**¿Por qué RFC 9457 con los campos extra `code` y `request_id`?**
- La spec lo pide: el front reacciona al `code` del dominio, no al texto.
- Con el `request_id` en el cuerpo, quien recibe el error puede citarlo y se encuentra en los logs.

**¿Por qué también se traducen las `HTTPException` de Starlette?**
- Una ruta inexistente (404) o un método no permitido (405) responden `{"detail": ...}` por defecto. Todo error de la API sale en un solo formato.
- `CODIGOS_POR_ESTADO_HTTP` da el `code`; un estado que no figura cae en `error_http`.

**¿Por qué el 500 agrega su propia cabecera `X-Request-ID` y no incluye el mensaje de la excepción?**
- El manejador de `Exception` lo ejecuta `ServerErrorMiddleware`, que está por fuera de `MiddlewareDeSolicitud`: la respuesta no pasa por el middleware. El id se toma de `obtener_contexto()`, que sigue vinculado porque el middleware ASGI corre en la misma tarea.
- El mensaje puede filtrar detalles internos. Se registra completo en el log con su `request_id`.

**¿Por qué `cast` en los manejadores?**
- Starlette tipa los manejadores con `Exception`; el registro por clase garantiza que llega la subclase esperada.

---

## Paso 1: Escribir el test que falla

`tests/api/test_errores_http.py`:

```python
import httpx
import pytest
from fastapi import FastAPI

from minutas.api.app import crear_app
from minutas.compartido.dominio.errores import (
    Conflicto,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)
from minutas.compartido.infraestructura.configuracion import Configuracion


class TiendaCerrada(ReglaDeNegocioIncumplida):
    codigo = "tienda_cerrada"


@pytest.fixture
def app(configuracion: Configuracion) -> FastAPI:
    app = crear_app(configuracion)
    errores: dict[str, Exception] = {
        "tienda-cerrada": TiendaCerrada("La tienda está cerrada"),
        "no-encontrado": NoEncontrado("No existe"),
        "conflicto": Conflicto("Choca con otro dato"),
        "limite": LimiteExcedido("Demasiados pedidos"),
        "inesperado": RuntimeError("secreto interno"),
    }

    @app.get("/prueba/{caso}")
    async def lanzar(caso: str) -> None:
        raise errores[caso]

    @app.get("/prueba-validacion")
    async def validar(cantidad: int) -> dict[str, int]:
        return {"cantidad": cantidad}

    return app


@pytest.mark.parametrize(
    ("caso", "estado", "codigo", "detalle"),
    [
        ("tienda-cerrada", 422, "tienda_cerrada", "La tienda está cerrada"),
        ("no-encontrado", 404, "no_encontrado", "No existe"),
        ("conflicto", 409, "conflicto", "Choca con otro dato"),
        ("limite", 429, "limite_excedido", "Demasiados pedidos"),
    ],
)
async def test_lanzar_error_de_dominio_responde_problem_json(
    cliente: httpx.AsyncClient, caso: str, estado: int, codigo: str, detalle: str
) -> None:
    respuesta = await cliente.get(f"/prueba/{caso}", headers={"X-Request-ID": "sol-1"})

    assert respuesta.status_code == estado
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo.pop("title")
    assert cuerpo == {
        "type": "about:blank",
        "status": estado,
        "detail": detalle,
        "code": codigo,
        "request_id": "sol-1",
    }


async def test_lanzar_error_inesperado_responde_500_con_id_y_sin_detalles(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/prueba/inesperado", headers={"X-Request-ID": "sol-2"})

    assert respuesta.status_code == 500
    assert respuesta.headers["X-Request-ID"] == "sol-2"
    assert respuesta.json()["code"] == "error_interno"
    assert respuesta.json()["request_id"] == "sol-2"
    assert "secreto" not in respuesta.text


async def test_enviar_parametro_invalido_responde_solicitud_invalida(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/prueba-validacion", params={"cantidad": "muchas"})

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "solicitud_invalida"
    assert cuerpo["errores"][0]["loc"] == ["query", "cantidad"]


@pytest.mark.parametrize(
    ("metodo", "ruta", "estado", "codigo"),
    [
        ("GET", "/no-existe", 404, "ruta_inexistente"),
        ("POST", "/salud", 405, "metodo_no_permitido"),
    ],
)
async def test_pedir_ruta_o_metodo_inexistente_responde_problem_json(
    cliente: httpx.AsyncClient, metodo: str, ruta: str, estado: int, codigo: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)

    assert respuesta.status_code == estado
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["code"] == codigo
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/api/test_errores_http.py -v`
Expected: FAIL; los casos de dominio responden `500` en lugar del estado esperado, y los demás responden `content-type` `application/json`

## Paso 3: Implementación mínima

`src/minutas/api/errores_http.py`:

```python
"""Traducción de errores a respuestas application/problem+json (RFC 9457)."""

from http import HTTPStatus
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from minutas.api.middleware_de_solicitud import CABECERA_ID_DE_SOLICITUD
from minutas.compartido.dominio.errores import (
    Conflicto,
    ErrorDeDominio,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)
from minutas.compartido.infraestructura.registro import obtener_contexto

TIPO_DE_MEDIO = "application/problem+json"

ESTADOS_POR_CATEGORIA: dict[type[ErrorDeDominio], HTTPStatus] = {
    NoEncontrado: HTTPStatus.NOT_FOUND,
    Conflicto: HTTPStatus.CONFLICT,
    ReglaDeNegocioIncumplida: HTTPStatus.UNPROCESSABLE_ENTITY,
    LimiteExcedido: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorDeDominio: HTTPStatus.BAD_REQUEST,
}

CODIGOS_POR_ESTADO_HTTP: dict[int, str] = {
    HTTPStatus.NOT_FOUND: "ruta_inexistente",
    HTTPStatus.METHOD_NOT_ALLOWED: "metodo_no_permitido",
}


def obtener_estado_por_error(error: ErrorDeDominio) -> HTTPStatus:
    return next(
        ESTADOS_POR_CATEGORIA[clase]
        for clase in type(error).__mro__
        if clase in ESTADOS_POR_CATEGORIA
    )


def crear_problema(estado: HTTPStatus, codigo: str, detalle: str, **extras: Any) -> JSONResponse:
    contenido = {
        "type": "about:blank",
        "title": estado.phrase,
        "status": int(estado),
        "detail": detalle,
        "code": codigo,
        "request_id": obtener_contexto().get("request_id"),
        **extras,
    }
    return JSONResponse(status_code=estado, content=contenido, media_type=TIPO_DE_MEDIO)


async def manejar_error_de_dominio(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(ErrorDeDominio, excepcion)
    return crear_problema(obtener_estado_por_error(error), error.codigo, error.mensaje)


async def manejar_error_http(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(HTTPException, excepcion)
    codigo = CODIGOS_POR_ESTADO_HTTP.get(error.status_code, "error_http")
    return crear_problema(HTTPStatus(error.status_code), codigo, str(error.detail))


async def manejar_solicitud_invalida(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(RequestValidationError, excepcion)
    return crear_problema(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "solicitud_invalida",
        "La solicitud tiene datos inválidos",
        errores=jsonable_encoder(error.errors()),
    )


async def manejar_error_inesperado(_: Request, excepcion: Exception) -> JSONResponse:
    structlog.get_logger().error("error_no_controlado", exc_info=excepcion)
    respuesta = crear_problema(
        HTTPStatus.INTERNAL_SERVER_ERROR, "error_interno", "Ocurrió un error inesperado"
    )
    respuesta.headers[CABECERA_ID_DE_SOLICITUD] = str(obtener_contexto().get("request_id", ""))
    return respuesta


def registrar_manejadores_de_errores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDeDominio, manejar_error_de_dominio)
    app.add_exception_handler(HTTPException, manejar_error_http)
    app.add_exception_handler(RequestValidationError, manejar_solicitud_invalida)
    app.add_exception_handler(Exception, manejar_error_inesperado)
```

En `src/minutas/api/app.py`, agregar el import y la llamada dentro de `crear_app`, después de `app.include_router(router_de_salud)`:

```python
from minutas.api.errores_http import registrar_manejadores_de_errores
```

```python
    registrar_manejadores_de_errores(app)
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/api -v`
Expected: PASS (todos: los de errores y los de salud)

## Paso 5: Commit

```bash
git add src/minutas/api/errores_http.py src/minutas/api/app.py tests/api/test_errores_http.py
git commit -m "feat(api): errores en application/problem+json con código del dominio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
