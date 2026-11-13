from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest

from minutas.locales.aplicacion.actualizar_datos_del_local import ActualizarDatosDelLocal
from minutas.locales.aplicacion.cambiar_hora_de_corte import CambiarHoraDeCorte
from minutas.locales.aplicacion.cerrar_manualmente import CerrarManualmente, TipoDeCierre
from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.aplicacion.obtener_local_del_panel import ObtenerLocalDelPanel
from minutas.locales.aplicacion.reabrir import Reabrir
from minutas.locales.aplicacion.reemplazar_horario import ReemplazarHorario
from minutas.locales.aplicacion.subir_imagen_del_local import SubirImagenDelLocal
from minutas.locales.dominio.cierre_manual import CierreHastaNuevoAviso, CierrePorJornada, SinCierre
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import FranjaCortaLaHoraDeCorte, LocalSuspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from soporte.imagenes_en_memoria import AlmacenDeImagenesEnMemoria, ProcesadorDeImagenesFalso
from soporte.locales_en_memoria import BaseDeLocalesEnMemoria

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
AHORA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def base() -> BaseDeLocalesEnMemoria:
    return BaseDeLocalesEnMemoria()


@pytest.fixture
async def local(base: BaseDeLocalesEnMemoria) -> Local:
    return await DarDeAltaLocal(base.crear_unidad_del_local).ejecutar(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )


async def test_actualizar_datos_guarda_e_incrementa_la_version(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    datos = replace(local.datos, nombre="La Esquina de Ana")

    await ActualizarDatosDelLocal(base.crear_unidad_del_local).ejecutar(local.id, datos)

    assert base.locales[local.id].datos == datos
    assert base.locales[local.id].version == 1


async def test_reemplazar_horario_invalido_no_guarda_nada(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    horario = Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(20), time(9)),))

    with pytest.raises(FranjaCortaLaHoraDeCorte):
        await ReemplazarHorario(base.crear_unidad_del_local).ejecutar(local.id, horario, AHORA)

    assert base.locales[local.id].horario == Horario.vacio()


async def test_cambiar_hora_de_corte_queda_pendiente(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    await CambiarHoraDeCorte(base.crear_unidad_del_local).ejecutar(local.id, time(5), AHORA)

    assert base.locales[local.id].jornada.cortes() == (time(6), time(5))


@pytest.mark.parametrize(
    ("tipo", "cierre"),
    [
        (TipoDeCierre.POR_HOY, CierrePorJornada(date(2026, 11, 6))),
        (TipoDeCierre.HASTA_NUEVO_AVISO, CierreHastaNuevoAviso()),
    ],
)
async def test_cerrar_manualmente_y_reabrir(
    base: BaseDeLocalesEnMemoria,
    local: Local,
    tipo: TipoDeCierre,
    cierre: CierrePorJornada | CierreHastaNuevoAviso,
) -> None:
    await CerrarManualmente(base.crear_unidad_del_local).ejecutar(local.id, tipo, AHORA)
    assert base.locales[local.id].cierre_manual == cierre

    await Reabrir(base.crear_unidad_del_local).ejecutar(local.id)
    assert base.locales[local.id].cierre_manual == SinCierre()


async def test_subir_imagen_la_procesa_con_las_medidas_del_tipo_y_la_guarda(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    almacen = AlmacenDeImagenesEnMemoria()
    subir = SubirImagenDelLocal(base.crear_unidad_del_local, ProcesadorDeImagenesFalso(), almacen)

    nombre = await subir.ejecutar(local.id, TipoDeImagen.LOGO, b"foto")

    assert almacen.imagenes == {nombre: b"webp 512x512:foto"}
    assert base.locales[local.id].imagenes == {TipoDeImagen.LOGO: nombre}


async def test_subir_imagen_a_un_local_suspendido_falla_sin_guardar_el_archivo(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    base.locales[local.id].suspender()
    almacen = AlmacenDeImagenesEnMemoria()
    subir = SubirImagenDelLocal(base.crear_unidad_del_local, ProcesadorDeImagenesFalso(), almacen)

    with pytest.raises(LocalSuspendido):
        await subir.ejecutar(local.id, TipoDeImagen.PORTADA, b"foto")

    assert almacen.imagenes == {}


async def test_obtener_local_del_panel_devuelve_el_local(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    leido = await ObtenerLocalDelPanel(base.crear_unidad_del_local).ejecutar(local.id)

    assert leido.slug == local.slug
