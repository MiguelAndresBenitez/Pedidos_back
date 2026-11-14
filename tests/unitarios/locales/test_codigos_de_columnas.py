"""Las tablas de códigos del repositorio cubren todas las variantes del dominio, ida y vuelta.

Si se suma una variante a `EstadoDelLocal` o `CierreManual` y no se le da su código,
estos tests fallan acá y no con un `KeyError` en producción.
"""

from datetime import date
from typing import get_args

import pytest

from minutas.locales.dominio.cierre_manual import (
    CierreHastaNuevoAviso,
    CierreManual,
    CierrePorJornada,
    SinCierre,
)
from minutas.locales.dominio.estado_del_local import EstadoDelLocal
from minutas.locales.infraestructura.repositorio_de_locales_sqlalchemy import (
    CIERRES,
    CODIGOS_DE_CIERRE,
    CODIGOS_DE_ESTADO,
    ESTADOS,
)

VARIANTES_DE_ESTADO = get_args(EstadoDelLocal.__value__)
VARIANTES_DE_CIERRE = get_args(CierreManual.__value__)
JORNADA = date(2026, 11, 6)


@pytest.mark.parametrize("variante", VARIANTES_DE_ESTADO)
def test_cada_estado_se_guarda_y_se_lee_igual(variante: type[EstadoDelLocal]) -> None:
    estado = variante()

    assert ESTADOS[CODIGOS_DE_ESTADO[type(estado)]]() == estado


# Un ejemplo por variante, con la jornada que se guarda en `cierre_manual_jornada`.
EJEMPLOS_DE_CIERRE: list[tuple[CierreManual, date | None]] = [
    (SinCierre(), None),
    (CierrePorJornada(JORNADA), JORNADA),
    (CierreHastaNuevoAviso(), None),
]


def test_hay_un_ejemplo_de_cierre_por_cada_variante() -> None:
    assert {type(cierre) for cierre, _ in EJEMPLOS_DE_CIERRE} == set(VARIANTES_DE_CIERRE)


@pytest.mark.parametrize(("cierre", "jornada"), EJEMPLOS_DE_CIERRE)
def test_cada_cierre_se_guarda_y_se_lee_igual(cierre: CierreManual, jornada: date | None) -> None:
    assert CIERRES[CODIGOS_DE_CIERRE[type(cierre)]](jornada) == cierre


def test_los_codigos_de_estado_no_se_repiten() -> None:
    assert len(set(CODIGOS_DE_ESTADO.values())) == len(VARIANTES_DE_ESTADO)


def test_los_codigos_de_cierre_no_se_repiten() -> None:
    assert len(set(CODIGOS_DE_CIERRE.values())) == len(VARIANTES_DE_CIERRE)
