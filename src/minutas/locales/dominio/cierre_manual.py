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
