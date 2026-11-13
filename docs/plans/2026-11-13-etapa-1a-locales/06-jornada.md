# Tarea 6: Reglas de jornada y cambios pendientes

**Archivos:**
- Crear: `src/minutas/locales/dominio/reglas_de_jornada.py`
- Crear: `src/minutas/locales/dominio/jornada.py`
- Test: `tests/unitarios/locales/test_jornada.py`

---

## Decisiones de diseño

**¿Qué son las reglas de jornada?**
- El par zona horaria y hora de corte, que define el día de trabajo: `jornada = fecha de (hora local - hora de corte)`. Cambiar cualquiera de los dos puede hacer retroceder la jornada, así que los dos cambian por el mismo mecanismo.

**¿Cómo funciona un cambio pendiente?**
- Dos variantes con los mismos métodos (polimorfismo, sin `if` por tipo): `JornadaFija(reglas)` y `JornadaConCambioPendiente(vigentes, pendientes, desde_jornada)`.
- `programar` deja las reglas nuevas para la jornada siguiente; un segundo cambio antes de que rija reemplaza al pendiente. Si el pendiente ya rige, `programar` lo consolida primero: el invariante "las reglas nuevas nunca rigen al instante" lo protege la propia variante, no quien la llama.
- Hasta la `transicion` (el inicio de `desde_jornada` según las reglas vigentes) se calcula con las vigentes; desde ahí, con las pendientes y nunca antes de `desde_jornada`. La jornada de transición puede durar más o menos de 24 h.
- `consolidar` convierte el pendiente en fijo cuando ya rige: no hace falta ningún proceso aparte.

**¿Es un condicional prohibido `pendientes if self.ya_rige(ahora) else vigentes`?**
- No: es una expresión que calcula un valor según el instante, no un `if` que elige comportamiento según el tipo. La comparación con la transición vive en un solo método, `ya_rige`.

**`reglas_vigentes`, `reglas_destino` y `cambio_pendiente`** son parte del lenguaje del dominio (qué rige, qué va a regir, desde cuándo): el repositorio (tarea 14) los usa para guardar la variante sin preguntar de qué tipo es.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_jornada.py`:

```python
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
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_jornada.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.jornada'`

## Paso 3: Implementación

`src/minutas/locales/dominio/reglas_de_jornada.py`:

```python
"""Reglas de jornada: la zona horaria y la hora de corte que definen el día de trabajo."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Self

from minutas.locales.dominio.errores import DatoDelLocalInvalido
from minutas.locales.dominio.zona_horaria import ZONA_HORARIA_POR_DEFECTO, ZonaHoraria

HORA_DE_CORTE_POR_DEFECTO = time(6, 0)


@dataclass(frozen=True, slots=True)
class ReglasDeJornada:
    zona: ZonaHoraria
    corte: time

    def __post_init__(self) -> None:
        if self.corte.second or self.corte.microsecond:
            raise DatoDelLocalInvalido("La hora de corte va en minutos exactos")

    @classmethod
    def por_defecto(cls) -> Self:
        return cls(ZONA_HORARIA_POR_DEFECTO, HORA_DE_CORTE_POR_DEFECTO)

    def con_corte(self, corte: time) -> Self:
        return replace(self, corte=corte)

    def con_zona(self, zona: ZonaHoraria) -> Self:
        return replace(self, zona=zona)

    def jornada_de(self, instante: datetime) -> date:
        """jornada = fecha de (hora local - hora de corte): antes del corte es el día anterior."""
        local = instante.astimezone(self.zona.info).replace(tzinfo=None)
        return (local - timedelta(hours=self.corte.hour, minutes=self.corte.minute)).date()

    def inicio_de(self, jornada: date) -> datetime:
        """Instante (UTC) en que empieza una jornada: su fecha a la hora de corte, en hora local."""
        local = datetime.combine(jornada, self.corte, tzinfo=self.zona.info)
        return local.astimezone(UTC)
```

`src/minutas/locales/dominio/jornada.py`:

