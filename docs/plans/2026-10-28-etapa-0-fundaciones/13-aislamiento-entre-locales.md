# Tarea 13: Prueba de aislamiento entre locales

**Archivos:**
- Test: `tests/integracion/test_aislamiento_entre_locales.py`

Esta tarea no agrega código de producción: prueba de punta a punta que las tareas 9, 11 y 12 juntas aíslan a cada local.

---

## Decisiones de diseño

**¿Por qué una tabla de ejemplo creada por el test y no por una migración?**
- La spec pide probar el aislamiento "con una tabla de ejemplo" en la etapa 0. Si se creara por migración, quedaría para siempre en el esquema de producción.
- El fixture la crea como `minutas_owner` con las mismas `sentencias_de_aislamiento` que usarán las migraciones reales, y la borra al final.

**¿Por qué estos cinco casos?**
- Son las garantías de la spec: un local no lee filas de otro, no escribe filas a nombre de otro, una consulta sin tenant falla, y SQL crudo con el tenant de A no ve filas de B.
- "Sin tenant" se prueba dos veces porque falla con mensajes distintos (ver tarea 11): en una conexión nueva, y en la misma conexión después de `confirmar()`, que es el caso real del pool.
- La prueba "por repositorio" llega en la etapa 1, con los primeros repositorios.

**¿Por qué `DBAPIError` en lugar de una excepción de asyncpg?**
- SQLAlchemy envuelve los errores del driver: el test depende de SQLAlchemy, no de asyncpg. El `match` asegura que la causa es la esperada.

---

## Paso 1: Escribir el test

`tests/integracion/test_aislamiento_entre_locales.py`:

```python
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.identificador import Identificador
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from minutas.compartido.infraestructura.rls import sentencias_de_aislamiento
from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
    UnidadDeTrabajoSQLAlchemy,
)
from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion

INSERTAR_NOTA = text(
    "INSERT INTO notas_de_prueba (id, local_id, texto) VALUES (:id, :local_id, :texto)"
)
CONTAR_NOTAS = text("SELECT count(*) FROM notas_de_prueba")


@pytest.fixture
async def fabrica(
    base_de_prueba: BaseDePrueba,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    owner = await asyncpg.connect(base_de_prueba.dsn_owner())
    motor = crear_motor(base_de_prueba.url_app())
    try:
        await owner.execute(
            "CREATE TABLE notas_de_prueba ("
            "id uuid PRIMARY KEY, local_id uuid NOT NULL, texto text NOT NULL)"
        )
        for sentencia in sentencias_de_aislamiento("notas_de_prueba"):
            await owner.execute(sentencia)
        yield crear_fabrica_de_sesiones(motor)
    finally:
        await motor.dispose()
        await owner.execute("DROP TABLE IF EXISTS notas_de_prueba")
        await owner.close()


async def insertar_nota(
    fabrica: async_sessionmaker[AsyncSession], local_id: LocalId, texto: str
) -> None:
    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_id) as unidad:
        await unidad.sesion.execute(
            INSERTAR_NOTA,
            {"id": Identificador.generar().valor, "local_id": local_id.valor, "texto": texto},
        )
        await unidad.confirmar()


async def contar_notas(fabrica: async_sessionmaker[AsyncSession], local_id: LocalId) -> int:
    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_id) as unidad:
        cantidad = await unidad.sesion.scalar(CONTAR_NOTAS)
    return int(cantidad or 0)


async def test_contar_notas_de_otro_local_devuelve_cero(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_a, local_b = LocalId.generar(), LocalId.generar()
    await insertar_nota(fabrica, local_a, "nota de A")

    assert await contar_notas(fabrica, local_a) == 1
    assert await contar_notas(fabrica, local_b) == 0


async def test_insertar_nota_a_nombre_de_otro_local_falla(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_a, local_b = LocalId.generar(), LocalId.generar()

    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_a) as unidad:
        with pytest.raises(DBAPIError, match="row-level security"):
            await unidad.sesion.execute(
                INSERTAR_NOTA,
                {"id": Identificador.generar().valor, "local_id": local_b.valor, "texto": "x"},
            )


async def test_consultar_sin_local_fijado_falla(
    fabrica: async_sessionmaker[AsyncSession], base_de_prueba: BaseDePrueba
) -> None:
    motor_nuevo = crear_motor(base_de_prueba.url_app())
    try:
        async with crear_fabrica_de_sesiones(motor_nuevo)() as sesion:
            with pytest.raises(DBAPIError, match=r"app\.local_id"):
                await sesion.execute(CONTAR_NOTAS)
    finally:
        await motor_nuevo.dispose()


async def test_consultar_despues_de_confirmar_falla_en_la_misma_conexion(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with UnidadDeTrabajoSQLAlchemy(fabrica, LocalId.generar()) as unidad:
        await unidad.confirmar()
        with pytest.raises(DBAPIError, match="invalid input syntax for type uuid"):
            await unidad.sesion.execute(CONTAR_NOTAS)


async def test_consultar_con_sql_crudo_solo_ve_filas_del_local_fijado(
    fabrica: async_sessionmaker[AsyncSession], base_de_prueba: BaseDePrueba
) -> None:
    local_a, local_b = LocalId.generar(), LocalId.generar()
    await insertar_nota(fabrica, local_a, "nota de A")
    await insertar_nota(fabrica, local_b, "nota de B")

    conexion = await asyncpg.connect(base_de_prueba.dsn_app())
    try:
        await conexion.execute("SELECT set_config('app.local_id', $1, false)", str(local_a))
        filas = await conexion.fetch("SELECT texto FROM notas_de_prueba")
        textos = [fila["texto"] for fila in filas]
    finally:
        await conexion.close()

    assert textos == ["nota de A"]
```

## Paso 2: Correr el test

Run: `uv run pytest tests/integracion/test_aislamiento_entre_locales.py -v`
Expected: PASS (5 passed). Las piezas ya existen; si algún caso falla, el aislamiento tiene un agujero y se corrige antes de seguir.

## Paso 3: Comprobar que el test detecta un agujero

Como el test se escribe después de las piezas, hay que verlo fallar a propósito: en el fixture, cambiar temporalmente `sentencias_de_aislamiento("notas_de_prueba")` por `[]` (tabla sin RLS).

Run: `uv run pytest tests/integracion/test_aislamiento_entre_locales.py -v`
Expected: FAIL en los 5 casos (por ejemplo `assert 1 == 0` en `test_contar_notas_de_otro_local_devuelve_cero`)

Revertir el cambio y volver a correr: PASS (5 passed).

## Paso 4: Verificar todo junto

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -v`
Expected: sin errores y todos los tests en PASS

## Paso 5: Commit

```bash
git add tests/integracion/test_aislamiento_entre_locales.py
git commit -m "test(compartido): aislamiento entre locales con RLS y unidad de trabajo" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
