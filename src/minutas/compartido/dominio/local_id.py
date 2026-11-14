"""Identificador del local, el tenant dueño de cada dato de negocio."""

from dataclasses import dataclass

from minutas.compartido.dominio.identificador import Identificador


@dataclass(frozen=True, slots=True)
class LocalId(Identificador):
    """Identifica al local dueño de un dato."""
