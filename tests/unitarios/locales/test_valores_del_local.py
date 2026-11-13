import pytest

from minutas.locales.dominio.color import Color
from minutas.locales.dominio.errores import (
    DatoDelLocalInvalido,
    SlugInvalido,
    SlugReservado,
    WhatsappInvalido,
    ZonaHorariaInvalida,
)
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria


@pytest.mark.parametrize("valor", ["abc", "la-esquina", "pizzeria-24", "a" * 40])
def test_crear_slug_valido_conserva_el_valor(valor: str) -> None:
    assert str(Slug(valor)) == valor


@pytest.mark.parametrize(
    "valor",
    ["ab", "a" * 41, "La-Esquina", "-esquina", "esquina-", "la--esquina", "la esquina", "ñu"],
)
def test_crear_slug_invalido_falla(valor: str) -> None:
    with pytest.raises(SlugInvalido, match="no es un slug válido"):
        Slug(valor)


@pytest.mark.parametrize("valor", ["api", "panel", "admin", "tiendas"])
def test_crear_slug_reservado_falla(valor: str) -> None:
    with pytest.raises(SlugReservado, match="palabra reservada"):
        Slug(valor)


@pytest.mark.parametrize(
    "texto",
    [
        "0351 15 512-3456",
        "351 15 5123456",
        "+54 9 351 512 3456",
        "5493515123456",
        "+5493515123456",
    ],
)
def test_whatsapp_desde_texto_normaliza_las_formas_de_escribir_un_celular(texto: str) -> None:
    assert Whatsapp.desde_texto(texto) == Whatsapp("5493515123456")


def test_whatsapp_desde_texto_de_otro_pais_lo_acepta_con_su_codigo() -> None:
    assert Whatsapp.desde_texto("+56 9 6123 4567").numero == "56961234567"


@pytest.mark.parametrize("texto", ["351 5123456", "0351 4123456", "123", "sin numero", ""])
def test_whatsapp_desde_texto_que_no_es_un_celular_falla(texto: str) -> None:
    with pytest.raises(WhatsappInvalido, match="no es un celular válido"):
        Whatsapp.desde_texto(texto)


def test_crear_whatsapp_sin_normalizar_falla() -> None:
    with pytest.raises(WhatsappInvalido):
        Whatsapp("03515123456")


def test_color_desde_texto_pasa_a_minusculas() -> None:
    assert Color.desde_texto("#FF8800") == Color("#ff8800")


@pytest.mark.parametrize("texto", ["ff8800", "#ff88", "#gg8800", "rojo"])
def test_color_desde_texto_invalido_falla(texto: str) -> None:
    with pytest.raises(DatoDelLocalInvalido, match="no es un color válido"):
        Color.desde_texto(texto)


def test_crear_zona_horaria_valida_expone_su_zoneinfo() -> None:
    assert ZonaHoraria("America/Santiago").info.key == "America/Santiago"


@pytest.mark.parametrize("nombre", ["Marte/Olympus", "", "../etc/passwd"])
def test_crear_zona_horaria_desconocida_falla(nombre: str) -> None:
    with pytest.raises(ZonaHorariaInvalida, match="no es una zona horaria válida"):
        ZonaHoraria(nombre)
