"""Esquemas HTTP de la tienda pública: traducen la vista de la aplicación, sin calcular nada."""

from datetime import datetime, time
from functools import singledispatch
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

from minutas.locales.aplicacion.vista_de_tienda import (
    TiendaDisponible,
    TiendaNoDisponible,
    VistaDeTienda,
)
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.modalidad import Modalidad

Hora = Annotated[time, PlainSerializer(lambda hora: hora.strftime("%H:%M"), return_type=str)]


class FranjaHttp(BaseModel):
    dia: DiaDeLaSemana
    apertura: Hora
    cierre: Hora


class TiendaHttp(BaseModel):
    disponible: Literal[True] = True
    slug: str
    nombre: str
    descripcion: str | None
    direccion: str | None
    whatsapp: str
    color: str
    modalidades: list[Modalidad]
    zona_horaria: str
    horarios: list[FranjaHttp]
    logo_url: str | None
    portada_url: str | None
    abierto_ahora: bool
    proxima_apertura: datetime | None


class TiendaNoDisponibleHttp(BaseModel):
    disponible: Literal[False] = False
    slug: str


@singledispatch
def crear_tienda_http(vista: VistaDeTienda) -> TiendaHttp | TiendaNoDisponibleHttp:
    """Despacho por tipo de vista (sin `if`): cada variante tiene su traducción."""
    raise TypeError(f"Vista de tienda desconocida: {type(vista).__name__}")


@crear_tienda_http.register
def _(vista: TiendaDisponible) -> TiendaHttp:
    return TiendaHttp(
        slug=vista.slug,
        nombre=vista.nombre,
        descripcion=vista.descripcion,
        direccion=vista.direccion,
        whatsapp=vista.whatsapp,
        color=vista.color,
        modalidades=list(vista.modalidades),
        zona_horaria=vista.zona_horaria,
        horarios=[
            FranjaHttp(dia=franja.dia, apertura=franja.apertura, cierre=franja.cierre)
            for franja in vista.franjas
        ],
        logo_url=vista.logo_url,
        portada_url=vista.portada_url,
        abierto_ahora=vista.abierto_ahora,
        proxima_apertura=vista.proxima_apertura,
    )


@crear_tienda_http.register
def _(vista: TiendaNoDisponible) -> TiendaNoDisponibleHttp:
    return TiendaNoDisponibleHttp(slug=vista.slug)
