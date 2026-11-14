# Tarea 13: Tablas, migración 0002 y políticas de RLS

**Archivos:**
- Crear: `src/minutas/compartido/infraestructura/metadata.py`
- Crear: `src/minutas/locales/infraestructura/tablas.py`
- Crear: `migraciones/versions/0002_locales.py`
- Crear: `tests/soporte/esquema.py`
- Modificar: `migraciones/env.py`
- Modificar: `migraciones/script.py.mako`
- Modificar: `tests/integracion/conftest.py`
- Test: `tests/integracion/test_migraciones.py`
- Test: `tests/integracion/test_politicas_de_locales.py`

---

## Decisiones de diseño

**¿Cómo queda el RLS de `locales`?**
- Por operación, como en el diseño: `SELECT` abierto (resolver el slug sin local fijado), `INSERT` y `UPDATE` solo con `id = app.local_id`, y sin política de `DELETE`, así no se puede borrar ninguna fila. `franjas_horarias` lleva la política estándar de la etapa 0 (`sentencias_de_aislamiento`).
- Sin local fijado, una escritura falla cerrado: `current_setting` lanza error si la variable no existe, o falla al convertir `''` a `uuid` en una conexión reusada del pool.

**¿Qué guarda `locales`?**
- Las columnas del diseño, más `version` (bloqueo optimista) y `zona_horaria_pendiente` (cambio pendiente de zona). Los `CHECK` repiten en la base lo que el dominio ya valida: alguna modalidad, estado conocido, las tres columnas del cambio pendiente nulas o no nulas juntas, y la jornada del cierre solo si es `por_jornada`.

**¿Por qué `METADATA` con convención de nombres?**
- Alembic la compara con la base (`alembic check` en los tests). Los nombres estables (`uq_locales_slug`) los usa el repositorio para traducir violaciones a errores de dominio. `env.py` importa los módulos de tablas para registrarlas.

**La migración tiene sus sentencias de RLS escritas en ella**, sin importar código de la app: una migración no debe cambiar si cambia el código.

**Los tests de políticas usan SQL crudo** con la unidad de trabajo de la etapa 0: prueban la base, no el repositorio (que llega en la tarea 14).

**Fixtures:** `base_migrada` lleva la base a `head` y vacía las tablas (`TRUNCATE` no pasa por RLS); `fabrica_de_sesiones` conecta como `minutas_app`.

---

## Paso 1: Escribir el test que falla

`tests/integracion/test_migraciones.py`:

```python
import asyncio

import asyncpg
import pytest
from alembic import command

from soporte.base_de_prueba import BaseDePrueba
from soporte.esquema import crear_configuracion_alembic

pytestmark = pytest.mark.integracion

TABLAS_DE_LA_APP = ["franjas_horarias", "locales"]


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


async def listar_tablas_con_permisos_de_app(dsn: str) -> list[str]:
    conexion = await asyncpg.connect(dsn)
    try:
        filas = await conexion.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND has_table_privilege('minutas_app', format('%I.%I', schemaname, tablename), "
            "'SELECT, INSERT, UPDATE, DELETE') "
            "ORDER BY tablename"
        )
    finally:
        await conexion.close()
    return [fila["tablename"] for fila in filas]


def test_migrar_hasta_head_deja_la_version_0002_con_owner_como_duenio(
    base_de_prueba: BaseDePrueba,
) -> None:
    configuracion = crear_configuracion_alembic(base_de_prueba.url_owner())

    command.upgrade(configuracion, "head")
    try:
        version, duenio = asyncio.run(consultar_version_y_duenio(base_de_prueba.dsn_admin()))
    finally:
        command.downgrade(configuracion, "base")

    assert version == "0002"
    assert duenio == "minutas_owner"


def test_migrar_hasta_head_da_a_la_app_acceso_a_las_tablas_nuevas(
    base_de_prueba: BaseDePrueba,
) -> None:
    configuracion = crear_configuracion_alembic(base_de_prueba.url_owner())

    command.upgrade(configuracion, "head")
    try:
        tablas = asyncio.run(listar_tablas_con_permisos_de_app(base_de_prueba.dsn_admin()))
    finally:
        command.downgrade(configuracion, "base")

    assert tablas == TABLAS_DE_LA_APP


def test_check_despues_de_migrar_no_encuentra_diferencias_con_las_tablas(
    base_de_prueba: BaseDePrueba,
) -> None:
    configuracion = crear_configuracion_alembic(base_de_prueba.url_owner())

    command.upgrade(configuracion, "head")
    try:
        command.check(configuracion)
    finally:
        command.downgrade(configuracion, "base")


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

`tests/integracion/test_politicas_de_locales.py`:

```python
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from sqlalchemy import CursorResult, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
    UnidadDeTrabajoDePlataformaSQLAlchemy,
    UnidadDeTrabajoSQLAlchemy,
)

