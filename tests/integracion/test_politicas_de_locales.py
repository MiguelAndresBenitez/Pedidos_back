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
