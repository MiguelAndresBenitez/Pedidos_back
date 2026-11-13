"""Raíz de composición compartida por la API y la consola: arma adaptadores y casos de uso."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from minutas.api.rutas_publicas import RUTA_DE_IMAGENES
from minutas.compartido.aplicacion.reloj import Reloj
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.reloj_del_sistema import RelojDelSistema
from minutas.locales.aplicacion.actualizar_datos_del_local import ActualizarDatosDelLocal
from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.cambiar_hora_de_corte import CambiarHoraDeCorte
from minutas.locales.aplicacion.cambiar_slug import CambiarSlug
from minutas.locales.aplicacion.cambiar_zona_horaria import CambiarZonaHoraria
from minutas.locales.aplicacion.cerrar_manualmente import CerrarManualmente
from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.aplicacion.lector_de_imagenes import LectorDeImagenes
from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.aplicacion.obtener_local_del_panel import ObtenerLocalDelPanel
from minutas.locales.aplicacion.obtener_tienda import ObtenerTienda
from minutas.locales.aplicacion.procesador_de_imagenes import ProcesadorDeImagenes
from minutas.locales.aplicacion.reabrir import Reabrir
from minutas.locales.aplicacion.reactivar_local import ReactivarLocal
from minutas.locales.aplicacion.reemplazar_horario import ReemplazarHorario
from minutas.locales.aplicacion.subir_imagen_del_local import SubirImagenDelLocal
from minutas.locales.aplicacion.suspender_local import SuspenderLocal
from minutas.locales.aplicacion.unidades_de_trabajo import (
    FabricaDeUnidadesDelDirectorio,
    FabricaDeUnidadesDelLocal,
    UnidadDeTrabajoDelDirectorio,
    UnidadDeTrabajoDelLocal,
)
from minutas.locales.infraestructura.almacen_de_imagenes_en_disco import AlmacenDeImagenesEnDisco
from minutas.locales.infraestructura.procesador_de_imagenes_con_pillow import (
    ProcesadorDeImagenesConPillow,
)
from minutas.locales.infraestructura.unidades_de_trabajo_sqlalchemy import (
    UnidadDelDirectorioSQLAlchemy,
    UnidadDelLocalSQLAlchemy,
)


@dataclass(frozen=True, kw_only=True)
class Servicios:
    """Adaptadores de los casos de uso; los tests los reemplazan por dobles en memoria."""

    crear_unidad_del_local: FabricaDeUnidadesDelLocal
    crear_unidad_del_directorio: FabricaDeUnidadesDelDirectorio
    reloj: Reloj
    procesador_de_imagenes: ProcesadorDeImagenes
    almacen_de_imagenes: AlmacenDeImagenes
    lector_de_imagenes: LectorDeImagenes
    cerrar: Callable[[], Awaitable[None]]


def crear_servicios(configuracion: Configuracion) -> Servicios:
    motor = crear_motor(configuracion.url_base_de_datos.get_secret_value())
    fabrica = crear_fabrica_de_sesiones(motor)

    def crear_unidad_del_local(local_id: LocalId) -> UnidadDeTrabajoDelLocal:
        return UnidadDelLocalSQLAlchemy(fabrica, local_id)

    def crear_unidad_del_directorio() -> UnidadDeTrabajoDelDirectorio:
        return UnidadDelDirectorioSQLAlchemy(fabrica)

    imagenes = AlmacenDeImagenesEnDisco(configuracion.directorio_de_imagenes, RUTA_DE_IMAGENES)
    return Servicios(
        crear_unidad_del_local=crear_unidad_del_local,
        crear_unidad_del_directorio=crear_unidad_del_directorio,
        reloj=RelojDelSistema(),
        procesador_de_imagenes=ProcesadorDeImagenesConPillow(),
        almacen_de_imagenes=imagenes,
        lector_de_imagenes=imagenes,
        cerrar=motor.dispose,
    )


@dataclass(frozen=True, kw_only=True)
class CasosDeUso:
    """Casos de uso ya armados: la API y la consola solo los ejecutan. No tienen estado."""

    dar_de_alta_local: DarDeAltaLocal
    cambiar_slug: CambiarSlug
    cambiar_zona_horaria: CambiarZonaHoraria
    suspender_local: SuspenderLocal
    reactivar_local: ReactivarLocal
    obtener_tienda: ObtenerTienda
    actualizar_datos_del_local: ActualizarDatosDelLocal
    reemplazar_horario: ReemplazarHorario
    cambiar_hora_de_corte: CambiarHoraDeCorte
    cerrar_manualmente: CerrarManualmente
    reabrir: Reabrir
    subir_imagen_del_local: SubirImagenDelLocal
    obtener_local_del_panel: ObtenerLocalDelPanel


def crear_casos_de_uso(servicios: Servicios) -> CasosDeUso:
    del_local = servicios.crear_unidad_del_local
    por_slug = LocalesPorSlug(servicios.crear_unidad_del_directorio, del_local)
    return CasosDeUso(
        dar_de_alta_local=DarDeAltaLocal(del_local),
        cambiar_slug=CambiarSlug(por_slug),
        cambiar_zona_horaria=CambiarZonaHoraria(por_slug),
        suspender_local=SuspenderLocal(por_slug),
        reactivar_local=ReactivarLocal(por_slug),
        obtener_tienda=ObtenerTienda(por_slug, servicios.almacen_de_imagenes),
        actualizar_datos_del_local=ActualizarDatosDelLocal(del_local),
        reemplazar_horario=ReemplazarHorario(del_local),
        cambiar_hora_de_corte=CambiarHoraDeCorte(del_local),
        cerrar_manualmente=CerrarManualmente(del_local),
        reabrir=Reabrir(del_local),
        subir_imagen_del_local=SubirImagenDelLocal(
            del_local, servicios.procesador_de_imagenes, servicios.almacen_de_imagenes
        ),
        obtener_local_del_panel=ObtenerLocalDelPanel(del_local),
    )
