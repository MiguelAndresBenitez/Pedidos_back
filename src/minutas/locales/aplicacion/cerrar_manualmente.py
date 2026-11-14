"""Caso de uso del admin: cerrar el local por hoy o hasta nuevo aviso."""

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class TipoDeCierre(StrEnum):
    POR_HOY = "por_hoy"
    HASTA_NUEVO_AVISO = "hasta_nuevo_aviso"


def _cerrar_por_hoy(local: Local, ahora: datetime) -> None:
    local.cerrar_por_hoy(ahora)


def _cerrar_hasta_nuevo_aviso(local: Local, _ahora: datetime) -> None:
    local.cerrar_hasta_nuevo_aviso()


CIERRES_POR_TIPO: dict[TipoDeCierre, Callable[[Local, datetime], None]] = {
    TipoDeCierre.POR_HOY: _cerrar_por_hoy,
    TipoDeCierre.HASTA_NUEVO_AVISO: _cerrar_hasta_nuevo_aviso,
}


class CerrarManualmente:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, tipo: TipoDeCierre, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: CIERRES_POR_TIPO[tipo](local, ahora)
        )
