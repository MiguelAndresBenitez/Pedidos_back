"""Caso de uso del admin: quitar el cierre manual, vigente o no."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class Reabrir:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId) -> Local:
        return await modificar_local(self._crear_unidad, local_id, Local.reabrir)
