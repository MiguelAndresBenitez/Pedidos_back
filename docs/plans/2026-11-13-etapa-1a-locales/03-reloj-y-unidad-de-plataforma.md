# Tarea 3: Reloj y unidad de trabajo de plataforma

**Archivos:**
- Crear: `src/minutas/compartido/aplicacion/reloj.py`
- Crear: `src/minutas/compartido/infraestructura/reloj_del_sistema.py`
- Crear: `tests/soporte/reloj_fijo.py`
- Modificar: `src/minutas/compartido/aplicacion/unidad_de_trabajo.py`
- Modificar: `src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py`
- Test: `tests/unitarios/compartido/test_reloj.py`
- Test: `tests/integracion/test_unidad_de_trabajo.py`

---

## Decisiones de diseño

**¿Por qué un puerto `Reloj`?**
- Jornadas, cierres, cambios pendientes y la próxima apertura dependen de la hora. El borde (API o consola) lee el reloj una vez y los casos de uso reciben `ahora`; los tests fijan el instante con `RelojFijo`. Solo `RelojDelSistema` lee la hora real, en UTC.

**¿Por qué una unidad de trabajo de plataforma?**
- El diseño tiene dos: la del local, que fija `app.local_id`, y la de plataforma, sin local fijado, para resolver el slug (y en la 1b, usuarios y sesiones). La de plataforma no expone `local_id`; la del local la extiende y suma el `set_config` al entrar.
- El puerto `UnidadDeTrabajo` extiende a `UnidadDeTrabajoDePlataforma`: todo lo que acepta una acepta las dos.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_reloj.py`:

```python
from datetime import UTC, datetime, timedelta

from minutas.compartido.aplicacion.reloj import Reloj
from minutas.compartido.infraestructura.reloj_del_sistema import RelojDelSistema
from soporte.reloj_fijo import RelojFijo


def test_ahora_del_reloj_del_sistema_es_utc_y_actual() -> None:
    reloj: Reloj = RelojDelSistema()

    ahora = reloj.ahora()

    assert ahora.tzinfo is UTC
    assert abs(datetime.now(UTC) - ahora) < timedelta(seconds=5)


def test_reloj_fijo_avanza_solo_cuando_se_le_pide() -> None:
    instante = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    reloj: Reloj = RelojFijo(instante)

    assert reloj.ahora() == instante
    assert isinstance(reloj, RelojFijo)
    reloj.avanzar(timedelta(hours=1))
    assert reloj.ahora() == instante + timedelta(hours=1)
```

`tests/integracion/test_unidad_de_trabajo.py` (cambios):

```diff
@@ -7,5 +7,8 @@ from sqlalchemy.exc import DBAPIError
 from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
 
-from minutas.compartido.aplicacion.unidad_de_trabajo import UnidadDeTrabajo
+from minutas.compartido.aplicacion.unidad_de_trabajo import (
+    UnidadDeTrabajo,
+    UnidadDeTrabajoDePlataforma,
+)
 from minutas.compartido.dominio.local_id import LocalId
 from minutas.compartido.infraestructura import unidad_de_trabajo_sqlalchemy
@@ -15,4 +18,5 @@ from minutas.compartido.infraestructura.base_de_datos import (
 )
 from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
+    UnidadDeTrabajoDePlataformaSQLAlchemy,
     UnidadDeTrabajoSQLAlchemy,
 )
