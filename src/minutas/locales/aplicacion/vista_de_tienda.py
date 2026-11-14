"""Modelo de lectura de la tienda pública: todo lo que muestra, ya calculado."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import assert_never

from minutas.locales.dominio.estado_del_local import Activo, Suspendido
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


def _disponible(local: Local, ahora: datetime, url_de: UrlDeImagen) -> TiendaDisponible:
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


def crear_vista_de_tienda(local: Local, ahora: datetime, url_de: UrlDeImagen) -> VistaDeTienda:
    """La variante la decide el estado del local.

    El `match` es exhaustivo sobre `EstadoDelLocal`: si se suma un estado, mypy marca este
    lugar con `assert_never` en vez de que la tienda falle en producción.
    """
    match local.estado:
        case Activo():
            return _disponible(local, ahora, url_de)
        case Suspendido():
            return TiendaNoDisponible(local.slug.valor)
        case _:
            assert_never(local.estado)
