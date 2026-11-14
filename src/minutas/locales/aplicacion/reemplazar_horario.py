"""Caso de uso del admin: reemplazar la semana completa de franjas."""

from datetime import datetime

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.local import Local


class ReemplazarHorario:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, horario: Horario, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.reemplazar_horario(horario, ahora)
        )
