"""Errores de dominio, agrupados por categoría.

Cada error concreto hereda de una categoría y redefine `codigo`. El borde HTTP
traduce la categoría a un estado; el dominio no conoce HTTP.
"""

from typing import ClassVar


class ErrorDeDominio(Exception):
    """Base de todos los errores que el dominio lanza a propósito."""

    codigo: ClassVar[str] = "error_de_dominio"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorDeDominio):
    """Lo pedido no existe o no pertenece al local."""

    codigo = "no_encontrado"


class Conflicto(ErrorDeDominio):
    """La operación choca con el estado actual de los datos."""

    codigo = "conflicto"


class ReglaDeNegocioIncumplida(ErrorDeDominio):
    """Los datos son válidos en forma, pero el negocio no lo permite."""

    codigo = "regla_de_negocio_incumplida"


class LimiteExcedido(ErrorDeDominio):
    """Se superó un límite de uso."""

    codigo = "limite_excedido"
