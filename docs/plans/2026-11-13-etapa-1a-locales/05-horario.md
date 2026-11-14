# Tarea 5: Momento de la semana, franjas y horario

**Archivos:**
- Crear: `src/minutas/locales/dominio/dia_de_la_semana.py`
- Crear: `src/minutas/locales/dominio/momento_de_la_semana.py`
- Crear: `src/minutas/locales/dominio/franja_horaria.py`
- Crear: `src/minutas/locales/dominio/horario.py`
- Test: `tests/unitarios/locales/test_horario.py`

---

## Decisiones de diseño

**¿Por qué contar en minutos de la semana?**
- Con aritmética circular (`% 10080`) una franja que cruza la medianoche, o del domingo al lunes, no necesita casos especiales. `minutos_desde` mide cuánto falta hacia adelante dando la vuelta a la semana.

**¿Cómo responde cada operación?**
- `contiene`: el momento cae entre la apertura (incluida) y el cierre (excluido).
- `se_superpone_con`: una franja contiene el inicio de la otra.
- `corta`: el momento cae estrictamente adentro; empezar o terminar justo en la hora de corte está permitido.

**¿Por qué `aperturas` en `Horario`?**
- Lista los inicios de franja en hora local para una ventana de días. La usa la próxima apertura (tarea 10), que los pasa a UTC con la zona que rija.

**¿Por qué la base no controla la superposición?**
- Decisión del diseño: la única forma de escribir franjas es el agregado, que valida el `Horario` entero al construirlo.

**Días de 0 a 6**, como `date.weekday()` y como la columna `dia` de `franjas_horarias`.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_horario.py`:

```python
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
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_horario.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.dia_de_la_semana'`

## Paso 3: Implementación

`src/minutas/locales/dominio/dia_de_la_semana.py`:

```python
"""Días de la semana con la numeración de Python (`date.weekday()`): lunes = 0, domingo = 6."""

from enum import IntEnum


class DiaDeLaSemana(IntEnum):
    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6
```

`src/minutas/locales/dominio/momento_de_la_semana.py`:

```python
"""Momento de la semana: día y hora, sin fecha, contado en minutos desde el lunes 00:00."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Self

from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.zona_horaria import ZonaHoraria

MINUTOS_POR_DIA = 24 * 60
MINUTOS_POR_SEMANA = 7 * MINUTOS_POR_DIA


@dataclass(frozen=True, slots=True, order=True)
class MomentoDeLaSemana:
    minuto: int

    def __post_init__(self) -> None:
        # Invariante interno: el minuto lo calcula el propio dominio, nunca lo escribe una persona.
        if not 0 <= self.minuto < MINUTOS_POR_SEMANA:
            raise ValueError(f"{self.minuto} no es un minuto de la semana (0 a 10079)")

    @classmethod
    def desde_dia_y_hora(cls, dia: DiaDeLaSemana, hora: time) -> Self:
        return cls(dia * MINUTOS_POR_DIA + hora.hour * 60 + hora.minute)

    @classmethod
    def desde_instante(cls, instante: datetime, zona_horaria: ZonaHoraria) -> Self:
        """El instante pasado a la hora local; los segundos se descartan."""
        local = instante.astimezone(zona_horaria.info)
        return cls.desde_dia_y_hora(DiaDeLaSemana(local.weekday()), local.time())

    def minutos_desde(self, otro: "MomentoDeLaSemana") -> int:
        """Cuántos minutos van de `otro` a este, hacia adelante y dando la vuelta a la semana."""
        return (self.minuto - otro.minuto) % MINUTOS_POR_SEMANA
```

`src/minutas/locales/dominio/franja_horaria.py`:

