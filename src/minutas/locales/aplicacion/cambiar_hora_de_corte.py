"""Caso de uso del admin: cambiar la hora de corte. Rige desde la próxima jornada."""

from datetime import datetime, time

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class CambiarHoraDeCorte:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, corte: time, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.cambiar_hora_de_corte(corte, ahora)
        )
