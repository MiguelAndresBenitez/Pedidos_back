from datetime import UTC, date, datetime, time, timedelta

import pytest

from minutas.locales.dominio.jornada import JornadaConCambioPendiente, JornadaFija
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.zona_horaria import ZonaHoraria

BUENOS_AIRES = ZonaHoraria("America/Argentina/Buenos_Aires")
SANTIAGO = ZonaHoraria("America/Santiago")
SEIS = ReglasDeJornada(BUENOS_AIRES, time(6))


def utc(dia: int, hora: int, minuto: int = 0) -> datetime:
    """Un instante de noviembre de 2026, en UTC."""
    return datetime(2026, 11, dia, hora, minuto, tzinfo=UTC)


@pytest.mark.parametrize(
    ("instante", "jornada"),
    [
        (utc(7, 2), date(2026, 11, 6)),  # viernes 23:00 en Buenos Aires
        (utc(7, 5), date(2026, 11, 6)),  # sábado 02:00, antes del corte
        (utc(7, 8, 59), date(2026, 11, 6)),  # sábado 05:59
        (utc(7, 9), date(2026, 11, 7)),  # sábado 06:00: empieza la del sábado
    ],
)
def test_jornada_de_usa_la_hora_de_corte_en_la_hora_local(
    instante: datetime, jornada: date
) -> None:
    assert JornadaFija(SEIS).jornada_de(instante) == jornada


def test_inicio_de_una_jornada_es_su_fecha_a_la_hora_de_corte() -> None:
    assert SEIS.inicio_de(date(2026, 11, 7)) == utc(7, 9)


def test_programar_desde_reglas_fijas_rige_desde_la_jornada_siguiente() -> None:
    jornada = JornadaFija(SEIS).programar(SEIS.con_corte(time(8)), utc(7, 12))

    assert jornada == JornadaConCambioPendiente(SEIS, SEIS.con_corte(time(8)), date(2026, 11, 8))


def test_correr_el_corte_para_mas_tarde_alarga_la_jornada_de_transicion() -> None:
    # Sábado 09:00 en Buenos Aires: el corte pasa de 06:00 a 08:00 desde el domingo.
    jornada = JornadaFija(SEIS).programar(SEIS.con_corte(time(8)), utc(7, 12))

    assert jornada.jornada_de(utc(8, 8, 59)) == date(2026, 11, 7)  # domingo 05:59
    assert jornada.jornada_de(utc(8, 9)) == date(2026, 11, 8)  # domingo 06:00: no retrocede
    assert jornada.jornada_de(utc(9, 10, 59)) == date(2026, 11, 8)  # lunes 07:59
    assert jornada.jornada_de(utc(9, 11)) == date(2026, 11, 9)  # lunes 08:00


def test_cambiar_a_una_zona_con_menos_horas_no_hace_retroceder_la_jornada() -> None:
    # Sábado 4/7 a las 06:30 en Buenos Aires (UTC-3), el local pasa a Santiago (UTC-4 en julio).
    sabado = datetime(2026, 7, 4, 9, 30, tzinfo=UTC)
    jornada = JornadaFija(SEIS).programar(SEIS.con_zona(SANTIAGO), sabado)
    domingo_06_de_buenos_aires = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)
    lunes_06_de_santiago = datetime(2026, 7, 6, 10, 0, tzinfo=UTC)

    assert jornada.jornada_de(sabado) == date(2026, 7, 4)
    # El domingo empieza a las 06:00 de Buenos Aires (05:00 en Santiago), no retrocede al
    # sábado, y dura 25 h: hasta las 06:00 de Santiago del lunes.
    assert jornada.jornada_de(domingo_06_de_buenos_aires) == date(2026, 7, 5)
    assert jornada.jornada_de(lunes_06_de_santiago - timedelta(minutes=1)) == date(2026, 7, 5)
    assert jornada.jornada_de(lunes_06_de_santiago) == date(2026, 7, 6)
    assert jornada.reglas_en(domingo_06_de_buenos_aires).zona == SANTIAGO


def test_programar_dos_veces_antes_de_que_rija_reemplaza_al_pendiente() -> None:
    primera = JornadaFija(SEIS).programar(SEIS.con_corte(time(8)), utc(7, 12))

    segunda = primera.programar(primera.reglas_destino.con_zona(SANTIAGO), utc(7, 13))

    assert segunda == JornadaConCambioPendiente(
        SEIS, ReglasDeJornada(SANTIAGO, time(8)), date(2026, 11, 8)
    )


def test_consolidar_convierte_en_fija_solo_cuando_el_cambio_ya_rige() -> None:
    pendiente = JornadaFija(SEIS).programar(SEIS.con_corte(time(8)), utc(7, 12))

    assert pendiente.consolidar(utc(8, 8)) is pendiente
    assert pendiente.consolidar(utc(8, 9)) == JornadaFija(SEIS.con_corte(time(8)))


def test_cortes_de_un_cambio_pendiente_incluye_los_dos() -> None:
    pendiente = JornadaConCambioPendiente(SEIS, SEIS.con_corte(time(8)), date(2026, 11, 8))

    assert pendiente.cortes() == (time(6), time(8))
    assert JornadaFija(SEIS).cortes() == (time(6),)
    assert pendiente.transicion == utc(8, 9)


def test_programar_cuando_el_cambio_ya_rige_no_lo_aplica_al_instante() -> None:
    pendiente = JornadaFija(SEIS).programar(SEIS.con_corte(time(8)), utc(7, 12))
    lunes = utc(9, 12)  # el corte de 08:00 rige desde el domingo

    nueva = pendiente.programar(SEIS.con_corte(time(5)), lunes)

    assert nueva == JornadaConCambioPendiente(
        SEIS.con_corte(time(8)), SEIS.con_corte(time(5)), date(2026, 11, 10)
    )
