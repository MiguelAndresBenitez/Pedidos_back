"""Datos del local que edita su admin, validados juntos."""

from dataclasses import dataclass

from minutas.locales.dominio.color import Color
from minutas.locales.dominio.errores import DatoDelLocalInvalido
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.whatsapp import Whatsapp

LARGO_MAXIMO_DE_NOMBRE = 80
LARGO_MAXIMO_DE_DESCRIPCION = 500
LARGO_MAXIMO_DE_DIRECCION = 200


def asegurar_texto(campo: str, valor: str | None, largo_maximo: int) -> None:
    if valor is not None and (valor != valor.strip() or not valor or len(valor) > largo_maximo):
        raise DatoDelLocalInvalido(
            f"El campo {campo} tiene que tener entre 1 y {largo_maximo} caracteres, "
            "sin espacios al principio ni al final"
        )


@dataclass(frozen=True, slots=True)
class DatosDelLocal:
    nombre: str
    descripcion: str | None
    direccion: str | None
    whatsapp: Whatsapp
    color: Color
    modalidades: frozenset[Modalidad]

    def __post_init__(self) -> None:
        asegurar_texto("nombre", self.nombre, LARGO_MAXIMO_DE_NOMBRE)
        asegurar_texto("descripcion", self.descripcion, LARGO_MAXIMO_DE_DESCRIPCION)
        asegurar_texto("direccion", self.direccion, LARGO_MAXIMO_DE_DIRECCION)
        if not self.modalidades:
            raise DatoDelLocalInvalido("El local tiene que ofrecer delivery, retiro o ambos")
