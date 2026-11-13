"""Repositorio del local fijado, sobre SQLAlchemy Core, con traducción explícita fila ↔ dominio."""

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, cast

from sqlalchemy import CursorResult, Executable, RowMapping, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from minutas.compartido.dominio.identificador import Identificador
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.errores_de_base import viola_restriccion
from minutas.locales.dominio.cierre_manual import (
    CierreHastaNuevoAviso,
    CierreManual,
    CierrePorJornada,
    SinCierre,
)
from minutas.locales.dominio.color import Color
from minutas.locales.dominio.datos_del_local import DatosDelLocal
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import LocalModificadoEnParalelo, LocalNoEncontrado, SlugEnUso
from minutas.locales.dominio.estado_del_local import Activo, EstadoDelLocal, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.jornada import Jornada, JornadaConCambioPendiente, JornadaFija
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from minutas.locales.infraestructura.tablas import FRANJAS_HORARIAS, LOCALES

RESTRICCION_DE_SLUG = "uq_locales_slug"
MENSAJE_DE_CONFLICTO = "El local cambió mientras lo editabas; volvé a cargarlo e intentá de nuevo"

# El vocabulario de las columnas vive acá, no en el dominio: tablas de despacho en los dos sentidos.
CODIGOS_DE_ESTADO: dict[type[EstadoDelLocal], str] = {Activo: "activo", Suspendido: "suspendido"}
ESTADOS: dict[str, Callable[[], EstadoDelLocal]] = {"activo": Activo, "suspendido": Suspendido}
CODIGOS_DE_CIERRE: dict[type[CierreManual], str | None] = {
    SinCierre: None,
    CierrePorJornada: "por_jornada",
    CierreHastaNuevoAviso: "hasta_nuevo_aviso",
}
CIERRES: dict[str | None, Callable[[date | None], CierreManual]] = {
    None: lambda _jornada: SinCierre(),
    "por_jornada": lambda jornada: CierrePorJornada(cast(date, jornada)),
    "hasta_nuevo_aviso": lambda _jornada: CierreHastaNuevoAviso(),
}


class RepositorioDeLocalesSQLAlchemy:
    """Trabaja solo sobre el local fijado: RLS impide escribir otro."""

    def __init__(self, sesion: AsyncSession, local_id: LocalId) -> None:
        self._sesion = sesion
        self._local_id = local_id
        self._horario_leido: Horario | None = None

    async def obtener(self) -> Local:
        fila = (
            (
                await self._sesion.execute(
                    select(LOCALES).where(LOCALES.c.id == self._local_id.valor)
                )
            )
            .mappings()
            .one_or_none()
        )
        if fila is None:
            raise LocalNoEncontrado("El local no existe")
        franjas = (
            await self._sesion.execute(
                select(FRANJAS_HORARIAS)
                .where(FRANJAS_HORARIAS.c.local_id == self._local_id.valor)
                .order_by(FRANJAS_HORARIAS.c.dia, FRANJAS_HORARIAS.c.apertura)
            )
        ).mappings()
        local = _desde_filas(fila, franjas.all())
        self._horario_leido = local.horario
        return local

    async def agregar(self, local: Local) -> None:
        await self._escribir(insert(LOCALES).values(_a_fila(local)), local.slug)
        await self._insertar_franjas(local)

    async def guardar(self, local: Local) -> None:
        """Bloqueo optimista: solo escribe si nadie guardó el local desde que se leyó."""
        sentencia = (
            update(LOCALES)
            .where(LOCALES.c.id == local.id.valor, LOCALES.c.version == local.version)
            .values({**_a_fila(local), "version": local.version + 1, "actualizado_en": func.now()})
        )
        resultado = await self._escribir(sentencia, local.slug)
        if resultado.rowcount != 1:
            raise LocalModificadoEnParalelo(MENSAJE_DE_CONFLICTO)
        local.registrar_guardado()
        if local.horario != self._horario_leido:
            await self._reemplazar_franjas(local)

    async def _reemplazar_franjas(self, local: Local) -> None:
        """Solo cuando el horario cambió: suspender o cerrar no reescribe las franjas."""
        await self._sesion.execute(
            delete(FRANJAS_HORARIAS).where(FRANJAS_HORARIAS.c.local_id == local.id.valor)
        )
        await self._insertar_franjas(local)
        self._horario_leido = local.horario

    async def _insertar_franjas(self, local: Local) -> None:
        filas = [
            {
                "id": Identificador.generar().valor,
                "local_id": local.id.valor,
                "dia": franja.dia.value,
                "apertura": franja.apertura,
                "cierre": franja.cierre,
            }
            for franja in local.horario.franjas
        ]
        if filas:
            await self._sesion.execute(insert(FRANJAS_HORARIAS), filas)

    async def _escribir(self, sentencia: Executable, slug: Slug) -> CursorResult[Any]:
        try:
            return cast(CursorResult[Any], await self._sesion.execute(sentencia))
        except IntegrityError as error:
            if viola_restriccion(error, RESTRICCION_DE_SLUG):
                raise SlugEnUso(f"El slug '{slug}' ya está en uso") from error
            raise


