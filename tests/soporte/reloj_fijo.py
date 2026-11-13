"""Reloj de prueba: devuelve siempre el instante que se le fija."""

from datetime import datetime, timedelta


class RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self.instante = instante

    def ahora(self) -> datetime:
        return self.instante

    def avanzar(self, tiempo: timedelta) -> None:
        self.instante += tiempo
