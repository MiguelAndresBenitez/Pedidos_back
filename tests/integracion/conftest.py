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
