from datetime import time

import httpx
import pytest

from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from soporte.servicios_en_memoria import INSTANTE_DE_PRUEBA, ServiciosEnMemoria

LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


@pytest.fixture
async def local(memoria: ServiciosEnMemoria) -> Local:
    local = await DarDeAltaLocal(memoria.servicios.crear_unidad_del_local).ejecutar(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )
    guardado = memoria.locales.locales[local.id]
    guardado.reemplazar_horario(
        Horario(
            (
                FranjaHoraria(DiaDeLaSemana.VIERNES, time(19), time(1)),
                FranjaHoraria(DiaDeLaSemana.SABADO, time(19), time(1)),
            )
        ),
        INSTANTE_DE_PRUEBA,
    )
    guardado.cambiar_imagen(TipoDeImagen.LOGO, LOGO)
    return guardado


@pytest.mark.usefixtures("local")
async def test_obtener_tienda_abierta_devuelve_los_datos_publicos(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/la-esquina")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "disponible": True,
        "slug": "la-esquina",
        "nombre": "La Esquina",
        "descripcion": None,
        "direccion": None,
        "whatsapp": "5493515123456",
        "color": "#000000",
        "modalidades": ["retiro"],
        "zona_horaria": "America/Argentina/Buenos_Aires",
        "horarios": [
            {"dia": 4, "apertura": "19:00", "cierre": "01:00"},
            {"dia": 5, "apertura": "19:00", "cierre": "01:00"},
        ],
        "logo_url": f"/api/v1/imagenes/{LOGO}",
        "portada_url": None,
        "abierto_ahora": True,
        "proxima_apertura": None,
    }


async def test_obtener_tienda_cerrada_por_hoy_anuncia_la_proxima_apertura(
    cliente: httpx.AsyncClient, local: Local
) -> None:
    local.cerrar_por_hoy(INSTANTE_DE_PRUEBA)

    cuerpo = (await cliente.get("/api/v1/tiendas/la-esquina")).json()

    assert cuerpo["abierto_ahora"] is False
    # Sábado 7/11 a las 19:00 en Buenos Aires.
    assert cuerpo["proxima_apertura"] == "2026-11-07T22:00:00Z"


async def test_obtener_tienda_suspendida_solo_dice_que_no_esta_disponible(
    cliente: httpx.AsyncClient, local: Local
) -> None:
    local.suspender()

    respuesta = await cliente.get("/api/v1/tiendas/la-esquina")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"disponible": False, "slug": "la-esquina"}


async def test_obtener_tienda_inexistente_responde_404(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "local_no_encontrado"


async def test_obtener_tienda_con_slug_mal_formado_responde_422(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/La_Esquina")

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "slug_invalido"
