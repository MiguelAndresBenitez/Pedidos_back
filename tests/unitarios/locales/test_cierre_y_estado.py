from datetime import date

import pytest

from minutas.locales.dominio.cierre_manual import CierreHastaNuevoAviso, CierrePorJornada, SinCierre
from minutas.locales.dominio.errores import LocalSuspendido
from minutas.locales.dominio.estado_del_local import Activo, Suspendido

VIERNES, SABADO = date(2026, 11, 6), date(2026, 11, 7)


def test_sin_cierre_permite_abrir_siempre() -> None:
    assert SinCierre().permite_abrir(VIERNES)


def test_cierre_por_jornada_vale_solo_en_su_jornada() -> None:
    cierre = CierrePorJornada(VIERNES)

    assert not cierre.permite_abrir(VIERNES)
    assert cierre.permite_abrir(SABADO)


def test_cierre_hasta_nuevo_aviso_no_permite_abrir_nunca() -> None:
    assert not CierreHastaNuevoAviso().permite_abrir(SABADO)


def test_activo_permite_abrir_y_modificar() -> None:
    Activo().asegurar_modificable()

    assert Activo().permite_abrir()


def test_suspendido_no_permite_abrir_ni_modificar() -> None:
    assert not Suspendido().permite_abrir()
    with pytest.raises(LocalSuspendido, match="suspendida"):
        Suspendido().asegurar_modificable()
