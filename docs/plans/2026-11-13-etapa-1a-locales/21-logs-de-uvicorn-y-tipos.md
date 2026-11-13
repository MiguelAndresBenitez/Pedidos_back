# Tarea 21: Logs de uvicorn en JSON y tipos sin ignore

**Archivos:**
- Modificar: `src/minutas/compartido/infraestructura/registro.py`
- Modificar: `tests/integracion/test_aislamiento_entre_locales.py`
- Test: `tests/unitarios/compartido/test_registro.py`

---

## Decisiones de diseño

**¿Cómo salen en JSON los logs de uvicorn?**
- Uvicorn usa la librería estándar. `configurar_registro` les pone un `ProcessorFormatter` de structlog con la misma cadena (contexto, nivel, fecha) y corta la propagación para no duplicar líneas. Uvicorn configura sus loggers antes de llamar a la fábrica de la app, así que queda la configuración de la app. Es un pendiente de la etapa 0.

**`cast` a `CursorResult`** reemplaza los dos `# type: ignore[attr-defined]` de `rowcount` en el test de aislamiento (pendiente de la etapa 0).

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_registro.py` (cambios):

```diff
@@ -1,3 +1,4 @@
 import json
+import logging
 from collections.abc import Iterator
 
@@ -67,2 +68,25 @@ def test_obtener_contexto_devuelve_los_valores_vinculados() -> None:
 
     assert obtener_contexto() == {"request_id": "abc"}
+
+
+def test_registro_de_uvicorn_sale_en_json_con_el_contexto(
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    configurar_registro("INFO")
+    vincular_contexto(request_id="abc")
+
+    logging.getLogger("uvicorn.error").warning("Puerto %s ocupado", 8000)
+
+    [linea] = leer_lineas(capsys)
+    assert linea["event"] == "Puerto 8000 ocupado"
+    assert linea["level"] == "warning"
+    assert linea["request_id"] == "abc"
+    assert "timestamp" in linea
+
+
+def test_registro_de_uvicorn_respeta_el_nivel(capsys: pytest.CaptureFixture[str]) -> None:
+    configurar_registro("WARNING")
+
+    logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /salud HTTP/1.1" 200')
+
+    assert leer_lineas(capsys) == []
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_registro.py -v`
Expected: FAIL: `ValueError: not enough values to unpack (expected 1, got 0)`: la línea de uvicorn no sale como JSON por stdout

## Paso 3: Implementación

`src/minutas/compartido/infraestructura/registro.py`:

```python
"""Registro estructurado en JSON, con contexto por request."""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor

from minutas.compartido.infraestructura.configuracion import NivelDeRegistro

REGISTROS_DE_UVICORN = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configurar_registro(nivel: NivelDeRegistro) -> None:
    """Emite una línea JSON por evento en stdout, filtrando por nivel.

    Los registros de uvicorn (librería estándar) salen con el mismo formato y contexto.
    """
    previos: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[
            *previos,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[nivel]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=previos,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    for nombre in REGISTROS_DE_UVICORN:
        registro = logging.getLogger(nombre)
        registro.handlers = [manejador]
        registro.propagate = False
        registro.setLevel(nivel)


def vincular_contexto(**valores: str) -> None:
    """Agrega valores que aparecen en todas las líneas del request actual."""
    structlog.contextvars.bind_contextvars(**valores)


def limpiar_contexto() -> None:
    structlog.contextvars.clear_contextvars()


def obtener_contexto() -> dict[str, Any]:
    """Valores vinculados al request actual, por ejemplo para incluir request_id en un error."""
    return structlog.contextvars.get_contextvars()
```

`tests/integracion/test_aislamiento_entre_locales.py` (cambios):

```diff
@@ -1,7 +1,8 @@
 from collections.abc import AsyncIterator
+from typing import Any, cast
 
 import asyncpg
 import pytest
-from sqlalchemy import text
+from sqlalchemy import CursorResult, text
 from sqlalchemy.exc import DBAPIError
 from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
@@ -99,5 +100,5 @@ async def test_actualizar_notas_de_otro_local_no_afecta_filas(
     async with UnidadDeTrabajoSQLAlchemy(fabrica, local_a) as unidad:
         resultado = await unidad.sesion.execute(ACTUALIZAR_TEXTO, {"texto": "pisada"})
-        assert resultado.rowcount == 0  # type: ignore[attr-defined]
+        assert cast(CursorResult[Any], resultado).rowcount == 0
 
     async with UnidadDeTrabajoSQLAlchemy(fabrica, local_b) as unidad:
@@ -114,5 +115,5 @@ async def test_borrar_notas_de_otro_local_no_afecta_filas(
     async with UnidadDeTrabajoSQLAlchemy(fabrica, local_a) as unidad:
         resultado = await unidad.sesion.execute(BORRAR_NOTAS)
-        assert resultado.rowcount == 0  # type: ignore[attr-defined]
+        assert cast(CursorResult[Any], resultado).rowcount == 0
 
     assert await contar_notas(fabrica, local_b) == 1
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy && ! grep -rn 'type: ignore' src tests`
Expected: PASS (6 passed en `test_registro.py`), `Success: no issues found` y ningún `type: ignore`

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/registro.py tests/unitarios/compartido/test_registro.py tests/integracion/test_aislamiento_entre_locales.py
git commit -m "feat(compartido): logs de uvicorn en json y tipos sin ignore" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
