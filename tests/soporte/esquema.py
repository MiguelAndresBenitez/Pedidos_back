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
