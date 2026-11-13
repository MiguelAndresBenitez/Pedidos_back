from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

import pytest

from minutas.locales.dominio.cierre_manual import CierreHastaNuevoAviso, CierrePorJornada, SinCierre
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import (
    DatoDelLocalInvalido,
    FranjaCortaLaHoraDeCorte,
    LocalSuspendido,
)
from minutas.locales.dominio.estado_del_local import Activo, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.jornada import JornadaConCambioPendiente, JornadaFija
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria

# Viernes 6/11/2026 a las 21:00 en Buenos Aires (UTC-3).
VIERNES_21 = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
NOCHES = Horario(tuple(FranjaHoraria(dia, time(19), time(1)) for dia in DiaDeLaSemana))
LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


@pytest.fixture
def local() -> Local:
    local = crear_local(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )
    local.reemplazar_horario(NOCHES, VIERNES_21)
    return local


def test_crear_local_usa_los_valores_por_defecto() -> None:
    local = crear_local(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )

    assert local.id.valor.version == 7
    assert local.version == 0
    assert local.estado == Activo()
    assert local.cierre_manual == SinCierre()
    assert local.horario == Horario.vacio()
    assert local.jornada == JornadaFija(ReglasDeJornada.por_defecto())
    assert local.datos.color.hexadecimal == "#000000"
    assert local.imagenes == {}


@pytest.mark.parametrize("nombre", ["", " La Esquina", "x" * 81])
def test_crear_local_con_nombre_invalido_falla(nombre: str) -> None:
    with pytest.raises(DatoDelLocalInvalido, match="nombre"):
        crear_local(
            Slug("la-esquina"), nombre, Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
        )


def test_crear_local_sin_modalidades_falla() -> None:
    with pytest.raises(DatoDelLocalInvalido, match="delivery, retiro o ambos"):
        crear_local(Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset())


@pytest.mark.parametrize(
    ("horas_despues", "abierto"), [(-3, False), (0, True), (3, True), (4, False)]
)
def test_esta_abierto_sigue_el_horario_en_la_hora_local(
    local: Local, horas_despues: int, abierto: bool
) -> None:
    assert local.esta_abierto(VIERNES_21 + timedelta(hours=horas_despues)) is abierto


def test_cerrar_por_hoy_cierra_hasta_la_proxima_jornada(local: Local) -> None:
    local.cerrar_por_hoy(VIERNES_21)

    assert local.cierre_manual == CierrePorJornada(local.jornada_de(VIERNES_21))
    assert not local.esta_abierto(VIERNES_21 + timedelta(hours=3))
    assert local.esta_abierto(VIERNES_21 + timedelta(days=1))


def test_cerrar_hasta_nuevo_aviso_cierra_hasta_reabrir(local: Local) -> None:
    local.cerrar_hasta_nuevo_aviso()

    assert local.cierre_manual == CierreHastaNuevoAviso()
    assert not local.esta_abierto(VIERNES_21 + timedelta(days=7))

    local.reabrir()

    assert local.esta_abierto(VIERNES_21)


def test_suspender_cierra_y_reactivar_reabre(local: Local) -> None:
    local.suspender()

    assert local.estado == Suspendido()
    assert not local.esta_abierto(VIERNES_21)

    local.reactivar()

    assert local.esta_abierto(VIERNES_21)


def test_reemplazar_horario_que_corta_la_hora_de_corte_falla(local: Local) -> None:
    horario = Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(20), time(8)),))

    with pytest.raises(FranjaCortaLaHoraDeCorte):
        local.reemplazar_horario(horario, VIERNES_21)

    assert local.horario == NOCHES


def test_cambiar_hora_de_corte_rige_desde_la_proxima_jornada(local: Local) -> None:
    desde = local.cambiar_hora_de_corte(time(2), VIERNES_21)

    assert desde == local.jornada_de(VIERNES_21) + timedelta(days=1)

    assert local.jornada == JornadaConCambioPendiente(
        ReglasDeJornada.por_defecto(),
        ReglasDeJornada.por_defecto().con_corte(time(2)),
        local.jornada_de(VIERNES_21) + timedelta(days=1),
    )


def test_cambiar_hora_de_corte_que_cortaria_una_franja_falla(local: Local) -> None:
    with pytest.raises(FranjaCortaLaHoraDeCorte, match="00:30"):
        local.cambiar_hora_de_corte(time(0, 30), VIERNES_21)

    assert local.jornada == JornadaFija(ReglasDeJornada.por_defecto())


def test_cambiar_zona_horaria_queda_pendiente_y_funciona_suspendido(local: Local) -> None:
    local.suspender()

    local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), VIERNES_21)

    assert local.jornada.reglas_destino.zona == ZonaHoraria("America/Santiago")


def test_cambiar_imagen_no_devuelve_la_anterior(local: Local) -> None:
    local.cambiar_imagen(TipoDeImagen.LOGO, LOGO)

    assert local.imagenes == {TipoDeImagen.LOGO: LOGO}


@pytest.mark.parametrize(
    "modificar",
    [
        lambda local: local.actualizar_datos(replace(local.datos, nombre="Otro")),
        lambda local: local.reemplazar_horario(Horario.vacio(), VIERNES_21),
        lambda local: local.cambiar_hora_de_corte(time(5), VIERNES_21),
        lambda local: local.cerrar_por_hoy(VIERNES_21),
        lambda local: local.cerrar_hasta_nuevo_aviso(),
        lambda local: local.reabrir(),
        lambda local: local.cambiar_imagen(TipoDeImagen.PORTADA, LOGO),
    ],
)
def test_modificar_desde_el_panel_un_local_suspendido_falla(
    local: Local, modificar: Callable[[Local], object]
) -> None:
    local.suspender()

    with pytest.raises(LocalSuspendido):
        modificar(local)


def test_cambiar_slug_funciona_con_el_local_suspendido(local: Local) -> None:
    local.suspender()

    local.cambiar_slug(Slug("esquina-nueva"))

    assert local.slug == Slug("esquina-nueva")


def test_registrar_guardado_avanza_la_version(local: Local) -> None:
    version = local.version

    local.registrar_guardado()

    assert local.version == version + 1


def test_zona_horaria_en_devuelve_la_que_rige_en_ese_instante(local: Local) -> None:
    desde = local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), VIERNES_21)

    assert local.zona_horaria_en(VIERNES_21) == ZonaHoraria("America/Argentina/Buenos_Aires")
    assert local.zona_horaria_en(VIERNES_21 + timedelta(days=2)) == ZonaHoraria("America/Santiago")
    assert desde == local.jornada_de(VIERNES_21) + timedelta(days=1)
