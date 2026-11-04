import json
from collections.abc import Iterator

import pytest
import structlog

from minutas.compartido.infraestructura.registro import (
    configurar_registro,
    limpiar_contexto,
    obtener_contexto,
    vincular_contexto,
)


@pytest.fixture(autouse=True)
def contexto_limpio() -> Iterator[None]:
    limpiar_contexto()
    yield
    limpiar_contexto()
    structlog.reset_defaults()


def leer_lineas(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines()]


def test_registrar_emite_json_con_el_contexto_vinculado(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configurar_registro("INFO")
    vincular_contexto(request_id="abc", local_id="123")

    structlog.get_logger().info("pedido_recibido", numero=42)

    [linea] = leer_lineas(capsys)
    assert linea["event"] == "pedido_recibido"
    assert linea["level"] == "info"
    assert linea["request_id"] == "abc"
    assert linea["local_id"] == "123"
    assert linea["numero"] == 42
    assert "timestamp" in linea


def test_registrar_por_debajo_del_nivel_no_emite_nada(capsys: pytest.CaptureFixture[str]) -> None:
    configurar_registro("WARNING")

    structlog.get_logger().info("detalle_sin_importancia")

    assert leer_lineas(capsys) == []


def test_limpiar_contexto_quita_los_valores_vinculados(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configurar_registro("INFO")
    vincular_contexto(request_id="abc")
    limpiar_contexto()

    structlog.get_logger().info("sin_contexto")

    [linea] = leer_lineas(capsys)
    assert "request_id" not in linea


def test_obtener_contexto_devuelve_los_valores_vinculados() -> None:
    vincular_contexto(request_id="abc")

    assert obtener_contexto() == {"request_id": "abc"}
