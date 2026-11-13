"""Número de WhatsApp del local, en el formato que usa el link `wa.me`."""

from dataclasses import dataclass
from typing import Self

import phonenumbers

from minutas.locales.dominio.errores import WhatsappInvalido

REGION_POR_DEFECTO = "AR"
TIPOS_DE_CELULAR = frozenset(
    {phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE}
)
MENSAJE = (
    "'{texto}' no es un celular válido. Escribilo con la característica y el 15, "
    "por ejemplo 0351 15 512-3456, o con el código de país, +54 9 351 512 3456"
)


@dataclass(frozen=True, slots=True)
class Whatsapp:
    """Solo dígitos, con código de país: `5493515123456`."""

    numero: str

    def __post_init__(self) -> None:
        if desde_texto_o_none(f"+{self.numero}") != self.numero:
            raise WhatsappInvalido(MENSAJE.format(texto=self.numero))

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        """Acepta el número como lo escribe una persona; Argentina es la región por defecto."""
        numero = desde_texto_o_none(texto)
        if numero is None:
            raise WhatsappInvalido(MENSAJE.format(texto=texto))
        return cls(numero)


def desde_texto_o_none(texto: str) -> str | None:
    """Interpreta el número con la tabla de numeración de `phonenumbers`; exige un celular."""
    try:
        interpretado = phonenumbers.parse(texto, REGION_POR_DEFECTO)
    except phonenumbers.NumberParseException:
        return None
    valido = phonenumbers.is_valid_number(interpretado) and (
        phonenumbers.number_type(interpretado) in TIPOS_DE_CELULAR
    )
    formato = phonenumbers.format_number(interpretado, phonenumbers.PhoneNumberFormat.E164)
    return formato.removeprefix("+") if valido else None
