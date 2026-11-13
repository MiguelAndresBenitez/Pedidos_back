from datetime import UTC, date, datetime, time

import pytest

from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import (
    FranjaAmbigua,
    FranjaCortaLaHoraDeCorte,
    HorariosSuperpuestos,
)
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.momento_de_la_semana import MomentoDeLaSemana
from minutas.locales.dominio.zona_horaria import ZonaHoraria

LUNES, MARTES, DOMINGO = DiaDeLaSemana.LUNES, DiaDeLaSemana.MARTES, DiaDeLaSemana.DOMINGO


def momento(dia: DiaDeLaSemana, hora: int, minuto: int = 0) -> MomentoDeLaSemana:
    return MomentoDeLaSemana.desde_dia_y_hora(dia, time(hora, minuto))


def test_momento_desde_instante_usa_la_hora_local() -> None:
    # Lunes 2/11/2026 a las 02:30 UTC son las 23:30 del domingo en Buenos Aires.
    instante = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)

    resultado = MomentoDeLaSemana.desde_instante(
        instante, ZonaHoraria("America/Argentina/Buenos_Aires")
    )

    assert resultado == momento(DOMINGO, 23, 30)


def test_momento_minutos_desde_da_la_vuelta_a_la_semana() -> None:
    assert momento(LUNES, 1).minutos_desde(momento(DOMINGO, 23)) == 120


@pytest.mark.parametrize("cierre", [time(20, 0), time(20, 0, 30)])
def test_crear_franja_ambigua_falla(cierre: time) -> None:
    with pytest.raises(FranjaAmbigua):
        FranjaHoraria(LUNES, time(20, 0), cierre)


@pytest.mark.parametrize(
    ("instante", "contiene"),
    [
        (momento(MARTES, 19, 59), False),
        (momento(MARTES, 20, 0), True),  # incluye la apertura
        (momento(MIERCOLES := DiaDeLaSemana.MIERCOLES, 0, 29), True),
        (momento(MIERCOLES, 0, 30), False),  # excluye el cierre
    ],
)
def test_franja_que_cruza_la_medianoche_contiene_el_tramo_del_dia_siguiente(
    instante: MomentoDeLaSemana, contiene: bool
) -> None:
    assert FranjaHoraria(MARTES, time(20, 0), time(0, 30)).contiene(instante) is contiene


def test_franja_del_domingo_que_cruza_al_lunes_contiene_el_lunes_temprano() -> None:
    franja = FranjaHoraria(DOMINGO, time(22, 0), time(2, 0))

    assert franja.contiene(momento(LUNES, 1, 59))
    assert not franja.contiene(momento(LUNES, 2, 0))


@pytest.mark.parametrize(
    ("una", "otra", "se_superponen"),
    [
        ((LUNES, 12, 16), (LUNES, 15, 18), True),
        ((LUNES, 12, 15), (LUNES, 15, 18), False),  # se tocan en el borde
        ((LUNES, 20, 2), (MARTES, 1, 3), True),  # cruza la medianoche
        ((DOMINGO, 22, 2), (LUNES, 1, 4), True),  # cruza de domingo a lunes
        ((LUNES, 10, 22), (LUNES, 12, 13), True),  # una dentro de la otra
    ],
)
def test_franjas_se_superponen_cubre_medianoche_y_fin_de_semana(
    una: tuple[DiaDeLaSemana, int, int], otra: tuple[DiaDeLaSemana, int, int], se_superponen: bool
) -> None:
    primera = FranjaHoraria(una[0], time(una[1]), time(una[2]))
    segunda = FranjaHoraria(otra[0], time(otra[1]), time(otra[2]))

    assert primera.se_superpone_con(segunda) is se_superponen
    assert segunda.se_superpone_con(primera) is se_superponen


def test_crear_horario_con_franjas_superpuestas_falla() -> None:
    with pytest.raises(HorariosSuperpuestos):
        Horario(
            (FranjaHoraria(LUNES, time(12), time(16)), FranjaHoraria(LUNES, time(15), time(18)))
        )


def test_horario_con_varias_franjas_por_dia_contiene_cada_una() -> None:
    horario = Horario(
        (FranjaHoraria(MARTES, time(12), time(15)), FranjaHoraria(MARTES, time(20), time(0, 30)))
    )

    assert horario.contiene(momento(MARTES, 13))
    assert not horario.contiene(momento(MARTES, 17))
    assert horario.contiene(momento(MARTES, 23))


@pytest.mark.parametrize(
    ("apertura", "cierre", "respeta"),
    [
        (time(20), time(6), True),  # termina justo en el corte
        (time(6), time(14), True),  # empieza justo en el corte
        (time(20), time(7), False),  # pasa por las 06:00
        (time(4), time(8), False),  # sin cruzar la medianoche, también corta
    ],
)
def test_asegurar_respeta_corte_rechaza_solo_las_franjas_que_lo_cortan(
    apertura: time, cierre: time, respeta: bool
) -> None:
    horario = Horario((FranjaHoraria(LUNES, apertura, cierre),))

    if respeta:
        horario.asegurar_respeta_corte(time(6))
    else:
        with pytest.raises(FranjaCortaLaHoraDeCorte, match="06:00"):
            horario.asegurar_respeta_corte(time(6))


def test_aperturas_devuelve_los_inicios_de_cada_dia_en_hora_local() -> None:
    horario = Horario(
        (FranjaHoraria(LUNES, time(12), time(15)), FranjaHoraria(MARTES, time(20), time(1)))
    )

    aperturas = list(horario.aperturas(date(2026, 11, 2), 3))

    assert aperturas == [datetime(2026, 11, 2, 12), datetime(2026, 11, 3, 20)]


def test_horario_vacio_no_contiene_nada() -> None:
    assert not Horario.vacio().contiene(momento(LUNES, 12))
