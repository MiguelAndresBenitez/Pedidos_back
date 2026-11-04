# Tarea 10: Migraciones con Alembic

**Archivos:**
- Crear: `alembic.ini`
- Crear: `migraciones/env.py`, `migraciones/script.py.mako`
- Crear: `migraciones/versions/0001_base.py`
- Modificar: `pyproject.toml` (`[tool.mypy]` clave `files`, y `[tool.ruff.lint.per-file-ignores]`)
- Test: `tests/integracion/test_migraciones.py`

---

## Decisiones de diseño

**¿Por qué `env.py` asíncrono?**
- El proyecto usa solo el driver `asyncpg` (ver `docs/plans/00-conventions.md`): no se suma un driver sincrónico solo para migrar.

**¿Por qué la URL sale de `sqlalchemy.url` y, si no está, de `ConfiguracionDeMigraciones`?**
- En Docker y en producción la toma de `MINUTAS_URL_BASE_DE_DATOS_MIGRACIONES` (rol `minutas_owner`).
- Los tests la pasan con `set_main_option` apuntando al contenedor, sin tocar el entorno.

**¿Por qué la revisión `0001` solo revoca permisos sobre `alembic_version`?**
- Fija el punto de partida y prueba la cadena completa (Alembic, rol dueño, `alembic_version`) antes de que existan tablas reales.
- Los privilegios por defecto de `roles.sql` le dan a `minutas_app` acceso a toda tabla del owner, incluida `alembic_version`. La API no tiene por qué leer ni tocar el estado de las migraciones.
- El `downgrade` no devuelve el permiso: volver a un estado menos seguro no aporta nada.
- Las revisiones se numeran a mano y en orden (`--rev-id 0002`): se leen mejor que un hash.

**¿Por qué `target_metadata = None`?**
- El mapeo imperativo llega en la etapa 1 con las primeras tablas; hasta entonces no hay nada que autogenerar.

---

## Paso 1: Escribir el test que falla

`tests/integracion/test_migraciones.py`:

```python
import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion

RAIZ = Path(__file__).resolve().parents[2]


def crear_configuracion_alembic(url: str) -> Config:
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("sqlalchemy.url", url)
    return configuracion


async def consultar_version_y_duenio(dsn: str) -> tuple[str | None, str | None]:
    conexion = await asyncpg.connect(dsn)
    try:
        version = await conexion.fetchval("SELECT version_num FROM alembic_version")
        duenio = await conexion.fetchval(
            "SELECT tableowner FROM pg_tables WHERE tablename = 'alembic_version'"
        )
    finally:
        await conexion.close()
    return version, duenio


def test_migrar_hasta_head_deja_la_version_0001_con_owner_como_duenio(
    base_de_prueba: BaseDePrueba,
) -> None:
    configuracion = crear_configuracion_alembic(base_de_prueba.url_owner())

    command.upgrade(configuracion, "head")
    try:
        version, duenio = asyncio.run(consultar_version_y_duenio(base_de_prueba.dsn_admin()))
    finally:
        command.downgrade(configuracion, "base")

    assert version == "0001"
    assert duenio == "minutas_owner"


async def leer_version_como_app(dsn: str) -> None:
    conexion = await asyncpg.connect(dsn)
    try:
        await conexion.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conexion.close()


def test_migrar_hasta_head_no_da_acceso_a_alembic_version_al_rol_app(
    base_de_prueba: BaseDePrueba,
) -> None:
    configuracion = crear_configuracion_alembic(base_de_prueba.url_owner())

    command.upgrade(configuracion, "head")
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="alembic_version"):
            asyncio.run(leer_version_como_app(base_de_prueba.dsn_app()))
    finally:
        command.downgrade(configuracion, "base")
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/integracion/test_migraciones.py -v`
Expected: FAIL con `alembic.util.exc.CommandError: No 'script_location' key found in configuration.`

## Paso 3: Implementación mínima

`alembic.ini`:

```ini
[alembic]
script_location = %(here)s/migraciones
file_template = %%(rev)s_%%(slug)s
prepend_sys_path = .
path_separator = os
```

`migraciones/env.py`:

```python
"""Entorno de Alembic: migra con el rol dueño de las tablas, sobre asyncpg."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from minutas.compartido.infraestructura.configuracion import ConfiguracionDeMigraciones


def obtener_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    return url or ConfiguracionDeMigraciones().url_base_de_datos_migraciones


def ejecutar_migraciones(conexion: Connection) -> None:
    context.configure(connection=conexion, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def migrar() -> None:
    motor = create_async_engine(obtener_url())
    async with motor.connect() as conexion:
        await conexion.run_sync(ejecutar_migraciones)
    await motor.dispose()


asyncio.run(migrar())
```

`migraciones/script.py.mako`:

```mako
"""${message}"""

from collections.abc import Sequence

from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`migraciones/versions/0001_base.py`:

```python
"""Base: punto de partida de las migraciones."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Las tablas llegan con cada contexto desde la etapa 1; acá solo se protege alembic_version."""
    op.execute("REVOKE ALL ON alembic_version FROM minutas_app")


def downgrade() -> None:
    """No se devuelve el permiso a minutas_app."""
```

En `pyproject.toml`, sección `[tool.mypy]`, reemplazar `files = ["src", "tests"]` por (las revisiones quedan afuera porque `0001_base` no es un nombre de módulo válido para mypy):

```toml
files = ["src", "tests", "migraciones/env.py"]
```

En `pyproject.toml`, sección `[tool.ruff.lint.per-file-ignores]`, agregar. `N999` marca el nombre del archivo, por la misma razón; `F401` marca el `from alembic import op` que la plantilla incluye siempre, aunque una revisión no lo use:

```toml
"migraciones/versions/*" = ["N999", "F401"]
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/integracion/test_migraciones.py -v`
Expected: PASS (2 passed)

Run: `uv run mypy && uv run ruff check`
Expected: `Success: no issues found in N source files` y `All checks passed!`

## Paso 5: Commit

```bash
git add alembic.ini migraciones pyproject.toml tests/integracion/test_migraciones.py
git commit -m "feat(infra): migraciones con Alembic asíncrono y revisión base 0001" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
