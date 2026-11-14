import pytest

from minutas.locales.dominio.errores import ImagenInvalida
from minutas.locales.dominio.imagen import Medidas, NombreDeImagen, TipoDeImagen


def test_medidas_maximas_dependen_del_tipo() -> None:
    assert TipoDeImagen.LOGO.medidas_maximas == Medidas(512, 512)
    assert TipoDeImagen.PORTADA.medidas_maximas.ancho == 1600


def test_crear_nombre_de_imagen_valido_conserva_el_valor() -> None:
    assert str(NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")).endswith(".webp")


@pytest.mark.parametrize(
    "valor", ["logo.png", "../etc/passwd", "01a18e9b-3c49-45a8-a745-cbce398ad79a.webp"]
)
def test_crear_nombre_de_imagen_invalido_falla(valor: str) -> None:
    with pytest.raises(ImagenInvalida, match="no es un nombre de imagen válido"):
        NombreDeImagen(valor)
