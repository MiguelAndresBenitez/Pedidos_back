"""Dependencias de FastAPI: casos de uso, la hora de la solicitud y el lector de imágenes.

Las rutas no reciben `Servicios` entero: piden solo lo que usan.
"""

from datetime import datetime
from typing import Annotated, cast

from fastapi import Depends, Request

from minutas.composicion import CasosDeUso, Servicios
from minutas.locales.aplicacion.lector_de_imagenes import LectorDeImagenes


def obtener_servicios(request: Request) -> Servicios:
    return cast(Servicios, request.app.state.servicios)


def obtener_casos_de_uso(request: Request) -> CasosDeUso:
    return cast(CasosDeUso, request.app.state.casos_de_uso)


ServiciosInyectados = Annotated[Servicios, Depends(obtener_servicios)]
CasosInyectados = Annotated[CasosDeUso, Depends(obtener_casos_de_uso)]


def obtener_ahora(servicios: ServiciosInyectados) -> datetime:
    """Un solo instante por solicitud: FastAPI resuelve cada dependencia una vez por request."""
    return servicios.reloj.ahora()


AhoraInyectado = Annotated[datetime, Depends(obtener_ahora)]


def obtener_lector_de_imagenes(servicios: ServiciosInyectados) -> LectorDeImagenes:
    return servicios.lector_de_imagenes


LectorInyectado = Annotated[LectorDeImagenes, Depends(obtener_lector_de_imagenes)]