pytestmark = pytest.mark.integracion

type Fabrica = async_sessionmaker[AsyncSession]

LEER_SLUGS = text("SELECT slug FROM locales ORDER BY slug")
RENOMBRAR = text("UPDATE locales SET nombre = 'pisado'")
BORRAR = text("DELETE FROM locales")
CONTAR_FRANJAS = text("SELECT count(*) FROM franjas_horarias")
INSERTAR_FRANJA = text(
    "INSERT INTO franjas_horarias (id, local_id, dia, apertura, cierre) "
    "VALUES (gen_random_uuid(), :local_id, 0, '20:00', '23:00')"
)
INSERTAR_LOCAL = text(
    "INSERT INTO locales (id, slug, nombre, whatsapp, color, ofrece_delivery, ofrece_retiro, "
    "zona_horaria, hora_de_corte, estado, version) VALUES (:id, :slug, 'Local', "
    "'5493515123456', '#000000', true, false, 'UTC', '06:00', 'activo', 0)"
)


async def dar_de_alta(fabrica: Fabrica, slug: str) -> LocalId:
    """Inserta con SQL crudo y el local fijado: la política `alta_propia` lo exige."""
    local_id = LocalId.generar()
    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_id) as unidad:
        await unidad.sesion.execute(INSERTAR_LOCAL, {"id": local_id.valor, "slug": slug})
        await unidad.confirmar()
    return local_id


@pytest.fixture
async def dos_locales(fabrica_de_sesiones: Fabrica) -> AsyncIterator[tuple[LocalId, LocalId]]:
    yield (
        await dar_de_alta(fabrica_de_sesiones, "local-a"),
        await dar_de_alta(fabrica_de_sesiones, "local-b"),
    )


@pytest.mark.usefixtures("dos_locales")
async def test_leer_locales_sin_local_fijado_ve_todos(fabrica_de_sesiones: Fabrica) -> None:
    async with UnidadDeTrabajoDePlataformaSQLAlchemy(fabrica_de_sesiones) as unidad:
        slugs = (await unidad.sesion.scalars(LEER_SLUGS)).all()

    assert slugs == ["local-a", "local-b"]


@pytest.mark.usefixtures("dos_locales")
async def test_modificar_locales_sin_local_fijado_falla(fabrica_de_sesiones: Fabrica) -> None:
    async with UnidadDeTrabajoDePlataformaSQLAlchemy(fabrica_de_sesiones) as unidad:
        # Falla cerrado: sin `app.local_id` (o vacío en una conexión reusada del pool).
        with pytest.raises(DBAPIError, match=r"app\.local_id|type uuid"):
            await unidad.sesion.execute(RENOMBRAR)


async def test_modificar_locales_con_un_local_fijado_solo_toca_ese(
    fabrica_de_sesiones: Fabrica, dos_locales: tuple[LocalId, LocalId]
) -> None:
    local_a, _ = dos_locales

    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_a) as unidad:
        resultado = await unidad.sesion.execute(RENOMBRAR)

    assert cast(CursorResult[Any], resultado).rowcount == 1


async def test_insertar_un_local_con_otro_id_que_el_fijado_falla(
    fabrica_de_sesiones: Fabrica, dos_locales: tuple[LocalId, LocalId]
) -> None:
    local_a, _ = dos_locales

    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_a) as unidad:
        with pytest.raises(DBAPIError, match="row-level security"):
            await unidad.sesion.execute(
                INSERTAR_LOCAL, {"id": LocalId.generar().valor, "slug": "ajeno"}
            )


