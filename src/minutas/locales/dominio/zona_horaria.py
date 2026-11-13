"""Zona horaria IANA del local: define su hora local para horarios y jornada."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from minutas.locales.dominio.errores import ZonaHorariaInvalida


@dataclass(frozen=True, slots=True)
class ZonaHoraria:
    nombre: str

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.nombre)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ZonaHorariaInvalida(f"'{self.nombre}' no es una zona horaria válida") from error

    @property
    def info(self) -> ZoneInfo:
        return ZoneInfo(self.nombre)


ZONA_HORARIA_POR_DEFECTO = ZonaHoraria("America/Argentina/Buenos_Aires")
