import importlib

import pytest

import minutas

CONTEXTOS = ("compartido", "identidad", "locales", "carta", "pedidos")
CAPAS = ("dominio", "aplicacion", "infraestructura")
MODULOS = [f"minutas.{contexto}.{capa}" for contexto in CONTEXTOS for capa in CAPAS]


def test_importar_paquete_expone_version_0_1_0() -> None:
    assert minutas.__version__ == "0.1.0"


@pytest.mark.parametrize("modulo", [*MODULOS, "minutas.api"])
def test_importar_capa_de_contexto_existe(modulo: str) -> None:
    assert importlib.import_module(modulo).__name__ == modulo