async def test_borrar_locales_no_afecta_ninguna_fila(
    fabrica_de_sesiones: Fabrica, dos_locales: tuple[LocalId, LocalId]
) -> None:
    local_a, _ = dos_locales

    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_a) as unidad:
        resultado = await unidad.sesion.execute(BORRAR)

    assert cast(CursorResult[Any], resultado).rowcount == 0


async def test_franjas_de_otro_local_no_se_ven(
    fabrica_de_sesiones: Fabrica, dos_locales: tuple[LocalId, LocalId]
) -> None:
    local_a, local_b = dos_locales
    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_b) as unidad:
        await unidad.sesion.execute(INSERTAR_FRANJA, {"local_id": local_b.valor})
        await unidad.confirmar()

    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_a) as unidad:
        assert await unidad.sesion.scalar(CONTAR_FRANJAS) == 0


async def test_insertar_una_franja_para_otro_local_falla(
    fabrica_de_sesiones: Fabrica, dos_locales: tuple[LocalId, LocalId]
) -> None:
    local_a, local_b = dos_locales

    async with UnidadDeTrabajoSQLAlchemy(fabrica_de_sesiones, local_a) as unidad:
        with pytest.raises(DBAPIError, match="row-level security"):
            await unidad.sesion.execute(INSERTAR_FRANJA, {"local_id": local_b.valor})
```

`tests/soporte/esquema.py`:

```python
"""Esquema de la base de pruebas: migraciones hasta head y tablas vacías entre tests."""

from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config

from soporte.base_de_prueba import BaseDePrueba

RAIZ = Path(__file__).resolve().parents[2]
# TRUNCATE no pasa por RLS: el owner vacía todo sin fijar un local.
VACIAR_TABLAS = "TRUNCATE locales, franjas_horarias"


def crear_configuracion_alembic(url: str) -> Config:
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("sqlalchemy.url", url)
    return configuracion


def migrar_hasta_head(base: BaseDePrueba) -> None:
    command.upgrade(crear_configuracion_alembic(base.url_owner()), "head")


async def vaciar_tablas(base: BaseDePrueba) -> None:
    conexion = await asyncpg.connect(base.dsn_owner())
    try:
        await conexion.execute(VACIAR_TABLAS)
    finally:
        await conexion.close()
```

`tests/integracion/conftest.py` (cambios):

```diff
@@ -1,11 +1,17 @@
 import asyncio
-from collections.abc import Iterator
+from collections.abc import AsyncIterator, Iterator
 from pathlib import Path
 
 import asyncpg
 import pytest
+from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
 from testcontainers.community.postgres import PostgresContainer
 
+from minutas.compartido.infraestructura.base_de_datos import (
+    crear_fabrica_de_sesiones,
+    crear_motor,
+)
 from soporte.base_de_prueba import BaseDePrueba
+from soporte.esquema import migrar_hasta_head, vaciar_tablas
 
 RAIZ = Path(__file__).resolve().parents[2]
@@ -35,2 +41,19 @@ def base_de_prueba() -> Iterator[BaseDePrueba]:
         asyncio.run(preparar_roles(base))
         yield base
+
+
+@pytest.fixture
+def base_migrada(base_de_prueba: BaseDePrueba) -> BaseDePrueba:
+    """Base en head y con las tablas vacías."""
+    migrar_hasta_head(base_de_prueba)
+    asyncio.run(vaciar_tablas(base_de_prueba))
+    return base_de_prueba
+
+
+@pytest.fixture
+async def fabrica_de_sesiones(
+    base_migrada: BaseDePrueba,
+) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
+    motor = crear_motor(base_migrada.url_app())
+    yield crear_fabrica_de_sesiones(motor)
+    await motor.dispose()
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/integracion/test_migraciones.py tests/integracion/test_politicas_de_locales.py -v`
Expected: FAIL: `assert '0001' == '0002'` y `relation "locales" does not exist`

## Paso 3: Implementación

`src/minutas/compartido/infraestructura/metadata.py`:

```python
"""MetaData compartida por las tablas de todos los contextos; Alembic la compara con la base."""

