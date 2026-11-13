from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.locales.infraestructura.almacen_de_imagenes_en_disco import AlmacenDeImagenesEnDisco
from soporte.servicios_en_memoria import ServiciosEnMemoria

NOMBRE = "01a18e9b-3c49-75a8-a745-cbce398ad79a.webp"


@pytest.fixture
async def cliente(
    configuracion: Configuracion, memoria: ServiciosEnMemoria, tmp_path: Path
) -> AsyncIterator[httpx.AsyncClient]:
    """La app con el lector de disco real sobre una carpeta con una imagen."""
    (tmp_path / NOMBRE).write_bytes(b"RIFF....WEBP")
    lector = AlmacenDeImagenesEnDisco(tmp_path, "/api/v1/imagenes")
    app = crear_app(configuracion, replace(memoria.servicios, lector_de_imagenes=lector))
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


async def test_obtener_imagen_la_sirve_con_cache_de_un_anio(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get(f"/api/v1/imagenes/{NOMBRE}")

    assert respuesta.status_code == 200
    assert respuesta.content == b"RIFF....WEBP"
    assert respuesta.headers["content-type"] == "image/webp"
    assert respuesta.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize(
    "nombre", ["..%2F..%2Fetc%2Fpasswd", "logo.png", "01a18e9b-3c49-75a8-a745-cbce398ad79b.webp"]
)
async def test_obtener_imagen_invalida_o_inexistente_responde_404(
    cliente: httpx.AsyncClient, nombre: str
) -> None:
    respuesta = await cliente.get(f"/api/v1/imagenes/{nombre}")

    assert respuesta.status_code == 404
