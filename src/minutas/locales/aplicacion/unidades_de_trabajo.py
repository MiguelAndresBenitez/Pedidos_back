"""Unidades de trabajo del contexto Locales: la del local (con RLS) y la del directorio."""

from collections.abc import Callable
from typing import Protocol

from minutas.compartido.aplicacion.unidad_de_trabajo import (
    UnidadDeTrabajo,
    UnidadDeTrabajoDePlataforma,
)
from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.directorio_de_locales import DirectorioDeLocales
from minutas.locales.aplicacion.repositorio_de_locales import RepositorioDeLocales


class UnidadDeTrabajoDelLocal(UnidadDeTrabajo, Protocol):
    """Fija `app.local_id`: toda escritura del local pasa por acá."""

    @property
    def locales(self) -> RepositorioDeLocales: ...


class UnidadDeTrabajoDelDirectorio(UnidadDeTrabajoDePlataforma, Protocol):
    """Sin local fijado: solo resuelve slugs, de solo lectura."""

    @property
    def directorio(self) -> DirectorioDeLocales: ...


type FabricaDeUnidadesDelLocal = Callable[[LocalId], UnidadDeTrabajoDelLocal]
type FabricaDeUnidadesDelDirectorio = Callable[[], UnidadDeTrabajoDelDirectorio]
