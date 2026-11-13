"""Punto de entrada de la consola del owner."""

import argparse
import asyncio
import sys
from collections.abc import Sequence

import structlog

from minutas.cli import comandos
from minutas.compartido.dominio.errores import ErrorDeDominio
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minutas", description="Operaciones del owner")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    alta_local = subcomandos.add_parser("alta-local", help="Da de alta un local")
    alta_local.add_argument("--slug", required=True)
    alta_local.add_argument("--nombre", required=True)
    alta_local.add_argument("--whatsapp", required=True)
    alta_local.add_argument(
        "--modalidades", type=comandos.leer_modalidades, default="delivery,retiro"
    )
    alta_local.set_defaults(ejecutar=comandos.alta_local)

    cambiar_slug = subcomandos.add_parser("cambiar-slug", help="Cambia el link de un local")
    cambiar_slug.add_argument("--slug", required=True)
    cambiar_slug.add_argument("--nuevo", required=True)
    cambiar_slug.set_defaults(ejecutar=comandos.cambiar_slug)

    zona = subcomandos.add_parser(
        "cambiar-zona-horaria", help="Cambia la zona horaria desde la próxima jornada"
    )
    zona.add_argument("--slug", required=True)
    zona.add_argument("--zona", required=True, help="Nombre IANA, por ejemplo America/Santiago")
    zona.set_defaults(ejecutar=comandos.cambiar_zona_horaria)

    suspender = subcomandos.add_parser("suspender-local", help="Suspende un local")
    suspender.add_argument("--slug", required=True)
    suspender.set_defaults(ejecutar=comandos.suspender_local)

    reactivar = subcomandos.add_parser("reactivar-local", help="Reactiva un local suspendido")
    reactivar.add_argument("--slug", required=True)
    reactivar.set_defaults(ejecutar=comandos.reactivar_local)
    return parser


async def correr(argv: Sequence[str], servicios: Servicios) -> int:
    """Ejecuta un comando y devuelve el código de salida: 0 si funcionó, 1 si no."""
    argumentos = crear_parser().parse_args(argv)
    # Solo el comando y el slug: los argumentos pueden traer datos personales (el WhatsApp).
    # Por la misma razón el mensaje de error no se registra: puede repetir el WhatsApp escrito.
    registro = structlog.get_logger().bind(comando=argumentos.comando, slug=argumentos.slug)
    casos = crear_casos_de_uso(servicios)
    try:
        mensaje = await argumentos.ejecutar(argumentos, casos, servicios.reloj.ahora())
    except ErrorDeDominio as error:
        registro.warning("comando_rechazado", codigo=error.codigo)
        print(f"Error: {error.mensaje}", file=sys.stderr)
        return 1
    registro.info("comando_ejecutado")
    print(mensaje)
    return 0


async def principal(argv: Sequence[str]) -> int:
    configuracion = Configuracion()
    configurar_registro(configuracion.nivel_de_registro)
    servicios = crear_servicios(configuracion)
    try:
        return await correr(argv, servicios)
    finally:
        await servicios.cerrar()


if __name__ == "__main__":
    sys.exit(asyncio.run(principal(sys.argv[1:])))
