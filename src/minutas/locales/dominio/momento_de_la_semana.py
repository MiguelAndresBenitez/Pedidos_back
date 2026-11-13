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
