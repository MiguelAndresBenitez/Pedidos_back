"""Traducción de errores de PostgreSQL a errores de dominio."""

from sqlalchemy.exc import IntegrityError


def viola_restriccion(error: IntegrityError, restriccion: str) -> bool:
    """Si el error lo causó la restricción con ese nombre.

    asyncpg informa el nombre en `constraint_name`; no depende del idioma de los mensajes.
    """
    causa = getattr(error.orig, "__cause__", None)
    return getattr(causa, "constraint_name", None) == restriccion