from sqlalchemy import MetaData

METADATA = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
```

`src/minutas/locales/infraestructura/tablas.py`:

```python
"""Tablas del contexto Locales. `locales` tiene RLS por operación; `franjas_horarias`, completo."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Table,
    Text,
    Time,
    Uuid,
    func,
)

from minutas.compartido.infraestructura.metadata import METADATA

LOCALES = Table(
    "locales",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("slug", Text, nullable=False, unique=True),
    Column("nombre", Text, nullable=False),
    Column("descripcion", Text),
    Column("direccion", Text),
    Column("whatsapp", Text, nullable=False),
    Column("color", Text, nullable=False),
    Column("ofrece_delivery", Boolean, nullable=False),
    Column("ofrece_retiro", Boolean, nullable=False),
    Column("zona_horaria", Text, nullable=False),
    Column("hora_de_corte", Time, nullable=False),
    Column("zona_horaria_pendiente", Text),
    Column("hora_de_corte_pendiente", Time),
    Column("reglas_desde_jornada", Date),
    Column("cierre_manual", Text),
    Column("cierre_manual_jornada", Date),
    Column("logo", Text),
    Column("portada", Text),
    Column("estado", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("actualizado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("ofrece_delivery OR ofrece_retiro", name="modalidades"),
    CheckConstraint("estado IN ('activo', 'suspendido')", name="estado"),
    CheckConstraint(
        "num_nulls(zona_horaria_pendiente, hora_de_corte_pendiente, reglas_desde_jornada) "
        "IN (0, 3)",
        name="reglas_pendientes",
    ),
    CheckConstraint("cierre_manual IN ('por_jornada', 'hasta_nuevo_aviso')", name="cierre_manual"),
    CheckConstraint(
        "(cierre_manual IS NOT DISTINCT FROM 'por_jornada') = (cierre_manual_jornada IS NOT NULL)",
        name="cierre_manual_jornada",
    ),
)

FRANJAS_HORARIAS = Table(
    "franjas_horarias",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("local_id", Uuid, ForeignKey("locales.id"), nullable=False, index=True),
    Column("dia", SmallInteger, nullable=False),
    Column("apertura", Time, nullable=False),
    Column("cierre", Time, nullable=False),
    CheckConstraint("dia BETWEEN 0 AND 6", name="dia"),
)
```

`migraciones/env.py`:

```python
"""Entorno de Alembic: migra con el rol dueño de las tablas, sobre asyncpg."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from minutas.compartido.infraestructura.configuracion import ConfiguracionDeMigraciones
from minutas.compartido.infraestructura.metadata import METADATA
from minutas.locales.infraestructura import tablas as tablas_de_locales

# Importar los módulos de tablas las registra en METADATA, que Alembic compara con la base.
CONTEXTOS_CON_TABLAS = (tablas_de_locales,)


def obtener_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    return url or ConfiguracionDeMigraciones().url_base_de_datos_migraciones.get_secret_value()