def _a_fila(local: Local) -> dict[str, Any]:
    datos, jornada, imagenes = local.datos, local.jornada, local.imagenes
    pendiente = _reglas_pendientes(jornada)
    vigentes = jornada.reglas_vigentes
    return {
        "id": local.id.valor,
        "slug": local.slug.valor,
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "direccion": datos.direccion,
        "whatsapp": datos.whatsapp.numero,
        "color": datos.color.hexadecimal,
        "ofrece_delivery": Modalidad.DELIVERY in datos.modalidades,
        "ofrece_retiro": Modalidad.RETIRO in datos.modalidades,
        "zona_horaria": vigentes.zona.nombre,
        "hora_de_corte": vigentes.corte,
        **pendiente,
        "cierre_manual": CODIGOS_DE_CIERRE[type(local.cierre_manual)],
        "cierre_manual_jornada": _jornada_del_cierre(local.cierre_manual),
        "logo": _nombre(imagenes.get(TipoDeImagen.LOGO)),
        "portada": _nombre(imagenes.get(TipoDeImagen.PORTADA)),
        "estado": CODIGOS_DE_ESTADO[type(local.estado)],
        "version": local.version,
    }


def _reglas_pendientes(jornada: Jornada) -> dict[str, Any]:
    pendientes, desde = jornada.cambio_pendiente or (None, None)
    return {
        "zona_horaria_pendiente": pendientes.zona.nombre if pendientes else None,
        "hora_de_corte_pendiente": pendientes.corte if pendientes else None,
        "reglas_desde_jornada": desde,
    }


def _jornada_del_cierre(cierre: CierreManual) -> date | None:
    return cierre.jornada if isinstance(cierre, CierrePorJornada) else None


def _nombre(nombre: NombreDeImagen | None) -> str | None:
    return None if nombre is None else nombre.valor


def _jornada_desde_fila(fila: RowMapping) -> Jornada:
    vigentes = ReglasDeJornada(ZonaHoraria(fila["zona_horaria"]), fila["hora_de_corte"])
    if fila["reglas_desde_jornada"] is None:
        return JornadaFija(vigentes)
    pendientes = ReglasDeJornada(
        ZonaHoraria(fila["zona_horaria_pendiente"]), fila["hora_de_corte_pendiente"]
    )
    return JornadaConCambioPendiente(vigentes, pendientes, fila["reglas_desde_jornada"])


def _desde_filas(fila: RowMapping, franjas: Sequence[RowMapping]) -> Local:
    modalidades = {
        Modalidad.DELIVERY: fila["ofrece_delivery"],
        Modalidad.RETIRO: fila["ofrece_retiro"],
    }
    datos = DatosDelLocal(
        nombre=fila["nombre"],
        descripcion=fila["descripcion"],
        direccion=fila["direccion"],
        whatsapp=Whatsapp(fila["whatsapp"]),
        color=Color(fila["color"]),
        modalidades=frozenset(modalidad for modalidad, ofrece in modalidades.items() if ofrece),
    )
    horario = Horario(
        tuple(
            FranjaHoraria(DiaDeLaSemana(franja["dia"]), franja["apertura"], franja["cierre"])
            for franja in franjas
        )
    )
    imagenes = {tipo: NombreDeImagen(fila[tipo.value]) for tipo in TipoDeImagen if fila[tipo.value]}
    return Local(
        id=LocalId(fila["id"]),
        slug=Slug(fila["slug"]),
        datos=datos,
        jornada=_jornada_desde_fila(fila),
        horario=horario,
        cierre_manual=CIERRES[fila["cierre_manual"]](fila["cierre_manual_jornada"]),
        imagenes=imagenes,
        estado=ESTADOS[fila["estado"]](),
        version=fila["version"],
    )
