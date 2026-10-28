import httpx
import pytest
from fastapi import FastAPI

from minutas.api.app import crear_app
from minutas.compartido.dominio.errores import (
    Conflicto,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)
from minutas.compartido.infraestructura.configuracion import Configuracion


class TiendaCerrada(ReglaDeNegocioIncumplida):
    codigo = "tienda_cerrada"


@pytest.fixture
def app(configuracion: Configuracion) -> FastAPI:
    app = crear_app(configuracion)
    errores: dict[str, Exception] = {
        "tienda-cerrada": TiendaCerrada("La tienda está cerrada"),
        "no-encontrado": NoEncontrado("No existe"),
        "conflicto": Conflicto("Choca con otro dato"),
        "limite": LimiteExcedido("Demasiados pedidos"),
        "inesperado": RuntimeError("secreto interno"),
    }

    @app.get("/prueba/{caso}")
    async def lanzar(caso: str) -> None:
        raise errores[caso]

    @app.get("/prueba-validacion")
    async def validar(cantidad: int) -> dict[str, int]:
        return {"cantidad": cantidad}

    return app


@pytest.mark.parametrize(
    ("caso", "estado", "codigo", "detalle"),
    [
        ("tienda-cerrada", 422, "tienda_cerrada", "La tienda está cerrada"),
        ("no-encontrado", 404, "no_encontrado", "No existe"),
        ("conflicto", 409, "conflicto", "Choca con otro dato"),
        ("limite", 429, "limite_excedido", "Demasiados pedidos"),
    ],
)
async def test_lanzar_error_de_dominio_responde_problem_json(
    cliente: httpx.AsyncClient, caso: str, estado: int, codigo: str, detalle: str
) -> None:
    respuesta = await cliente.get(f"/prueba/{caso}", headers={"X-Request-ID": "sol-1"})

    assert respuesta.status_code == estado
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo.pop("title")
    assert cuerpo == {
        "type": "about:blank",
        "status": estado,
        "detail": detalle,
        "code": codigo,
        "request_id": "sol-1",
    }


async def test_lanzar_error_inesperado_responde_500_con_id_y_sin_detalles(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/prueba/inesperado", headers={"X-Request-ID": "sol-2"})

    assert respuesta.status_code == 500
    assert respuesta.headers["X-Request-ID"] == "sol-2"
    assert respuesta.json()["code"] == "error_interno"
    assert respuesta.json()["request_id"] == "sol-2"
    assert "secreto" not in respuesta.text


async def test_enviar_parametro_invalido_responde_solicitud_invalida(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/prueba-validacion", params={"cantidad": "muchas"})

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "solicitud_invalida"
    assert cuerpo["errores"][0]["loc"] == ["query", "cantidad"]


@pytest.mark.parametrize(
    ("metodo", "ruta", "estado", "codigo"),
    [
        ("GET", "/no-existe", 404, "ruta_inexistente"),
        ("POST", "/salud", 405, "metodo_no_permitido"),
    ],
)
async def test_pedir_ruta_o_metodo_inexistente_responde_problem_json(
    cliente: httpx.AsyncClient, metodo: str, ruta: str, estado: int, codigo: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)

    assert respuesta.status_code == estado
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["code"] == codigo


async def test_pedir_metodo_no_permitido_conserva_la_cabecera_allow(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.post("/salud")

    assert respuesta.status_code == 405
    assert "GET" in respuesta.headers["allow"]
