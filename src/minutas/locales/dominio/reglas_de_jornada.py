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
