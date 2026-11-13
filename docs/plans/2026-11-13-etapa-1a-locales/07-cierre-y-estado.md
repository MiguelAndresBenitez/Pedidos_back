# Tarea 7: Cierre manual y estado del local

**Archivos:**
- Crear: `src/minutas/locales/dominio/cierre_manual.py`
- Crear: `src/minutas/locales/dominio/estado_del_local.py`
- Test: `tests/unitarios/locales/test_cierre_y_estado.py`

---

## Decisiones de diseño

**¿Por qué clases y no un campo con valores?**
- Cada variante responde lo suyo: `permite_abrir` en el cierre y en el estado, `asegurar_modificable` en el estado. El agregado las llama sin preguntar cuál es (convención de polimorfismo por variantes).
- `SinCierre` es un objeto nulo: el agregado nunca tiene `None` como cierre.

**¿Dónde están los valores de las columnas (`"activo"`, `"por_jornada"`)?**
- En la infraestructura (tarea 14), en tablas de despacho por tipo en los dos sentidos. El dominio no conoce el vocabulario de la base.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_cierre_y_estado.py`:

```python
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
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_cierre_y_estado.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.cierre_manual'`

## Paso 3: Implementación

`src/minutas/locales/dominio/cierre_manual.py`:

```python
"""Cierre manual del local: sin cierre, por la jornada actual o hasta nuevo aviso."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class SinCierre:
    def permite_abrir(self, jornada: date) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class CierrePorJornada:
    """ "Cerrar por hoy": vale mientras dure la jornada guardada y deja de valer solo."""

    jornada: date

    def permite_abrir(self, jornada: date) -> bool:
        return jornada != self.jornada


@dataclass(frozen=True, slots=True)
class CierreHastaNuevoAviso:
    def permite_abrir(self, jornada: date) -> bool:
        return False


type CierreManual = SinCierre | CierrePorJornada | CierreHastaNuevoAviso
```

`src/minutas/locales/dominio/estado_del_local.py`:

```python
"""Estado comercial del local: el owner lo suspende cuando el abono no entra."""

from dataclasses import dataclass

from minutas.locales.dominio.errores import LocalSuspendido


@dataclass(frozen=True, slots=True)
class Activo:
    def permite_abrir(self) -> bool:
        return True

    def asegurar_modificable(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class Suspendido:
    def permite_abrir(self) -> bool:
        return False

    def asegurar_modificable(self) -> None:
        raise LocalSuspendido("La cuenta del local está suspendida; contactate con Minutas")


type EstadoDelLocal = Activo | Suspendido
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_cierre_y_estado.py -v && uv run mypy`
Expected: PASS (5 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/cierre_manual.py src/minutas/locales/dominio/estado_del_local.py tests/unitarios/locales/test_cierre_y_estado.py
git commit -m "feat(locales): cierre manual y estado del local" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
