"""Fábrica de la aplicación FastAPI: raíz de composición HTTP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from minutas import __version__
from minutas.api.errores_http import registrar_manejadores_de_errores
from minutas.api.middleware_de_solicitud import MiddlewareDeSolicitud
from minutas.api.rutas_de_tiendas import router_de_tiendas
from minutas.api.salud import router_de_salud
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios


def crear_app(configuracion: Configuracion, servicios: Servicios) -> FastAPI:
    configurar_registro(configuracion.nivel_de_registro)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        yield
        await servicios.cerrar()

    app = FastAPI(title="Minutas", version=__version__, lifespan=ciclo_de_vida)
    app.state.configuracion = configuracion
    app.state.servicios = servicios
    app.state.casos_de_uso = crear_casos_de_uso(servicios)
    app.add_middleware(MiddlewareDeSolicitud)
    app.include_router(router_de_salud)
    app.include_router(router_de_tiendas)
    registrar_manejadores_de_errores(app)
    return app


def crear_app_desde_entorno() -> FastAPI:
    """Entrada para uvicorn: `uvicorn --factory minutas.api.app:crear_app_desde_entorno`."""
    configuracion = Configuracion()
    return crear_app(configuracion, crear_servicios(configuracion))
