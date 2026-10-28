"""Traducción de errores a respuestas application/problem+json (RFC 9457)."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from minutas.api.middleware_de_solicitud import CABECERA_ID_DE_SOLICITUD
from minutas.compartido.dominio.errores import (
    Conflicto,
    ErrorDeDominio,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)
from minutas.compartido.infraestructura.registro import obtener_contexto

TIPO_DE_MEDIO = "application/problem+json"

ESTADOS_POR_CATEGORIA: dict[type[ErrorDeDominio], HTTPStatus] = {
    NoEncontrado: HTTPStatus.NOT_FOUND,
    Conflicto: HTTPStatus.CONFLICT,
    ReglaDeNegocioIncumplida: HTTPStatus.UNPROCESSABLE_ENTITY,
    LimiteExcedido: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorDeDominio: HTTPStatus.BAD_REQUEST,
}

CODIGOS_POR_ESTADO_HTTP: dict[int, str] = {
    HTTPStatus.NOT_FOUND: "ruta_inexistente",
    HTTPStatus.METHOD_NOT_ALLOWED: "metodo_no_permitido",
}


def obtener_estado_por_error(error: ErrorDeDominio) -> HTTPStatus:
    return next(
        ESTADOS_POR_CATEGORIA[clase]
        for clase in type(error).__mro__
        if clase in ESTADOS_POR_CATEGORIA
    )


def crear_problema(
    estado: HTTPStatus,
    codigo: str,
    detalle: str,
    cabeceras: Mapping[str, str] | None = None,
    **extras: Any,
) -> JSONResponse:
    contenido = {
        "type": "about:blank",
        "title": estado.phrase,
        "status": int(estado),
        "detail": detalle,
        "code": codigo,
        "request_id": obtener_contexto().get("request_id"),
        **extras,
    }
    return JSONResponse(
        status_code=estado, content=contenido, media_type=TIPO_DE_MEDIO, headers=cabeceras
    )


async def manejar_error_de_dominio(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(ErrorDeDominio, excepcion)
    return crear_problema(obtener_estado_por_error(error), error.codigo, error.mensaje)


async def manejar_error_http(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(HTTPException, excepcion)
    codigo = CODIGOS_POR_ESTADO_HTTP.get(error.status_code, "error_http")
    return crear_problema(
        HTTPStatus(error.status_code), codigo, str(error.detail), cabeceras=error.headers
    )


async def manejar_solicitud_invalida(_: Request, excepcion: Exception) -> JSONResponse:
    error = cast(RequestValidationError, excepcion)
    return crear_problema(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "solicitud_invalida",
        "La solicitud tiene datos inválidos",
        errores=jsonable_encoder(error.errors()),
    )


async def manejar_error_inesperado(_: Request, excepcion: Exception) -> JSONResponse:
    structlog.get_logger().error("error_no_controlado", exc_info=excepcion)
    respuesta = crear_problema(
        HTTPStatus.INTERNAL_SERVER_ERROR, "error_interno", "Ocurrió un error inesperado"
    )
    respuesta.headers[CABECERA_ID_DE_SOLICITUD] = str(obtener_contexto().get("request_id", ""))
    return respuesta


def registrar_manejadores_de_errores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDeDominio, manejar_error_de_dominio)
    app.add_exception_handler(HTTPException, manejar_error_http)
    app.add_exception_handler(RequestValidationError, manejar_solicitud_invalida)
    app.add_exception_handler(Exception, manejar_error_inesperado)
