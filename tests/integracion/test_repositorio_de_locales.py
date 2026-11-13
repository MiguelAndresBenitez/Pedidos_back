from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.cierre_manual import CierrePorJornada
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import (
    LocalModificadoEnParalelo,
    LocalNoEncontrado,
    SlugEnUso,
)
from minutas.locales.dominio.estado_del_local import Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from minutas.locales.infraestructura.unidades_de_trabajo_sqlalchemy import (
    UnidadDelDirectorioSQLAlchemy,
    UnidadDelLocalSQLAlchemy,
)

pytestmark = pytest.mark.integracion

LEER_IDS_DE_FRANJAS = text("SELECT id FROM franjas_horarias ORDER BY id")

type Fabrica = async_sessionmaker[AsyncSession]

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
AHORA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


def nuevo_local(slug: str = "la-esquina") -> Local:
    return crear_local(
        Slug(slug),
        "La Esquina",
        Whatsapp("5493515123456"),
        frozenset({Modalidad.DELIVERY, Modalidad.RETIRO}),
    )


async def agregar(fabrica: Fabrica, local: Local) -> None:
    async with UnidadDelLocalSQLAlchemy(fabrica, local.id) as unidad:
        await unidad.locales.agregar(local)
        await unidad.confirmar()


async def obtener(fabrica: Fabrica, local_id: LocalId) -> Local:
    async with UnidadDelLocalSQLAlchemy(fabrica, local_id) as unidad:
        return await unidad.locales.obtener()


async def guardar(fabrica: Fabrica, local: Local) -> None:
    async with UnidadDelLocalSQLAlchemy(fabrica, local.id) as unidad:
        await unidad.locales.guardar(local)
        await unidad.confirmar()


async def test_agregar_y_obtener_conserva_todo_el_agregado(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    local.reemplazar_horario(
        Horario(
            (
                FranjaHoraria(DiaDeLaSemana.LUNES, time(12), time(15)),
                FranjaHoraria(DiaDeLaSemana.DOMINGO, time(20), time(1, 30)),
            )
        ),
        AHORA,
    )
    local.cerrar_por_hoy(AHORA)
    local.cambiar_imagen(TipoDeImagen.LOGO, LOGO)
    local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), AHORA)
    local.suspender()
    await agregar(fabrica_de_sesiones, local)

    leido = await obtener(fabrica_de_sesiones, local.id)

    assert leido.slug == local.slug
    assert leido.datos == local.datos
    assert leido.horario == local.horario
    assert leido.cierre_manual == local.cierre_manual
    assert leido.jornada == local.jornada
    assert leido.imagenes == {TipoDeImagen.LOGO: LOGO}
    assert leido.estado == Suspendido()
    assert leido.version == 0


async def test_guardar_reemplaza_las_franjas_e_incrementa_la_version(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)
    leido = await obtener(fabrica_de_sesiones, local.id)
    horario = Horario((FranjaHoraria(DiaDeLaSemana.MARTES, time(20), time(0, 30)),))
    leido.reemplazar_horario(horario, AHORA)

    await guardar(fabrica_de_sesiones, leido)

    guardado = await obtener(fabrica_de_sesiones, local.id)
    assert guardado.horario == horario
    assert guardado.version == 1


async def test_suspension_durante_una_edicion_del_admin_no_se_pierde(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelLocalSQLAlchemy(fabrica_de_sesiones, local.id) as edicion_del_admin:
        leido_por_el_admin = await edicion_del_admin.locales.obtener()

        a_suspender = await obtener(fabrica_de_sesiones, local.id)
        a_suspender.suspender()
        await guardar(fabrica_de_sesiones, a_suspender)

        leido_por_el_admin.reabrir()
        with pytest.raises(LocalModificadoEnParalelo, match="volvé a cargarlo"):
            await edicion_del_admin.locales.guardar(leido_por_el_admin)

    assert (await obtener(fabrica_de_sesiones, local.id)).estado == Suspendido()


async def test_agregar_local_con_slug_en_uso_falla(fabrica_de_sesiones: Fabrica) -> None:
    await agregar(fabrica_de_sesiones, nuevo_local())

    with pytest.raises(SlugEnUso, match="la-esquina"):
        await agregar(fabrica_de_sesiones, nuevo_local())


async def test_guardar_con_el_slug_de_otro_local_falla(fabrica_de_sesiones: Fabrica) -> None:
    await agregar(fabrica_de_sesiones, nuevo_local())
    otro = nuevo_local("el-rincon")
    await agregar(fabrica_de_sesiones, otro)
    otro.cambiar_slug(Slug("la-esquina"))

    with pytest.raises(SlugEnUso):
        await guardar(fabrica_de_sesiones, otro)


async def test_obtener_local_inexistente_falla(fabrica_de_sesiones: Fabrica) -> None:
    with pytest.raises(LocalNoEncontrado):
        await obtener(fabrica_de_sesiones, LocalId.generar())


async def test_directorio_resuelve_el_slug_sin_local_fijado(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelDirectorioSQLAlchemy(fabrica_de_sesiones) as unidad:
        encontrado = await unidad.directorio.obtener_local_id_por_slug(Slug("la-esquina"))
        with pytest.raises(LocalNoEncontrado, match="no-existe"):
            await unidad.directorio.obtener_local_id_por_slug(Slug("no-existe"))

    assert encontrado == local.id


async def test_cierre_por_jornada_se_guarda_con_su_jornada(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    local.cerrar_por_hoy(AHORA)
    await agregar(fabrica_de_sesiones, local)

    leido = await obtener(fabrica_de_sesiones, local.id)

    assert leido.cierre_manual == CierrePorJornada(date(2026, 11, 6))


async def test_guardar_sin_cambiar_el_horario_no_reescribe_las_franjas(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    local.reemplazar_horario(
        Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(12), time(15)),)), AHORA
    )
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelLocalSQLAlchemy(fabrica_de_sesiones, local.id) as unidad:
        antes = (await unidad.sesion.scalars(LEER_IDS_DE_FRANJAS)).all()
        leido = await unidad.locales.obtener()
        leido.suspender()
        await unidad.locales.guardar(leido)
        despues = (await unidad.sesion.scalars(LEER_IDS_DE_FRANJAS)).all()

    assert antes == despues
    assert len(antes) == 1
