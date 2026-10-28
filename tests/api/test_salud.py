from uuid import UUID

import httpx
import pytest


async def test_consultar_salud_responde_ok(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


async def test_consultar_salud_genera_id_de_solicitud_uuid7(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/salud")

    assert UUID(respuesta.headers["X-Request-ID"]).version == 7


async def test_consultar_salud_respeta_id_de_solicitud_valido(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/salud", headers={"X-Request-ID": "pedido-123"})

    assert respuesta.headers["X-Request-ID"] == "pedido-123"


@pytest.mark.parametrize("recibido", ["x" * 65, "con espacios", "comillas'raras"])
async def test_consultar_salud_reemplaza_id_de_solicitud_invalido(
    cliente: httpx.AsyncClient, recibido: str
) -> None:
    respuesta = await cliente.get("/salud", headers={"X-Request-ID": recibido})

    assert UUID(respuesta.headers["X-Request-ID"]).version == 7
