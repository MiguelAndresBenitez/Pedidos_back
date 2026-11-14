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
