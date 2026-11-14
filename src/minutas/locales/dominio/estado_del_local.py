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
