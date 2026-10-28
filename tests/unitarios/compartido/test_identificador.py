import time
from dataclasses import dataclass
from uuid import uuid4

import pytest

from minutas.compartido.dominio.identificador import Identificador, IdentificadorInvalido
from minutas.compartido.dominio.local_id import LocalId


@dataclass(frozen=True, slots=True)
class PedidoId(Identificador):
    pass


def test_generar_crea_uuid_version_7() -> None:
    assert Identificador.generar().valor.version == 7


def test_generar_devuelve_instancia_de_la_subclase() -> None:
    assert isinstance(LocalId.generar(), LocalId)


def test_generar_respeta_el_orden_temporal() -> None:
    primero = Identificador.generar()
    time.sleep(0.002)
    segundo = Identificador.generar()

    assert primero.valor < segundo.valor


def test_crear_con_uuid_version_4_falla() -> None:
    with pytest.raises(IdentificadorInvalido, match="versión 4"):
        Identificador(uuid4())


def test_desde_texto_reconstruye_el_mismo_identificador() -> None:
    original = LocalId.generar()

    assert LocalId.desde_texto(str(original)) == original


def test_desde_texto_con_texto_invalido_falla() -> None:
    with pytest.raises(IdentificadorInvalido, match="no es un UUID válido"):
        LocalId.desde_texto("cualquier-cosa")


def test_comparar_identificadores_de_tipos_distintos_no_son_iguales() -> None:
    valor = Identificador.generar().valor
    otro: object = PedidoId(valor)

    assert LocalId(valor) != otro