def ejecutar_migraciones(conexion: Connection) -> None:
    context.configure(connection=conexion, target_metadata=METADATA, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def migrar() -> None:
    motor = create_async_engine(obtener_url())
    async with motor.connect() as conexion:
        await conexion.run_sync(ejecutar_migraciones)
    await motor.dispose()


asyncio.run(migrar())
```

`migraciones/script.py.mako` (cambios):

```diff
@@ -3,4 +3,5 @@
 from collections.abc import Sequence
 
+import sqlalchemy as sa
 from alembic import op
 ${imports if imports else ""}
```

`migraciones/versions/0002_locales.py`:

```python
"""Locales y franjas horarias, con RLS: `locales` por operación y `franjas_horarias` completo."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AHORA = sa.text("now()")
LOCAL_FIJADO = "id = current_setting('app.local_id')::uuid"

# Lectura abierta para resolver el slug; escritura solo con ese local fijado. Sin DELETE.
AISLAMIENTO_DE_LOCALES = [
    "ALTER TABLE locales ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE locales FORCE ROW LEVEL SECURITY",
    "CREATE POLICY lectura_publica ON locales FOR SELECT USING (true)",
    f"CREATE POLICY alta_propia ON locales FOR INSERT WITH CHECK ({LOCAL_FIJADO})",
    f"CREATE POLICY escritura_propia ON locales FOR UPDATE "
    f"USING ({LOCAL_FIJADO}) WITH CHECK ({LOCAL_FIJADO})",
]

# La política estándar de la etapa 0, copiada: la migración no depende del código de la app.
DEL_LOCAL = "local_id = current_setting('app.local_id')::uuid"
AISLAMIENTO_DE_FRANJAS = [
    "ALTER TABLE franjas_horarias ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE franjas_horarias FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY aislamiento_local ON franjas_horarias USING ({DEL_LOCAL}) "
    f"WITH CHECK ({DEL_LOCAL})",
]


def upgrade() -> None:
    op.create_table(
        "locales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("whatsapp", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("ofrece_delivery", sa.Boolean(), nullable=False),
        sa.Column("ofrece_retiro", sa.Boolean(), nullable=False),
        sa.Column("zona_horaria", sa.Text(), nullable=False),
        sa.Column("hora_de_corte", sa.Time(), nullable=False),
        sa.Column("zona_horaria_pendiente", sa.Text(), nullable=True),
        sa.Column("hora_de_corte_pendiente", sa.Time(), nullable=True),
        sa.Column("reglas_desde_jornada", sa.Date(), nullable=True),
        sa.Column("cierre_manual", sa.Text(), nullable=True),
        sa.Column("cierre_manual_jornada", sa.Date(), nullable=True),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("portada", sa.Text(), nullable=True),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False
        ),
        sa.CheckConstraint("ofrece_delivery OR ofrece_retiro", name=op.f("ck_locales_modalidades")),
        sa.CheckConstraint("estado IN ('activo', 'suspendido')", name=op.f("ck_locales_estado")),
        sa.CheckConstraint(
            "num_nulls(zona_horaria_pendiente, hora_de_corte_pendiente, reglas_desde_jornada) "
            "IN (0, 3)",
            name=op.f("ck_locales_reglas_pendientes"),
        ),
        sa.CheckConstraint(
            "cierre_manual IN ('por_jornada', 'hasta_nuevo_aviso')",
            name=op.f("ck_locales_cierre_manual"),
        ),
        sa.CheckConstraint(
            "(cierre_manual IS NOT DISTINCT FROM 'por_jornada') = "
            "(cierre_manual_jornada IS NOT NULL)",
            name=op.f("ck_locales_cierre_manual_jornada"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locales")),
        sa.UniqueConstraint("slug", name=op.f("uq_locales_slug")),
    )
    op.create_table(
        "franjas_horarias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("local_id", sa.Uuid(), nullable=False),
        sa.Column("dia", sa.SmallInteger(), nullable=False),
        sa.Column("apertura", sa.Time(), nullable=False),
        sa.Column("cierre", sa.Time(), nullable=False),
        sa.CheckConstraint("dia BETWEEN 0 AND 6", name=op.f("ck_franjas_horarias_dia")),
        sa.ForeignKeyConstraint(
            ["local_id"], ["locales.id"], name=op.f("fk_franjas_horarias_local_id_locales")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_franjas_horarias")),
    )
    op.create_index(
        op.f("ix_franjas_horarias_local_id"), "franjas_horarias", ["local_id"], unique=False
    )
    for sentencia in [*AISLAMIENTO_DE_LOCALES, *AISLAMIENTO_DE_FRANJAS]:
        op.execute(sentencia)


def downgrade() -> None:
    op.drop_table("franjas_horarias")
    op.drop_table("locales")
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/integracion -v && uv run mypy`
Expected: PASS (4 passed en `test_migraciones.py`, incluido `alembic check` sin diferencias; 7 en `test_politicas_de_locales.py`) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/metadata.py src/minutas/locales/infraestructura/tablas.py migraciones/env.py migraciones/script.py.mako migraciones/versions/0002_locales.py tests/soporte/esquema.py tests/integracion/conftest.py tests/integracion/test_migraciones.py tests/integracion/test_politicas_de_locales.py
git commit -m "feat(infra): tablas de locales y franjas con rls por operación" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
