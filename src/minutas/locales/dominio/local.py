"""Agregado Local: la tienda, sus datos, sus horarios y si está abierta."""

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from types import MappingProxyType

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.cierre_manual import (
    CierreHastaNuevoAviso,
    CierreManual,
    CierrePorJornada,
    SinCierre,
)
from minutas.locales.dominio.color import COLOR_POR_DEFECTO
from minutas.locales.dominio.datos_del_local import DatosDelLocal
from minutas.locales.dominio.estado_del_local import Activo, EstadoDelLocal, Suspendido
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.jornada import Jornada, JornadaFija
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.momento_de_la_semana import MomentoDeLaSemana
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria

# La próxima apertura se busca en esta ventana: una semana y un día de margen.
DIAS_A_BUSCAR_APERTURA = 8


class Local:
    """Todo cambio pasa por un método: los atributos son privados y se leen por propiedades.

    Los métodos del panel empiezan con `self.asegurar_modificable()`; los de la
    consola del owner (cambiar slug o zona, suspender, reactivar) no, a propósito.
    """

    def __init__(
        self,
        *,
        id: LocalId,
        slug: Slug,
        datos: DatosDelLocal,
        jornada: Jornada,
        horario: Horario,
        cierre_manual: CierreManual,
        imagenes: Mapping[TipoDeImagen, NombreDeImagen],
        estado: EstadoDelLocal,
        version: int,
    ) -> None:
        self._id = id
        self._slug = slug
        self._datos = datos
        self._jornada = jornada
        self._horario = horario
        self._cierre_manual = cierre_manual
        self._imagenes = dict(imagenes)
        self._estado = estado
        self._version = version

    @property
    def id(self) -> LocalId:
        return self._id

    @property
    def slug(self) -> Slug:
        return self._slug

    @property
    def datos(self) -> DatosDelLocal:
        return self._datos

    @property
    def jornada(self) -> Jornada:
        return self._jornada

    @property
    def horario(self) -> Horario:
        return self._horario

    @property
    def cierre_manual(self) -> CierreManual:
        return self._cierre_manual

    @property
    def imagenes(self) -> Mapping[TipoDeImagen, NombreDeImagen]:
        return MappingProxyType(self._imagenes)

    @property
    def estado(self) -> EstadoDelLocal:
        return self._estado

    @property
    def version(self) -> int:
        """Bloqueo optimista: la versión que se leyó. Solo el repositorio la avanza."""
        return self._version

    def registrar_guardado(self) -> None:
        """Lo llama el repositorio después de guardar: la próxima escritura compara con esta."""
        self._version += 1

    def asegurar_modificable(self) -> None:
        """La regla de suspensión vive en el estado; el agregado la expone en un solo lugar."""
        self._estado.asegurar_modificable()

    # Panel del admin

    def actualizar_datos(self, datos: DatosDelLocal) -> None:
        self.asegurar_modificable()
        self._datos = datos

    def reemplazar_horario(self, horario: Horario, ahora: datetime) -> None:
        self.asegurar_modificable()
        jornada = self._jornada.consolidar(ahora)
        _asegurar_horario_compatible(horario, jornada)
        self._jornada = jornada
        self._horario = horario

    def cambiar_hora_de_corte(self, corte: time, ahora: datetime) -> date:
        """Devuelve la jornada desde la que rige el corte nuevo."""
        self.asegurar_modificable()
        return self._programar(self._jornada.reglas_destino.con_corte(corte), ahora)

    def cerrar_por_hoy(self, ahora: datetime) -> None:
        self.asegurar_modificable()
        self._cierre_manual = CierrePorJornada(self.jornada_de(ahora))

    def cerrar_hasta_nuevo_aviso(self) -> None:
        self.asegurar_modificable()
        self._cierre_manual = CierreHastaNuevoAviso()

    def reabrir(self) -> None:
        self.asegurar_modificable()
        self._cierre_manual = SinCierre()

    def cambiar_imagen(self, tipo: TipoDeImagen, nombre: NombreDeImagen) -> None:
        """La imagen anterior no se borra: el nombre nuevo nunca se repite."""
        self.asegurar_modificable()
        self._imagenes = {**self._imagenes, tipo: nombre}

    # Consola del owner: no pasan por `asegurar_modificable`.

    def cambiar_slug(self, slug: Slug) -> None:
        self._slug = slug

    def cambiar_zona_horaria(self, zona: ZonaHoraria, ahora: datetime) -> date:
        """Devuelve la jornada desde la que rige la zona nueva."""
        return self._programar(self._jornada.reglas_destino.con_zona(zona), ahora)

    def suspender(self) -> None:
        self._estado = Suspendido()

    def reactivar(self) -> None:
        self._estado = Activo()

    # Consultas

    def jornada_de(self, ahora: datetime) -> date:
        return self._jornada.jornada_de(ahora)

    def zona_horaria_en(self, ahora: datetime) -> ZonaHoraria:
        """La zona que rige en ese instante: con un cambio pendiente, puede ser la nueva."""
        return self._jornada.reglas_en(ahora).zona

    def esta_abierto(self, ahora: datetime) -> bool:
        """Cada parte contesta la suya: estado, cierre manual y horario."""
        jornada = self._jornada.jornada_de(ahora)
        momento = MomentoDeLaSemana.desde_instante(ahora, self.zona_horaria_en(ahora))
        return (
            self._estado.permite_abrir()
            and self._cierre_manual.permite_abrir(jornada)
            and self._horario.contiene(momento)
        )

    def proxima_apertura(self, ahora: datetime) -> datetime | None:
        """Primer inicio de franja en el que el local abriría; `None` si está abierto ahora."""
        if self.esta_abierto(ahora):
            return None
        candidatas = (
            apertura
            for zona in self._jornada.zonas()
            for apertura in self._aperturas_en(zona, ahora)
            if apertura > ahora and self.esta_abierto(apertura)
        )
        return min(candidatas, default=None)

    def _aperturas_en(self, zona: ZonaHoraria, ahora: datetime) -> list[datetime]:
        desde = ahora.astimezone(zona.info).date()
        return [
            apertura.replace(tzinfo=zona.info).astimezone(UTC)
            for apertura in self._horario.aperturas(desde, DIAS_A_BUSCAR_APERTURA)
        ]

    def _programar(self, nuevas: ReglasDeJornada, ahora: datetime) -> date:
        jornada = self._jornada.programar(nuevas, ahora)
        _asegurar_horario_compatible(self._horario, jornada)
        self._jornada = jornada
        return jornada.desde_jornada


def _asegurar_horario_compatible(horario: Horario, jornada: Jornada) -> None:
    """Mientras haya un cambio pendiente, las franjas respetan los dos cortes."""
    for corte in jornada.cortes():
        horario.asegurar_respeta_corte(corte)


def crear_local(
    slug: Slug, nombre: str, whatsapp: Whatsapp, modalidades: frozenset[Modalidad]
) -> Local:
    """Alta del owner: color, zona y corte por defecto, sin horarios ni cierre."""
    datos = DatosDelLocal(
        nombre=nombre,
        descripcion=None,
        direccion=None,
        whatsapp=whatsapp,
        color=COLOR_POR_DEFECTO,
        modalidades=modalidades,
    )
    return Local(
        id=LocalId.generar(),
        slug=slug,
        datos=datos,
        jornada=JornadaFija(ReglasDeJornada.por_defecto()),
        horario=Horario.vacio(),
        cierre_manual=SinCierre(),
        imagenes={},
        estado=Activo(),
        version=0,
    )
