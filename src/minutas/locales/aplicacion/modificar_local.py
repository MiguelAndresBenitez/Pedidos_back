"""Paso que repiten los casos de uso del panel: obtener, cambiar, guardar y confirmar."""

from collections.abc import Callable

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


async def modificar_local(
    crear_unidad: FabricaDeUnidadesDelLocal, local_id: LocalId, cambio: Callable[[Local], object]
) -> Local:
    """Aplica el cambio al local en una transacción y devuelve el local guardado."""
    async with crear_unidad(local_id) as unidad:
        local = await unidad.locales.obtener()
        cambio(local)
        await unidad.locales.guardar(local)
        await unidad.confirmar()
    return local
