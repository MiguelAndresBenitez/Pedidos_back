"""Servicios de la app armados con dobles en memoria, para la API y la consola sin base."""

from dataclasses import dataclass
from datetime import UTC, datetime

from minutas.composicion import Servicios
from soporte.imagenes_en_memoria import (
    AlmacenDeImagenesEnMemoria,
    LectorSinImagenes,
    ProcesadorDeImagenesFalso,
)
from soporte.locales_en_memoria import BaseDeLocalesEnMemoria
from soporte.reloj_fijo import RelojFijo

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
INSTANTE_DE_PRUEBA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)


@dataclass
class ServiciosEnMemoria:
    locales: BaseDeLocalesEnMemoria
    reloj: RelojFijo
    almacen: AlmacenDeImagenesEnMemoria
    servicios: Servicios


async def no_cerrar_nada() -> None:
    return None


def crear_servicios_en_memoria() -> ServiciosEnMemoria:
    locales = BaseDeLocalesEnMemoria()
    reloj = RelojFijo(INSTANTE_DE_PRUEBA)
    almacen = AlmacenDeImagenesEnMemoria()
    servicios = Servicios(
        crear_unidad_del_local=locales.crear_unidad_del_local,
        crear_unidad_del_directorio=locales.crear_unidad_del_directorio,
        reloj=reloj,
        procesador_de_imagenes=ProcesadorDeImagenesFalso(),
        almacen_de_imagenes=almacen,
        lector_de_imagenes=LectorSinImagenes(),
        cerrar=no_cerrar_nada,
    )
    return ServiciosEnMemoria(locales, reloj, almacen, servicios)
