# Tarea 12: Unidad de trabajo con tenant

**Archivos:**
- Crear: `src/minutas/compartido/aplicacion/unidad_de_trabajo.py`
- Crear: `src/minutas/compartido/infraestructura/base_de_datos.py`
- Crear: `src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py`
- Test: `tests/integracion/test_unidad_de_trabajo.py`

---

## Decisiones de diseño

**¿Por qué la unidad de trabajo fija el tenant al entrar?**
- La spec define que la unidad de trabajo abre la transacción y fija `app.local_id`. Así ningún caso de uso puede olvidarse de hacerlo.

**¿Cómo llegan los repositorios a la sesión (punto de extensión para la etapa 1)?**
- El puerto `UnidadDeTrabajo` es la base común: `local_id`, contexto async y `confirmar()`. No expone la sesión, porque la capa de aplicación no conoce SQLAlchemy.
- Cada contexto define su propio puerto que extiende la base con sus repositorios, por ejemplo `class UnidadDeTrabajoDeCarta(UnidadDeTrabajo, Protocol)` con `productos: RepositorioDeProductos`. Su adaptador hereda de `UnidadDeTrabajoSQLAlchemy` y arma los repositorios con `self.sesion` y `self.local_id`.
- El test asigna el adaptador a una variable tipada con el puerto: si el adaptador se desvía del contrato, mypy falla.

**¿Por qué `set_config('app.local_id', :local_id, true)` y no `SET LOCAL`?**
- `SET LOCAL` no acepta parámetros: habría que interpolar el valor en el SQL. `set_config` sí los acepta y, con el tercer argumento en `true`, también vale solo para la transacción actual.

**¿Por qué `__aexit__` siempre hace rollback, sin preguntar si hubo error?**
- Después de `confirmar()` el rollback no tiene efecto; sin confirmar, descarta todo. Un solo camino, sin condicionales.
- Cada unidad de trabajo es de un solo uso y una sola transacción: después de `confirmar()` el tenant deja de valer y una consulta posterior falla cerrado (lo prueba la tarea 13).

**¿Por qué `__aenter__` cierra la sesión si falla?**
- Si `__aenter__` lanza, Python no llama a `__aexit__`: sin el cierre, la conexión queda tomada del pool con una transacción abierta.

**¿Por qué la sesión se crea en `__init__`?**
- Crear una `AsyncSession` no abre conexión; la conexión se toma en la primera consulta. Evita un atributo opcional y sus chequeos.

---

## Paso 1: Escribir el test que falla

`tests/integracion/test_unidad_de_trabajo.py`:

```python
from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import QueuePool, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from minutas.compartido.aplicacion.unidad_de_trabajo import UnidadDeTrabajo
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura import unidad_de_trabajo_sqlalchemy
from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
    UnidadDeTrabajoSQLAlchemy,
)
from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion


@pytest.fixture
async def motor(base_de_prueba: BaseDePrueba) -> AsyncIterator[AsyncEngine]:
    motor = crear_motor(base_de_prueba.url_app())
    yield motor
    await motor.dispose()


@pytest.fixture
def fabrica(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return crear_fabrica_de_sesiones(motor)


async def test_entrar_fija_el_local_en_la_transaccion(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_id = LocalId.generar()

    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_id) as unidad:
        valor = await unidad.sesion.scalar(text("SELECT current_setting('app.local_id')"))

    assert valor == str(local_id)


async def test_confirmar_termina_la_transaccion_y_el_local_deja_de_valer(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with UnidadDeTrabajoSQLAlchemy(fabrica, LocalId.generar()) as unidad:
        await unidad.confirmar()
        valor = await unidad.sesion.scalar(text("SELECT current_setting('app.local_id', true)"))

    assert not valor


async def test_entrar_con_error_devuelve_la_conexion_al_pool(
    motor: AsyncEngine,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentencia_que_falla = text("SELECT set_config('app.local_id', :local_id, true)::int")
    monkeypatch.setattr(unidad_de_trabajo_sqlalchemy, "FIJAR_LOCAL", sentencia_que_falla)

    with pytest.raises(DBAPIError, match="invalid input syntax for type integer"):
        async with UnidadDeTrabajoSQLAlchemy(fabrica, LocalId.generar()):
            pass

    assert cast(QueuePool, motor.pool).checkedout() == 0


async def test_asignar_adaptador_al_puerto_conserva_el_local(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_id = LocalId.generar()

    unidad: UnidadDeTrabajo = UnidadDeTrabajoSQLAlchemy(fabrica, local_id)

    assert unidad.local_id == local_id
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/integracion/test_unidad_de_trabajo.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.aplicacion.unidad_de_trabajo'`

## Paso 3: Implementación mínima

`src/minutas/compartido/aplicacion/unidad_de_trabajo.py`:

```python
"""Puerto de unidad de trabajo: una transacción atada a un local."""

from types import TracebackType
from typing import Protocol, Self

from minutas.compartido.dominio.local_id import LocalId


class UnidadDeTrabajo(Protocol):
    """Base de las unidades de trabajo de cada contexto, que suman sus repositorios."""

    @property
    def local_id(self) -> LocalId: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    async def confirmar(self) -> None: ...
```

`src/minutas/compartido/infraestructura/base_de_datos.py`:

```python
"""Motor y fábrica de sesiones de SQLAlchemy sobre asyncpg."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def crear_motor(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def crear_fabrica_de_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, expire_on_commit=False)
```

`src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py`:

```python
"""Unidad de trabajo sobre SQLAlchemy que fija el tenant para RLS. Es de un solo uso."""

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId

FIJAR_LOCAL = text("SELECT set_config('app.local_id', :local_id, true)")


class UnidadDeTrabajoSQLAlchemy:
    def __init__(
        self, fabrica_de_sesiones: async_sessionmaker[AsyncSession], local_id: LocalId
    ) -> None:
        self._local_id = local_id
        self._sesion = fabrica_de_sesiones()

    @property
    def local_id(self) -> LocalId:
        return self._local_id

    @property
    def sesion(self) -> AsyncSession:
        return self._sesion

    async def __aenter__(self) -> Self:
        try:
            await self._sesion.execute(FIJAR_LOCAL, {"local_id": str(self._local_id)})
        except BaseException:
            await self._sesion.close()
            raise
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        await self._sesion.rollback()
        await self._sesion.close()

    async def confirmar(self) -> None:
        await self._sesion.commit()
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/integracion/test_unidad_de_trabajo.py -v && uv run mypy`
Expected: PASS (4 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/compartido/aplicacion/unidad_de_trabajo.py src/minutas/compartido/infraestructura/base_de_datos.py src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py tests/integracion/test_unidad_de_trabajo.py
git commit -m "feat(compartido): unidad de trabajo que fija el local por transacción" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
