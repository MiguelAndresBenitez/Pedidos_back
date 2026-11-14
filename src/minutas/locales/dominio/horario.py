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
