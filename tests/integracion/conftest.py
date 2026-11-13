import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from soporte.base_de_prueba import BaseDePrueba
from soporte.esquema import migrar_hasta_head, vaciar_tablas

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


@pytest.fixture
def base_migrada(base_de_prueba: BaseDePrueba) -> BaseDePrueba:
    """Base en head y con las tablas vacías."""
    migrar_hasta_head(base_de_prueba)
    asyncio.run(vaciar_tablas(base_de_prueba))
    return base_de_prueba


@pytest.fixture
async def fabrica_de_sesiones(
    base_migrada: BaseDePrueba,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    motor = crear_motor(base_migrada.url_app())
    yield crear_fabrica_de_sesiones(motor)
    await motor.dispose()
