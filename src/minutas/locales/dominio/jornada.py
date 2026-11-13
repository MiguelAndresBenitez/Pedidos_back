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
        return self.reprogramar(nuevas, ahora)

    def reprogramar(self, nuevas: ReglasDeJornada, ahora: datetime) -> "JornadaConCambioPendiente":
        """Sin cambio pendiente, reprogramar es lo mismo que programar."""
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
        return self.consolidar(ahora).reprogramar(nuevas, ahora)

    def reprogramar(self, nuevas: ReglasDeJornada, ahora: datetime) -> "JornadaConCambioPendiente":
        """Reemplaza el cambio pendiente.

        Precondición: la jornada ya está consolidada (el cambio pendiente aún no rige).
        El punto de entrada es `programar`, que consolida antes de reprogramar.
        """
        return JornadaConCambioPendiente(self.vigentes, nuevas, self.desde_jornada)


type Jornada = JornadaFija | JornadaConCambioPendiente
