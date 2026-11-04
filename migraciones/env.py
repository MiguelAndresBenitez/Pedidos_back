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
