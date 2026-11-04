from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import QueuePool, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from minutas.compartido.aplicacion.unidad_de_trabajo import UnidadDeTrabajo
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura import unidad_de_trabajo_sqlalchemy
from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
    UnidadDeTrabajoSQLAlchemy,
)
from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion


@pytest.fixture
async def motor(base_de_prueba: BaseDePrueba) -> AsyncIterator[AsyncEngine]:
    motor = crear_motor(base_de_prueba.url_app())
    yield motor
    await motor.dispose()


@pytest.fixture
def fabrica(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return crear_fabrica_de_sesiones(motor)


async def test_entrar_fija_el_local_en_la_transaccion(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_id = LocalId.generar()

    async with UnidadDeTrabajoSQLAlchemy(fabrica, local_id) as unidad:
        valor = await unidad.sesion.scalar(text("SELECT current_setting('app.local_id')"))

    assert valor == str(local_id)


async def test_confirmar_termina_la_transaccion_y_el_local_deja_de_valer(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    async with UnidadDeTrabajoSQLAlchemy(fabrica, LocalId.generar()) as unidad:
        await unidad.confirmar()
        valor = await unidad.sesion.scalar(text("SELECT current_setting('app.local_id', true)"))

    assert not valor


async def test_entrar_con_error_devuelve_la_conexion_al_pool(
    motor: AsyncEngine,
    fabrica: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentencia_que_falla = text("SELECT set_config('app.local_id', :local_id, true)::int")
    monkeypatch.setattr(unidad_de_trabajo_sqlalchemy, "FIJAR_LOCAL", sentencia_que_falla)

    with pytest.raises(DBAPIError, match="invalid input syntax for type integer"):
        async with UnidadDeTrabajoSQLAlchemy(fabrica, LocalId.generar()):
            pass

    assert cast(QueuePool, motor.pool).checkedout() == 0


async def test_asignar_adaptador_al_puerto_conserva_el_local(
    fabrica: async_sessionmaker[AsyncSession],
) -> None:
    local_id = LocalId.generar()

    unidad: UnidadDeTrabajo = UnidadDeTrabajoSQLAlchemy(fabrica, local_id)

    assert unidad.local_id == local_id
