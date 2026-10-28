from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion

URL_APP = "postgresql+asyncpg://minutas_app:clave@localhost:5432/minutas"


@pytest.fixture
def configuracion() -> Configuracion:
    return Configuracion(url_base_de_datos=URL_APP, entorno="pruebas")


@pytest.fixture
def app(configuracion: Configuracion) -> FastAPI:
    return crear_app(configuracion)


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
