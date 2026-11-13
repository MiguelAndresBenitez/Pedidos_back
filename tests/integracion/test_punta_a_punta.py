import io
from collections.abc import AsyncIterator
from datetime import time
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from minutas.api.app import crear_app
from minutas.cli.__main__ import correr
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import TipoDeImagen
from minutas.locales.dominio.slug import Slug
from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion


def horario_de_todo_el_dia() -> Horario:
    """Abierto toda la semana: cada franja va de un corte (06:00) hasta un minuto antes del otro."""
    return Horario(tuple(FranjaHoraria(dia, time(6), time(5, 59)) for dia in DiaDeLaSemana))


def foto() -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (1024, 1024), "blue").save(salida, format="PNG")
    return salida.getvalue()


@pytest.fixture
def configuracion(base_migrada: BaseDePrueba, tmp_path: Path) -> Configuracion:
    return Configuracion(
        url_base_de_datos=SecretStr(base_migrada.url_app()),
        directorio_de_imagenes=tmp_path / "imagenes",
    )


@pytest.fixture
async def servicios(configuracion: Configuracion) -> AsyncIterator[Servicios]:
    servicios = crear_servicios(configuracion)
    yield servicios
    await servicios.cerrar()


@pytest.fixture
async def cliente(
    configuracion: Configuracion, servicios: Servicios
) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=crear_app(configuracion, servicios))
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


async def test_local_dado_de_alta_por_consola_abre_su_tienda_y_se_suspende(
    servicios: Servicios, cliente: httpx.AsyncClient
) -> None:
    alta = ["alta-local", "--slug", "la-esquina", "--nombre", "La Esquina"]
    assert await correr([*alta, "--whatsapp", "0351 15 512-3456"], servicios) == 0

    # Sin panel hasta la 1b: los horarios y el logo se cargan con los casos de uso.
    casos = crear_casos_de_uso(servicios)
    async with servicios.crear_unidad_del_directorio() as directorio:
        local_id = await directorio.directorio.obtener_local_id_por_slug(Slug("la-esquina"))
    ahora = servicios.reloj.ahora()
    await casos.reemplazar_horario.ejecutar(local_id, horario_de_todo_el_dia(), ahora)
    nombre = await casos.subir_imagen_del_local.ejecutar(local_id, TipoDeImagen.LOGO, foto())

    tienda = (await cliente.get("/api/v1/tiendas/la-esquina")).json()
    assert tienda["abierto_ahora"] is True
    assert tienda["whatsapp"] == "5493515123456"
    logo = await cliente.get(tienda["logo_url"])
    assert tienda["logo_url"] == f"/api/v1/imagenes/{nombre}"
    assert Image.open(io.BytesIO(logo.content)).size == (512, 512)

    assert await correr(["suspender-local", "--slug", "la-esquina"], servicios) == 0
    suspendida = await cliente.get("/api/v1/tiendas/la-esquina")
    assert suspendida.json() == {"disponible": False, "slug": "la-esquina"}