```python
"""Jornada: el día de trabajo del local. Un cambio de reglas rige desde la próxima jornada."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.zona_horaria import ZonaHoraria


@dataclass(frozen=True, slots=True)
class JornadaFija:
    """Reglas sin cambios pendientes."""

    reglas: ReglasDeJornada

    @property
    def reglas_vigentes(self) -> ReglasDeJornada:
        return self.reglas

    @property
    def reglas_destino(self) -> ReglasDeJornada:
        return self.reglas

    @property
    def cambio_pendiente(self) -> tuple[ReglasDeJornada, date] | None:
        return None

    def cortes(self) -> tuple[time, ...]:
        return (self.reglas.corte,)

    def zonas(self) -> tuple[ZonaHoraria, ...]:
        return (self.reglas.zona,)

    def reglas_en(self, ahora: datetime) -> ReglasDeJornada:
        return self.reglas

    def jornada_de(self, ahora: datetime) -> date:
        return self.reglas.jornada_de(ahora)

    def consolidar(self, ahora: datetime) -> "Jornada":
        return self

    def programar(self, nuevas: ReglasDeJornada, ahora: datetime) -> "JornadaConCambioPendiente":
        """Las reglas nuevas rigen desde la jornada siguiente a la actual."""
        desde = self.jornada_de(ahora) + timedelta(days=1)
        return JornadaConCambioPendiente(self.reglas, nuevas, desde)


@dataclass(frozen=True, slots=True)
class JornadaConCambioPendiente:
    """Reglas vigentes hasta que empieza `desde_jornada`; desde ahí, las pendientes."""

    vigentes: ReglasDeJornada
    pendientes: ReglasDeJornada
    desde_jornada: date

    @property
    def reglas_vigentes(self) -> ReglasDeJornada:
        return self.vigentes

    @property
    def reglas_destino(self) -> ReglasDeJornada:
        return self.pendientes

    @property
    def cambio_pendiente(self) -> tuple[ReglasDeJornada, date] | None:
        return (self.pendientes, self.desde_jornada)

    @property
    def transicion(self) -> datetime:
        """Instante en que empieza `desde_jornada` según las reglas vigentes."""
        return self.vigentes.inicio_de(self.desde_jornada)

    def ya_rige(self, ahora: datetime) -> bool:
        return ahora >= self.transicion

    def cortes(self) -> tuple[time, ...]:
        return (self.vigentes.corte, self.pendientes.corte)

    def zonas(self) -> tuple[ZonaHoraria, ...]:
        return (self.vigentes.zona, self.pendientes.zona)

    def reglas_en(self, ahora: datetime) -> ReglasDeJornada:
        return self.pendientes if self.ya_rige(ahora) else self.vigentes

    def jornada_de(self, ahora: datetime) -> date:
        """Con las reglas que rigen; tras la transición, nunca antes de `desde_jornada`."""
        jornada = self.reglas_en(ahora).jornada_de(ahora)
        return max(jornada, self.desde_jornada) if self.ya_rige(ahora) else jornada

    def consolidar(self, ahora: datetime) -> "Jornada":
        """Si el cambio ya rige, queda como reglas fijas: no hace falta ningún proceso aparte."""
        return JornadaFija(self.pendientes) if self.ya_rige(ahora) else self

    def programar(self, nuevas: ReglasDeJornada, ahora: datetime) -> "JornadaConCambioPendiente":
        """Antes de que rija, un segundo cambio reemplaza al pendiente; no se acumulan.

        Si el cambio ya rige, primero se consolida: las reglas nuevas nunca rigen al instante.
        """
        if self.ya_rige(ahora):
            return JornadaFija(self.pendientes).programar(nuevas, ahora)
        return JornadaConCambioPendiente(self.vigentes, nuevas, self.desde_jornada)


type Jornada = JornadaFija | JornadaConCambioPendiente
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_jornada.py -v && uv run mypy`
Expected: PASS (12 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/reglas_de_jornada.py src/minutas/locales/dominio/jornada.py tests/unitarios/locales/test_jornada.py
git commit -m "feat(locales): jornada con hora de corte y cambios que rigen desde la próxima" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
