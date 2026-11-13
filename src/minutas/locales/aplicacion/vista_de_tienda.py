"""Modelo de lectura de la tienda pública: todo lo que muestra, ya calculado."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from minutas.locales.dominio.estado_del_local import Activo, EstadoDelLocal, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad

type UrlDeImagen = Callable[[NombreDeImagen], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class TiendaDisponible:
    slug: str
    nombre: str
    descripcion: str | None
    direccion: str | None
    whatsapp: str
    color: str
    modalidades: tuple[Modalidad, ...]
    zona_horaria: str
    franjas: tuple[FranjaHoraria, ...]
    logo_url: str | None
    portada_url: str | None
    abierto_ahora: bool
    proxima_apertura: datetime | None


@dataclass(frozen=True, slots=True)
class TiendaNoDisponible:
    """Un local suspendido: la tienda no dice por qué."""

    slug: str


type VistaDeTienda = TiendaDisponible | TiendaNoDisponible


def _url(local: Local, tipo: TipoDeImagen, url_de: UrlDeImagen) -> str | None:
    nombre = local.imagenes.get(tipo)
    return None if nombre is None else url_de(nombre)


def _disponible(local: Local, ahora: datetime, url_de: UrlDeImagen) -> VistaDeTienda:
    datos = local.datos
    return TiendaDisponible(
        slug=local.slug.valor,
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        direccion=datos.direccion,
        whatsapp=datos.whatsapp.numero,
        color=datos.color.hexadecimal,
        modalidades=tuple(sorted(datos.modalidades)),
        zona_horaria=local.zona_horaria_en(ahora).nombre,
        franjas=local.horario.franjas,
        logo_url=_url(local, TipoDeImagen.LOGO, url_de),
        portada_url=_url(local, TipoDeImagen.PORTADA, url_de),
        abierto_ahora=local.esta_abierto(ahora),
        proxima_apertura=local.proxima_apertura(ahora),
    )


def _no_disponible(local: Local, _ahora: datetime, _url_de: UrlDeImagen) -> VistaDeTienda:
    return TiendaNoDisponible(local.slug.valor)


VISTAS_POR_ESTADO: dict[
    type[EstadoDelLocal], Callable[[Local, datetime, UrlDeImagen], VistaDeTienda]
] = {
    Activo: _disponible,
    Suspendido: _no_disponible,
}


def crear_vista_de_tienda(local: Local, ahora: datetime, url_de: UrlDeImagen) -> VistaDeTienda:
    """La variante la decide el estado del local, con una tabla de despacho."""
    return VISTAS_POR_ESTADO[type(local.estado)](local, ahora, url_de)
