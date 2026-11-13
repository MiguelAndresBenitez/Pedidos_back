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
