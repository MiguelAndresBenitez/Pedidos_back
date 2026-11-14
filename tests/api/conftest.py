from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion
from soporte.servicios_en_memoria import ServiciosEnMemoria

URL_APP = "postgresql+asyncpg://minutas_app:clave@localhost:5432/minutas"


@pytest.fixture
def configuracion(tmp_path: Path) -> Configuracion:
    return Configuracion(
        url_base_de_datos=SecretStr(URL_APP),
        entorno="pruebas",
        directorio_de_imagenes=tmp_path / "imagenes",
    )


@pytest.fixture
def app(configuracion: Configuracion, memoria: ServiciosEnMemoria) -> FastAPI:
    return crear_app(configuracion, memoria.servicios)


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
