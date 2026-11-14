# Tarea 6: Registro estructurado

**Archivos:**
- Crear: `src/minutas/compartido/infraestructura/registro.py`
- Test: `tests/unitarios/compartido/test_registro.py`

---

## Decisiones de diseño

**¿Por qué structlog con salida JSON?**
- La spec pide logs en JSON con `request_id` y `local_id` en cada línea.
- Las variables de contexto (`contextvars`) son seguras con async: cada request ve solo su contexto.

**¿Por qué envolver structlog en `vincular_contexto` y `limpiar_contexto`?**
- El middleware (tarea 7) y la resolución del tenant (etapa 1) usan estas funciones sin conocer structlog.
- Si se cambia la librería de logs, cambia un solo archivo.

**¿Por qué `obtener_contexto`?**
- El manejador del 500 (tarea 8) corre por fuera del middleware y necesita el `request_id` para devolverlo al cliente.

**¿Por qué las claves `event`, `level` y `request_id` quedan en inglés?**
- `event` y `level` las pone structlog; `request_id` es el nombre estándar que buscan las herramientas de logs. Ver `docs/plans/00-conventions.md`, sección Idioma.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_registro.py`:

```python
import json
from collections.abc import Iterator

import pytest
import structlog

from minutas.compartido.infraestructura.registro import (
    configurar_registro,
    limpiar_contexto,
    obtener_contexto,
    vincular_contexto,
)


@pytest.fixture(autouse=True)
def contexto_limpio() -> Iterator[None]:
    limpiar_contexto()
    yield
    limpiar_contexto()
    structlog.reset_defaults()


def leer_lineas(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines()]


def test_registrar_emite_json_con_el_contexto_vinculado(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configurar_registro("INFO")
    vincular_contexto(request_id="abc", local_id="123")

    structlog.get_logger().info("pedido_recibido", numero=42)

    [linea] = leer_lineas(capsys)
    assert linea["event"] == "pedido_recibido"
    assert linea["level"] == "info"
    assert linea["request_id"] == "abc"
    assert linea["local_id"] == "123"
    assert linea["numero"] == 42
    assert "timestamp" in linea


def test_registrar_por_debajo_del_nivel_no_emite_nada(capsys: pytest.CaptureFixture[str]) -> None:
    configurar_registro("WARNING")

    structlog.get_logger().info("detalle_sin_importancia")

    assert leer_lineas(capsys) == []


def test_limpiar_contexto_quita_los_valores_vinculados(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configurar_registro("INFO")
    vincular_contexto(request_id="abc")
    limpiar_contexto()

    structlog.get_logger().info("sin_contexto")

    [linea] = leer_lineas(capsys)
    assert "request_id" not in linea


def test_obtener_contexto_devuelve_los_valores_vinculados() -> None:
    vincular_contexto(request_id="abc")

    assert obtener_contexto() == {"request_id": "abc"}
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_registro.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.infraestructura.registro'`

## Paso 3: Implementación mínima

`src/minutas/compartido/infraestructura/registro.py`:

```python
"""Registro estructurado en JSON, con contexto por request."""

import logging
from typing import Any

import structlog

from minutas.compartido.infraestructura.configuracion import NivelDeRegistro


def configurar_registro(nivel: NivelDeRegistro) -> None:
    """Emite una línea JSON por evento en stdout, filtrando por nivel."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[nivel]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def vincular_contexto(**valores: str) -> None:
    """Agrega valores que aparecen en todas las líneas del request actual."""
    structlog.contextvars.bind_contextvars(**valores)


def limpiar_contexto() -> None:
    structlog.contextvars.clear_contextvars()


def obtener_contexto() -> dict[str, Any]:
    """Valores vinculados al request actual, por ejemplo para incluir request_id en un error."""
    return structlog.contextvars.get_contextvars()
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/compartido/test_registro.py -v`
Expected: PASS (4 passed)

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/registro.py tests/unitarios/compartido/test_registro.py
git commit -m "feat(compartido): registro estructurado en JSON con contexto por request" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
