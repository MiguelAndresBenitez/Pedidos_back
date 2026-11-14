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