@@ -78,2 +82,29 @@ async def test_asignar_adaptador_al_puerto_conserva_el_local(
 
     assert unidad.local_id == local_id
+
+
+async def test_unidad_de_plataforma_no_fija_ningun_local(
+    fabrica: async_sessionmaker[AsyncSession],
+) -> None:
+    async with UnidadDeTrabajoDePlataformaSQLAlchemy(fabrica) as unidad:
+        valor = await unidad.sesion.scalar(text("SELECT current_setting('app.local_id', true)"))
+
+    assert not valor
+
+
+async def test_salir_de_la_unidad_de_plataforma_devuelve_la_conexion_al_pool(
+    motor: AsyncEngine, fabrica: async_sessionmaker[AsyncSession]
+) -> None:
+    async with UnidadDeTrabajoDePlataformaSQLAlchemy(fabrica) as unidad:
+        await unidad.sesion.execute(text("SELECT 1"))
+        assert cast(QueuePool, motor.pool).checkedout() == 1
+
+    assert cast(QueuePool, motor.pool).checkedout() == 0
+
+
+def test_asignar_adaptador_de_plataforma_al_puerto_no_tiene_local(
+    fabrica: async_sessionmaker[AsyncSession],
+) -> None:
+    unidad: UnidadDeTrabajoDePlataforma = UnidadDeTrabajoDePlataformaSQLAlchemy(fabrica)
+
+    assert not hasattr(unidad, "local_id")
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_reloj.py tests/integracion/test_unidad_de_trabajo.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.aplicacion.reloj'`

## Paso 3: Implementación

`src/minutas/compartido/aplicacion/reloj.py`:

```python
"""Puerto de reloj: la hora actual llega de afuera para poder fijarla en los tests."""

from datetime import datetime
from typing import Protocol


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Instante actual, con zona horaria."""
        ...
```

`src/minutas/compartido/infraestructura/reloj_del_sistema.py`:

```python
"""Reloj real, en UTC."""

from datetime import UTC, datetime


class RelojDelSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)
```

`tests/soporte/reloj_fijo.py`:

```python
"""Reloj de prueba: devuelve siempre el instante que se le fija."""

from datetime import datetime, timedelta


class RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def ahora(self) -> datetime:
        return self.instante

    def avanzar(self, tiempo: timedelta) -> None:
        self.instante += tiempo
```

`src/minutas/compartido/aplicacion/unidad_de_trabajo.py`:

```python
"""Puertos de unidad de trabajo: una transacción, de plataforma o atada a un local."""

from types import TracebackType
from typing import Protocol, Self

from minutas.compartido.dominio.local_id import LocalId


class UnidadDeTrabajoDePlataforma(Protocol):
    """Transacción sin tenant, para las tablas de plataforma (locales, usuarios, sesiones)."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    async def confirmar(self) -> None: ...


class UnidadDeTrabajo(UnidadDeTrabajoDePlataforma, Protocol):
    """Transacción atada a un local: base de las unidades de trabajo con RLS."""

    @property
    def local_id(self) -> LocalId: ...
```

`src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py`:

```python
"""Unidades de trabajo sobre SQLAlchemy. Son de un solo uso."""

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId

FIJAR_LOCAL = text("SELECT set_config('app.local_id', :local_id, true)")


class UnidadDeTrabajoDePlataformaSQLAlchemy:
    """Transacción sin tenant: solo ve las tablas de plataforma, que no tienen RLS."""

    def __init__(self, fabrica_de_sesiones: async_sessionmaker[AsyncSession]) -> None:
        self._sesion = fabrica_de_sesiones()

    @property
    def sesion(self) -> AsyncSession:
        return self._sesion

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            await self._sesion.rollback()
        finally:
            await self._sesion.close()

    async def confirmar(self) -> None:
        await self._sesion.commit()


class UnidadDeTrabajoSQLAlchemy(UnidadDeTrabajoDePlataformaSQLAlchemy):
    """Transacción que fija el tenant para RLS al entrar."""

    def __init__(
        self, fabrica_de_sesiones: async_sessionmaker[AsyncSession], local_id: LocalId
    ) -> None:
        super().__init__(fabrica_de_sesiones)
        self._local_id = local_id

    @property
    def local_id(self) -> LocalId:
        return self._local_id

    async def __aenter__(self) -> Self:
        try:
            await self._sesion.execute(FIJAR_LOCAL, {"local_id": str(self._local_id)})
        except BaseException:
            await self._sesion.close()
            raise
        return self
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/compartido/test_reloj.py tests/integracion -v && uv run mypy`
Expected: PASS (2 passed; 7 en `test_unidad_de_trabajo.py`; el aislamiento entre locales sigue verde) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/compartido/aplicacion/reloj.py src/minutas/compartido/infraestructura/reloj_del_sistema.py tests/soporte/reloj_fijo.py src/minutas/compartido/aplicacion/unidad_de_trabajo.py src/minutas/compartido/infraestructura/unidad_de_trabajo_sqlalchemy.py tests/unitarios/compartido/test_reloj.py tests/integracion/test_unidad_de_trabajo.py
git commit -m "feat(compartido): reloj y unidad de trabajo de plataforma" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
