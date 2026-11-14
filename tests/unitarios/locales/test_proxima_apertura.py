from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta

import pytest

from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp

# Viernes 6/11/2026; Buenos Aires está en UTC-3.
VIERNES_10 = datetime(2026, 11, 6, 13, 0, tzinfo=UTC)
VIERNES_20 = datetime(2026, 11, 6, 23, 0, tzinfo=UTC)
SABADO_20 = datetime(2026, 11, 7, 23, 0, tzinfo=UTC)
LUNES_12 = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)


@pytest.fixture
def local() -> Local:
    local = crear_local(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )
    horario = Horario(
        (
            FranjaHoraria(DiaDeLaSemana.VIERNES, time(20), time(1)),
            FranjaHoraria(DiaDeLaSemana.SABADO, time(20), time(1)),
            FranjaHoraria(DiaDeLaSemana.LUNES, time(12), time(15)),
        )
    )
    local.reemplazar_horario(horario, VIERNES_10)
    return local


def test_proxima_apertura_cerrado_es_el_proximo_inicio_de_franja(local: Local) -> None:
    assert local.proxima_apertura(VIERNES_10) == VIERNES_20


def test_proxima_apertura_abierto_ahora_es_none(local: Local) -> None:
    assert local.proxima_apertura(VIERNES_20 + timedelta(hours=1)) is None


def test_proxima_apertura_cerrado_por_hoy_saltea_la_jornada_cerrada(local: Local) -> None:
    local.cerrar_por_hoy(VIERNES_10)

    assert local.proxima_apertura(VIERNES_10) == SABADO_20


def test_proxima_apertura_da_la_vuelta_a_la_semana(local: Local) -> None:
    domingo = datetime(2026, 11, 8, 15, 0, tzinfo=UTC)

    assert local.proxima_apertura(domingo) == LUNES_12


@pytest.mark.parametrize("cerrar", [Local.cerrar_hasta_nuevo_aviso, Local.suspender])
def test_proxima_apertura_sin_apertura_posible_es_none(
    local: Local, cerrar: Callable[[Local], None]
) -> None:
    cerrar(local)

    assert local.proxima_apertura(VIERNES_10) is None


def test_proxima_apertura_sin_horario_es_none() -> None:
    local = crear_local(
        Slug("vacio"), "Vacío", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )

    assert local.proxima_apertura(VIERNES_10) is None
