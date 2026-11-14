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
