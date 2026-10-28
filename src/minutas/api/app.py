"""Fábrica de la aplicación FastAPI: raíz de composición HTTP."""

from fastapi import FastAPI

from minutas import __version__
from minutas.api.middleware_de_solicitud import MiddlewareDeSolicitud
from minutas.api.salud import router_de_salud
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro


def crear_app(configuracion: Configuracion) -> FastAPI:
    configurar_registro(configuracion.nivel_de_registro)
    app = FastAPI(title="Minutas", version=__version__)
    app.add_middleware(MiddlewareDeSolicitud)
    app.include_router(router_de_salud)
    return app


def crear_app_desde_entorno() -> FastAPI:
    """Entrada para uvicorn: `uvicorn --factory minutas.api.app:crear_app_desde_entorno`."""
    return crear_app(Configuracion())
