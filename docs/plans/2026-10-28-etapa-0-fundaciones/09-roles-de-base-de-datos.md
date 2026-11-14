# Tarea 9: Roles de base de datos

**Archivos:**
- Crear: `docker/postgres/roles.sql`
- Crear: `tests/soporte/__init__.py`, `tests/soporte/base_de_prueba.py`
- Crear: `tests/integracion/conftest.py`
- Modificar: `pyproject.toml` (`[tool.pytest.ini_options]`, clave `pythonpath`)
- Test: `tests/integracion/test_roles.py`

---

## Decisiones de diseño

**¿Por qué dos roles, `minutas_owner` y `minutas_app`?**
- La spec exige que la API se conecte con un rol sin `BYPASSRLS` y que no sea dueño de las tablas: el dueño de una tabla puede saltear RLS.
- `minutas_owner` crea las tablas en las migraciones; `minutas_app` recibe solo `SELECT, INSERT, UPDATE, DELETE` por privilegios por defecto.

**¿Por qué `roles.sql` no tiene contraseñas?**
- Es el mismo archivo para Docker (tarea 14) y para los tests. Cada uno fija las contraseñas por su lado: Docker desde variables de entorno y los tests con valores de prueba.

**¿Por qué un contenedor de PostgreSQL por sesión de tests?**
- Arrancar un contenedor tarda segundos: se comparte entre todos los tests de integración. Cada test crea y borra sus propias tablas.
- El fixture es sincrónico (testcontainers lo es) y corre la preparación async con `asyncio.run`, fuera del loop de los tests.

**¿Por qué `BaseDePrueba` en `tests/soporte/` y no en el `conftest.py`?**
- Con `--import-mode=importlib` un test no puede importar desde `conftest.py`. En `soporte`, con `pythonpath = ["tests"]`, los tests tipan el fixture con la clase real en lugar de `Any`.

---

## Paso 1: Escribir el test que falla

En `pyproject.toml`, sección `[tool.pytest.ini_options]`, agregar:

```toml
pythonpath = ["tests"]
```

`tests/soporte/__init__.py`:

```python
"""Código de apoyo compartido por los tests."""
```

`tests/soporte/base_de_prueba.py`:

```python
"""Datos de conexión al PostgreSQL de pruebas, con sus tres roles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BaseDePrueba:
    host: str
    puerto: int
    nombre: str
    usuario_admin: str
    clave_admin: str

    def dsn(self, usuario: str, clave: str) -> str:
        return f"postgresql://{usuario}:{clave}@{self.host}:{self.puerto}/{self.nombre}"

    def dsn_admin(self) -> str:
        return self.dsn(self.usuario_admin, self.clave_admin)

    def dsn_owner(self) -> str:
        return self.dsn("minutas_owner", "owner-pruebas")

    def dsn_app(self) -> str:
        return self.dsn("minutas_app", "app-pruebas")

    def url_owner(self) -> str:
        return self.dsn_owner().replace("postgresql://", "postgresql+asyncpg://", 1)

    def url_app(self) -> str:
        return self.dsn_app().replace("postgresql://", "postgresql+asyncpg://", 1)
```

`tests/integracion/conftest.py`:

```python
import asyncio
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from testcontainers.community.postgres import PostgresContainer

from soporte.base_de_prueba import BaseDePrueba

RAIZ = Path(__file__).resolve().parents[2]
ROLES_SQL = RAIZ / "docker" / "postgres" / "roles.sql"


async def preparar_roles(base: BaseDePrueba) -> None:
    conexion = await asyncpg.connect(base.dsn_admin())
    try:
        await conexion.execute(ROLES_SQL.read_text())
        await conexion.execute("ALTER ROLE minutas_owner PASSWORD 'owner-pruebas'")
        await conexion.execute("ALTER ROLE minutas_app PASSWORD 'app-pruebas'")
    finally:
        await conexion.close()


@pytest.fixture(scope="session")
def base_de_prueba() -> Iterator[BaseDePrueba]:
    with PostgresContainer("postgres:17-alpine") as contenedor:
        base = BaseDePrueba(
            host=contenedor.get_container_host_ip(),
            puerto=int(contenedor.get_exposed_port(5432)),
            nombre=contenedor.dbname,
            usuario_admin=contenedor.username,
            clave_admin=contenedor.password,
        )
        asyncio.run(preparar_roles(base))
        yield base
```

`tests/integracion/test_roles.py`:

```python
import asyncpg
import pytest

from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion


async def test_consultar_rol_app_no_tiene_bypassrls_ni_superusuario(
    base_de_prueba: BaseDePrueba,
) -> None:
    conexion = await asyncpg.connect(base_de_prueba.dsn_admin())
    try:
        fila = await conexion.fetchrow(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'minutas_app'"
        )
    finally:
        await conexion.close()

    assert fila["rolsuper"] is False
    assert fila["rolbypassrls"] is False


async def test_crear_tabla_como_app_falla(base_de_prueba: BaseDePrueba) -> None:
    conexion = await asyncpg.connect(base_de_prueba.dsn_app())
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="schema public"):
            await conexion.execute("CREATE TABLE intrusa (id int)")
    finally:
        await conexion.close()


async def test_crear_tabla_como_owner_da_permisos_de_datos_a_app(
    base_de_prueba: BaseDePrueba,
) -> None:
    owner = await asyncpg.connect(base_de_prueba.dsn_owner())
    try:
        await owner.execute("CREATE TABLE prueba_privilegios (id int)")
        app = await asyncpg.connect(base_de_prueba.dsn_app())
        try:
            await app.execute("INSERT INTO prueba_privilegios VALUES (1)")
            cantidad = await app.fetchval("SELECT count(*) FROM prueba_privilegios")
        finally:
            await app.close()
    finally:
        await owner.execute("DROP TABLE prueba_privilegios")
        await owner.close()

    assert cantidad == 1
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/integracion/test_roles.py -v`
Expected: ERROR en el fixture `base_de_prueba` con `FileNotFoundError: [Errno 2] No such file or directory: '.../docker/postgres/roles.sql'`

## Paso 3: Implementación mínima

`docker/postgres/roles.sql`:

```sql
-- Roles de Minutas. Lo ejecuta el superusuario una sola vez, sobre la base de la app.
-- Las contraseñas se fijan aparte (Docker: 02-claves.sh; tests: conftest.py).

CREATE ROLE minutas_owner LOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE minutas_app LOGIN NOSUPERUSER NOBYPASSRLS;

GRANT USAGE, CREATE ON SCHEMA public TO minutas_owner;
GRANT USAGE ON SCHEMA public TO minutas_app;

ALTER DEFAULT PRIVILEGES FOR ROLE minutas_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO minutas_app;
ALTER DEFAULT PRIVILEGES FOR ROLE minutas_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO minutas_app;
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/integracion/test_roles.py -v`
Expected: PASS (3 passed). La primera corrida descarga la imagen `postgres:17-alpine`.

## Paso 5: Commit

```bash
git add pyproject.toml docker/postgres/roles.sql tests/soporte tests/integracion/conftest.py tests/integracion/test_roles.py
git commit -m "feat(infra): roles minutas_owner y minutas_app con privilegios separados" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
