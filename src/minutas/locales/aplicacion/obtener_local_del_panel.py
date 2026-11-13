"""Consulta del admin: su local completo. Sin entrada HTTP hasta la etapa 1b."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class ObtenerLocalDelPanel:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId) -> Local:
        async with self._crear_unidad(local_id) as unidad:
            return await unidad.locales.obtener()
