"""Imágenes del local: tipos, límites y el nombre con que se guardan."""

import re
from dataclasses import dataclass
from enum import StrEnum

from minutas.locales.dominio.errores import ImagenInvalida

TAMANIO_MAXIMO_DE_IMAGEN = 2 * 1024 * 1024
PATRON_DE_NOMBRE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}\.webp"
)


@dataclass(frozen=True, slots=True)
class Medidas:
    """Medidas máximas en píxeles; la imagen se achica manteniendo la proporción."""

    ancho: int
    alto: int


class TipoDeImagen(StrEnum):
    LOGO = "logo"
    PORTADA = "portada"

    @property
    def medidas_maximas(self) -> Medidas:
        return MEDIDAS_POR_TIPO[self]


# La portada se limita por ancho; el alto queda libre dentro de una proporción razonable.
MEDIDAS_POR_TIPO = {
    TipoDeImagen.LOGO: Medidas(512, 512),
    TipoDeImagen.PORTADA: Medidas(1600, 4800),
}


@dataclass(frozen=True, slots=True)
class NombreDeImagen:
    """`<uuid7>.webp`: lo genera el almacén y nunca se repite."""

    valor: str

    def __post_init__(self) -> None:
        if not PATRON_DE_NOMBRE.fullmatch(self.valor):
            raise ImagenInvalida(f"'{self.valor}' no es un nombre de imagen válido")

    def __str__(self) -> str:
        return self.valor
