# Tarea 11: Sentencias de Row Level Security

**Archivos:**
- Crear: `src/minutas/compartido/infraestructura/rls.py`
- Test: `tests/unitarios/compartido/test_rls.py`

---

## Decisiones de diseño

**¿Por qué generar las sentencias en una función en lugar de escribirlas a mano en cada migración?**
- Toda tabla del local lleva exactamente la misma política (spec, sección Multi-tenancy). Un copiar y pegar mal hecho deja una tabla sin aislar.
- Las migraciones de las etapas siguientes hacen `for sentencia in sentencias_de_aislamiento("productos"): op.execute(sentencia)`.

**¿Por qué `FORCE ROW LEVEL SECURITY`?**
- Sin `FORCE`, el dueño de la tabla (`minutas_owner`) no está sujeto a la política. Con `FORCE` nadie salvo un superusuario la saltea.

**¿Por qué validar el nombre de la tabla?**
- Se interpola en SQL: solo se aceptan nombres `snake_case` en minúsculas, que además es la convención de tablas.
- Es validación de un valor, un condicional permitido por `docs/plans/00-conventions.md`.

**¿Por qué `FORCE` y qué cuesta?**
- Una migración de datos (backfill) corre como `minutas_owner` y también queda sujeta a la política: sin tenant fijado falla. Regla para las etapas siguientes: una migración de datos recorre los locales y hace `set_config('app.local_id', <id>, true)` antes de tocar las filas de cada uno. Nunca desactiva RLS.

**¿Por qué `current_setting('app.local_id')` sin `missing_ok`?**
- Si el tenant no está fijado, la consulta falla en lugar de devolver filas: falla cerrado.
- El mensaje depende de la conexión. En una conexión que nunca fijó el tenant: `unrecognized configuration parameter "app.local_id"`. En una conexión del pool que ya lo fijó en una transacción anterior, la variable existe vacía: `invalid input syntax for type uuid: ""`. Las dos fallan cerrado; la tarea 13 prueba las dos.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_rls.py`:

```python
import pytest

from minutas.compartido.infraestructura.rls import (
    NombreDeTablaInvalido,
    sentencias_de_aislamiento,
    sentencias_para_quitar_aislamiento,
)

CONDICION = "local_id = current_setting('app.local_id')::uuid"


def test_sentencias_de_aislamiento_activan_fuerzan_y_crean_la_politica() -> None:
    assert sentencias_de_aislamiento("productos") == [
        "ALTER TABLE productos ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE productos FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY aislamiento_local ON productos USING ({CONDICION}) "
        f"WITH CHECK ({CONDICION})",
    ]


def test_sentencias_para_quitar_aislamiento_revierten_en_orden_inverso() -> None:
    assert sentencias_para_quitar_aislamiento("productos") == [
        "DROP POLICY aislamiento_local ON productos",
        "ALTER TABLE productos NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE productos DISABLE ROW LEVEL SECURITY",
    ]


@pytest.mark.parametrize("tabla", ["", "Productos", "productos; DROP TABLE x", "1productos"])
def test_sentencias_de_aislamiento_con_nombre_invalido_falla(tabla: str) -> None:
    with pytest.raises(NombreDeTablaInvalido, match="no es un nombre de tabla válido"):
        sentencias_de_aislamiento(tabla)
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_rls.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.infraestructura.rls'`

## Paso 3: Implementación mínima

`src/minutas/compartido/infraestructura/rls.py`:

```python
"""Sentencias SQL que aíslan una tabla del local con Row Level Security."""

import re

PATRON_DE_TABLA = re.compile(r"[a-z_][a-z0-9_]*")
NOMBRE_DE_POLITICA = "aislamiento_local"
CONDICION = "local_id = current_setting('app.local_id')::uuid"


class NombreDeTablaInvalido(ValueError):
    pass


def asegurar_nombre_de_tabla_valido(tabla: str) -> None:
    if not PATRON_DE_TABLA.fullmatch(tabla):
        raise NombreDeTablaInvalido(f"'{tabla}' no es un nombre de tabla válido")


def sentencias_de_aislamiento(tabla: str) -> list[str]:
    asegurar_nombre_de_tabla_valido(tabla)
    return [
        f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {NOMBRE_DE_POLITICA} ON {tabla} USING ({CONDICION}) "
        f"WITH CHECK ({CONDICION})",
    ]


def sentencias_para_quitar_aislamiento(tabla: str) -> list[str]:
    asegurar_nombre_de_tabla_valido(tabla)
    return [
        f"DROP POLICY {NOMBRE_DE_POLITICA} ON {tabla}",
        f"ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY",
    ]
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/compartido/test_rls.py -v`
Expected: PASS (6 passed)

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/rls.py tests/unitarios/compartido/test_rls.py
git commit -m "feat(compartido): sentencias de Row Level Security por local" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