```python
"""Franja horaria: un tramo de atención que empieza un día y puede cruzar la medianoche."""

from dataclasses import dataclass
from datetime import time

from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import FranjaAmbigua
from minutas.locales.dominio.momento_de_la_semana import MINUTOS_POR_DIA, MomentoDeLaSemana


@dataclass(frozen=True, slots=True)
class FranjaHoraria:
    """Incluye la apertura y excluye el cierre. Si cierra antes de abrir, cruza la medianoche."""

    dia: DiaDeLaSemana
    apertura: time
    cierre: time

    def __post_init__(self) -> None:
        if any(hora.second or hora.microsecond for hora in (self.apertura, self.cierre)):
            raise FranjaAmbigua("Las horas de una franja van en minutos exactos")
        if self.apertura == self.cierre:
            raise FranjaAmbigua("Una franja no puede abrir y cerrar a la misma hora")

    @property
    def inicio(self) -> MomentoDeLaSemana:
        return MomentoDeLaSemana.desde_dia_y_hora(self.dia, self.apertura)

    @property
    def duracion(self) -> int:
        """Minutos que dura; una franja que cruza la medianoche dura menos de un día igual."""
        apertura = self.apertura.hour * 60 + self.apertura.minute
        cierre = self.cierre.hour * 60 + self.cierre.minute
        return (cierre - apertura) % MINUTOS_POR_DIA

    def contiene(self, momento: MomentoDeLaSemana) -> bool:
        return momento.minutos_desde(self.inicio) < self.duracion

    def se_superpone_con(self, otra: "FranjaHoraria") -> bool:
        """Dos franjas se superponen si una contiene el inicio de la otra."""
        return self.contiene(otra.inicio) or otra.contiene(self.inicio)

    def corta(self, momento: MomentoDeLaSemana) -> bool:
        """El momento cae estrictamente adentro: empezar o terminar justo ahí no corta."""
        return 0 < momento.minutos_desde(self.inicio) < self.duracion
```

`src/minutas/locales/dominio/horario.py`:

```python
"""Horario: la semana de franjas de un local, sin superposiciones."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import combinations
from typing import Self

from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import FranjaCortaLaHoraDeCorte, HorariosSuperpuestos
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.momento_de_la_semana import MomentoDeLaSemana


@dataclass(frozen=True, slots=True)
class Horario:
    franjas: tuple[FranjaHoraria, ...] = ()

    def __post_init__(self) -> None:
        if any(una.se_superpone_con(otra) for una, otra in combinations(self.franjas, 2)):
            raise HorariosSuperpuestos("Hay franjas que se superponen")

    @classmethod
    def vacio(cls) -> Self:
        """Sin franjas: el local está cerrado hasta que cargue sus horarios."""
        return cls()

    def contiene(self, momento: MomentoDeLaSemana) -> bool:
        return any(franja.contiene(momento) for franja in self.franjas)

    def asegurar_respeta_corte(self, hora_de_corte: time) -> None:
        """Ninguna franja puede cortar una de las siete horas de corte de la semana."""
        cortes = [MomentoDeLaSemana.desde_dia_y_hora(dia, hora_de_corte) for dia in DiaDeLaSemana]
        if any(franja.corta(corte) for franja in self.franjas for corte in cortes):
            raise FranjaCortaLaHoraDeCorte(
                f"Hay franjas que pasan por la hora de corte ({hora_de_corte:%H:%M}): "
                "una jornada no puede meterse en la siguiente"
            )

    def aperturas(self, desde: date, dias: int) -> Iterator[datetime]:
        """Aperturas en hora local (sin zona) de los `dias` días que empiezan en `desde`."""
        for numero in range(dias):
            fecha = desde + timedelta(days=numero)
            for franja in self.franjas:
                if franja.dia == fecha.weekday():
                    yield datetime.combine(fecha, franja.apertura)
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_horario.py -v && uv run mypy`
Expected: PASS (22 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/dia_de_la_semana.py src/minutas/locales/dominio/momento_de_la_semana.py src/minutas/locales/dominio/franja_horaria.py src/minutas/locales/dominio/horario.py tests/unitarios/locales/test_horario.py
git commit -m "feat(locales): franjas horarias y horario semanal" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
