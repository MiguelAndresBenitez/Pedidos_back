"""Color de marca del local, en hexadecimal."""

import re
from dataclasses import dataclass
from typing import Self

from minutas.locales.dominio.errores import DatoDelLocalInvalido

PATRON_DE_COLOR = re.compile(r"#[0-9a-f]{6}")


@dataclass(frozen=True, slots=True)
class Color:
    hexadecimal: str

    def __post_init__(self) -> None:
        if not PATRON_DE_COLOR.fullmatch(self.hexadecimal):
            raise DatoDelLocalInvalido(
                f"'{self.hexadecimal}' no es un color válido: se espera #rrggbb"
            )

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        return cls(texto.lower())


COLOR_POR_DEFECTO = Color("#000000")
