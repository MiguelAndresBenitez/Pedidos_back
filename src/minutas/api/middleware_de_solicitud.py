"""Asigna un id a cada solicitud, lo vincula al registro y lo devuelve en la respuesta."""

import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from minutas.compartido.dominio.identificador import Identificador
from minutas.compartido.infraestructura.registro import limpiar_contexto, vincular_contexto

CABECERA_ID_DE_SOLICITUD = "X-Request-ID"
PATRON_ID_DE_SOLICITUD = re.compile(r"[A-Za-z0-9._-]{1,64}")


def obtener_id_de_solicitud(cabeceras: Headers) -> str:
    recibido = cabeceras.get(CABECERA_ID_DE_SOLICITUD, "")
    if PATRON_ID_DE_SOLICITUD.fullmatch(recibido):
        return recibido
    return str(Identificador.generar())


class MiddlewareDeSolicitud:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        id_de_solicitud = obtener_id_de_solicitud(Headers(scope=scope))
        limpiar_contexto()
        vincular_contexto(request_id=id_de_solicitud)

        async def enviar_con_id(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                MutableHeaders(scope=mensaje).append(CABECERA_ID_DE_SOLICITUD, id_de_solicitud)
            await send(mensaje)

        await self._app(scope, receive, enviar_con_id)
