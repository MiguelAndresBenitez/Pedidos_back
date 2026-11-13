"""Comandos del owner. Cada uno ejecuta un caso de uso y devuelve el texto para la consola."""

import argparse
from datetime import datetime

from minutas.composicion import CasosDeUso
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria


def leer_modalidades(texto: str) -> frozenset[Modalidad]:
    """Tipo de argparse: `delivery,retiro`. Un valor desconocido es un error de uso (código 2)."""
    try:
        return frozenset(Modalidad(valor.strip()) for valor in texto.split(","))
    except ValueError as error:
        opciones = ", ".join(Modalidad)
        raise argparse.ArgumentTypeError(f"modalidades válidas: {opciones}") from error


async def alta_local(argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime) -> str:
    local = await casos.dar_de_alta_local.ejecutar(
        Slug(argumentos.slug),
        argumentos.nombre,
        Whatsapp.desde_texto(argumentos.whatsapp),
        argumentos.modalidades,
    )
    return f"Local '{local.slug}' dado de alta con id {local.id}"


async def cambiar_slug(argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime) -> str:
    await casos.cambiar_slug.ejecutar(Slug(argumentos.slug), Slug(argumentos.nuevo))
    return f"El local '{argumentos.slug}' ahora es '{argumentos.nuevo}'"


async def cambiar_zona_horaria(
    argumentos: argparse.Namespace, casos: CasosDeUso, ahora: datetime
) -> str:
    desde = await casos.cambiar_zona_horaria.ejecutar(
        Slug(argumentos.slug), ZonaHoraria(argumentos.zona), ahora
    )
    return f"El local '{argumentos.slug}' pasa a {argumentos.zona} desde la jornada del {desde}"


async def suspender_local(
    argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime
) -> str:
    await casos.suspender_local.ejecutar(Slug(argumentos.slug))
    return f"Local '{argumentos.slug}' suspendido"


async def reactivar_local(
    argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime
) -> str:
    await casos.reactivar_local.ejecutar(Slug(argumentos.slug))
    return f"Local '{argumentos.slug}' reactivado"
