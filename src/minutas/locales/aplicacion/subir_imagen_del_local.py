"""Caso de uso del admin: subir el logo o la portada. Sin entrada HTTP hasta la etapa 1b."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.procesador_de_imagenes import ProcesadorDeImagenes
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen


class SubirImagenDelLocal:
    def __init__(
        self,
        crear_unidad: FabricaDeUnidadesDelLocal,
        procesador: ProcesadorDeImagenes,
        almacen: AlmacenDeImagenes,
    ) -> None:
        self._crear_unidad = crear_unidad
        self._procesador = procesador
        self._almacen = almacen

    async def ejecutar(
        self, local_id: LocalId, tipo: TipoDeImagen, contenido: bytes
    ) -> NombreDeImagen:
        """Procesa fuera de la transacción. Si la transacción falla, el archivo queda huérfano:
        es aceptable, porque el nombre nunca se reutiliza."""
        procesada = await self._procesador.procesar(contenido, tipo.medidas_maximas)
        async with self._crear_unidad(local_id) as unidad:
            local = await unidad.locales.obtener()
            local.asegurar_modificable()
            nombre = await self._almacen.guardar(procesada)
            local.cambiar_imagen(tipo, nombre)
            await unidad.locales.guardar(local)
            await unidad.confirmar()
        return nombre
