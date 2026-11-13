"""Caso de uso del admin: reemplazar los datos editables de su local."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.datos_del_local import DatosDelLocal
from minutas.locales.dominio.local import Local


class ActualizarDatosDelLocal:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, datos: DatosDelLocal) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.actualizar_datos(datos)
        )
