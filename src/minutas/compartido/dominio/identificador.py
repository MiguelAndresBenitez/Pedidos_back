"""Identificador UUIDv7, base de los ids de todas las entidades."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from uuid_utils.compat import uuid7

from minutas.compartido.dominio.errores import ReglaDeNegocioIncumplida

VERSION_ESPERADA = 7


class IdentificadorInvalido(ReglaDeNegocioIncumplida):
    codigo = "identificador_invalido"


@dataclass(frozen=True, slots=True)
class Identificador:
    """Value object que envuelve un UUIDv7."""

    valor: UUID

    def __post_init__(self) -> None:
        if self.valor.version != VERSION_ESPERADA:
            raise IdentificadorInvalido(
                f"Se esperaba un UUIDv7 y llegó la versión {self.valor.version}"
            )

    @classmethod
    def generar(cls) -> Self:
        return cls(uuid7())

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        try:
            valor = UUID(texto)
        except ValueError as error:
            raise IdentificadorInvalido(f"'{texto}' no es un UUID válido") from error
        return cls(valor)

    def __str__(self) -> str:
        return str(self.valor)
