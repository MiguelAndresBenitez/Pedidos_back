"""Registro estructurado en JSON, con contexto por request."""

import logging
from typing import Any

import structlog

from minutas.compartido.infraestructura.configuracion import NivelDeRegistro


def configurar_registro(nivel: NivelDeRegistro) -> None:
    """Emite una línea JSON por evento en stdout, filtrando por nivel."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[nivel]),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def vincular_contexto(**valores: str) -> None:
    """Agrega valores que aparecen en todas las líneas del request actual."""
    structlog.contextvars.bind_contextvars(**valores)


def limpiar_contexto() -> None:
    structlog.contextvars.clear_contextvars()


def obtener_contexto() -> dict[str, Any]:
    """Valores vinculados al request actual, por ejemplo para incluir request_id en un error."""
    return structlog.contextvars.get_contextvars()
