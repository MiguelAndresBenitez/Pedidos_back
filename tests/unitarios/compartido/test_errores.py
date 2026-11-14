import pytest

from minutas.compartido.dominio.errores import (
    Conflicto,
    ErrorDeDominio,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)


class ProductoInexistente(NoEncontrado):
    codigo = "producto_inexistente"


def test_crear_error_de_dominio_guarda_mensaje_y_codigo() -> None:
    error = ErrorDeDominio("Algo salió mal")

    assert error.mensaje == "Algo salió mal"
    assert error.codigo == "error_de_dominio"
    assert str(error) == "Algo salió mal"


@pytest.mark.parametrize(
    ("clase", "codigo"),
    [
        (NoEncontrado, "no_encontrado"),
        (Conflicto, "conflicto"),
        (ReglaDeNegocioIncumplida, "regla_de_negocio_incumplida"),
        (LimiteExcedido, "limite_excedido"),
    ],
)
def test_crear_categoria_de_error_tiene_codigo_propio(
    clase: type[ErrorDeDominio], codigo: str
) -> None:
    error = clase("mensaje")

    assert isinstance(error, ErrorDeDominio)
    assert error.codigo == codigo


def test_crear_error_concreto_hereda_categoria_y_redefine_codigo() -> None:
    error = ProductoInexistente("El producto no existe")

    assert isinstance(error, NoEncontrado)
    assert error.codigo == "producto_inexistente"
