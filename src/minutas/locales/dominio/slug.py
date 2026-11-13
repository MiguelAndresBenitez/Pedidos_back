"""Slug: el tramo del link público de la tienda, por ejemplo `la-esquina`."""

import re
from dataclasses import dataclass

from minutas.locales.dominio.errores import SlugInvalido, SlugReservado

PATRON_DE_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
LARGO_MINIMO_DE_SLUG = 3
LARGO_MAXIMO_DE_SLUG = 40
SLUGS_RESERVADOS = frozenset(
    {
        "admin",
        "api",
        "auth",
        "imagenes",
        "minutas",
        "owner",
        "panel",
        "salud",
        "static",
        "tiendas",
        "www",
    }
)


@dataclass(frozen=True, slots=True)
class Slug:
    valor: str

    def __post_init__(self) -> None:
        largo_valido = LARGO_MINIMO_DE_SLUG <= len(self.valor) <= LARGO_MAXIMO_DE_SLUG
        if not largo_valido or not PATRON_DE_SLUG.fullmatch(self.valor):
            raise SlugInvalido(
                f"'{self.valor}' no es un slug válido: de 3 a 40 caracteres entre a-z, 0-9 y "
                "guiones, sin guion al principio, al final ni dos seguidos"
            )
        if self.valor in SLUGS_RESERVADOS:
            raise SlugReservado(f"'{self.valor}' es una palabra reservada")

    def __str__(self) -> str:
        return self.valor
