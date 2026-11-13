# Tarea 9: Agregado Local

**Archivos:**
- Crear: `src/minutas/locales/dominio/datos_del_local.py`
- Crear: `src/minutas/locales/dominio/local.py`
- Test: `tests/unitarios/locales/test_local.py`

---

## Decisiones de diseño

**¿Por qué atributos privados y propiedades?**
- Todo cambio pasa por un método del agregado, que valida. Las propiedades permiten leer (repositorio, casos de uso) sin poder asignar.
- `version` también es de solo lectura: el único que la avanza es el repositorio, con `registrar_guardado()`, después de guardar (bloqueo optimista, tarea 14).

**¿Cómo se aplica la suspensión?**
- `Local.asegurar_modificable()` delega en el estado: la regla vive en un solo lugar. Los métodos del panel empiezan llamándolo, y un caso de uso que necesite verificarlo antes de un efecto (subir una imagen, tarea 12) llama al del agregado, no al del estado. Los métodos de la consola (cambiar slug o zona, suspender, reactivar) no lo llaman, a propósito, y están agrupados bajo un comentario que lo dice.

**¿Qué devuelven los cambios de corte y de zona?**
- La jornada desde la que rigen. La consola la muestra sin navegar por dentro del agregado. `zona_horaria_en(ahora)` dice qué zona rige en un instante.

**¿Por qué `esta_abierto` es una sola expresión?**
- Estado, cierre manual y horario contestan cada uno lo suyo; el resultado es la conjunción. El momento se calcula en la zona que rige en ese instante (`jornada.reglas_en(ahora).zona`).

**¿Cuándo se validan las franjas contra la hora de corte?**
- Al reemplazar el horario y al cambiar el corte o la zona. Mientras haya un cambio pendiente, contra los dos cortes. Esos métodos reciben `ahora` para consolidar antes un cambio que ya rige.

**`DatosDelLocal`** agrupa lo que edita el admin y se valida entero. **`crear_local`** es el alta del owner: reglas por defecto (Buenos Aires, 06:00), sin horario ni cierre, activo y en versión 0.

La próxima apertura se suma en la tarea 10.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_local.py`:

```python
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

import pytest

from minutas.locales.dominio.cierre_manual import CierreHastaNuevoAviso, CierrePorJornada, SinCierre
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import (
    DatoDelLocalInvalido,
    FranjaCortaLaHoraDeCorte,
    LocalSuspendido,
)
from minutas.locales.dominio.estado_del_local import Activo, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.jornada import JornadaConCambioPendiente, JornadaFija
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria

# Viernes 6/11/2026 a las 21:00 en Buenos Aires (UTC-3).
VIERNES_21 = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
NOCHES = Horario(tuple(FranjaHoraria(dia, time(19), time(1)) for dia in DiaDeLaSemana))
LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


@pytest.fixture
def local() -> Local:
    local = crear_local(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )
    local.reemplazar_horario(NOCHES, VIERNES_21)
    return local


def test_crear_local_usa_los_valores_por_defecto() -> None:
    local = crear_local(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )

    assert local.id.valor.version == 7
    assert local.version == 0
    assert local.estado == Activo()
    assert local.cierre_manual == SinCierre()
    assert local.horario == Horario.vacio()
    assert local.jornada == JornadaFija(ReglasDeJornada.por_defecto())
    assert local.datos.color.hexadecimal == "#000000"
    assert local.imagenes == {}


@pytest.mark.parametrize("nombre", ["", " La Esquina", "x" * 81])
def test_crear_local_con_nombre_invalido_falla(nombre: str) -> None:
    with pytest.raises(DatoDelLocalInvalido, match="nombre"):
        crear_local(
            Slug("la-esquina"), nombre, Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
        )


def test_crear_local_sin_modalidades_falla() -> None:
    with pytest.raises(DatoDelLocalInvalido, match="delivery, retiro o ambos"):
        crear_local(Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset())


@pytest.mark.parametrize(
    ("horas_despues", "abierto"), [(-3, False), (0, True), (3, True), (4, False)]
)
def test_esta_abierto_sigue_el_horario_en_la_hora_local(
    local: Local, horas_despues: int, abierto: bool
) -> None:
    assert local.esta_abierto(VIERNES_21 + timedelta(hours=horas_despues)) is abierto


def test_cerrar_por_hoy_cierra_hasta_la_proxima_jornada(local: Local) -> None:
    local.cerrar_por_hoy(VIERNES_21)

    assert local.cierre_manual == CierrePorJornada(local.jornada_de(VIERNES_21))
    assert not local.esta_abierto(VIERNES_21 + timedelta(hours=3))
    assert local.esta_abierto(VIERNES_21 + timedelta(days=1))


def test_cerrar_hasta_nuevo_aviso_cierra_hasta_reabrir(local: Local) -> None:
    local.cerrar_hasta_nuevo_aviso()

    assert local.cierre_manual == CierreHastaNuevoAviso()
    assert not local.esta_abierto(VIERNES_21 + timedelta(days=7))

    local.reabrir()

    assert local.esta_abierto(VIERNES_21)


def test_suspender_cierra_y_reactivar_reabre(local: Local) -> None:
    local.suspender()

    assert local.estado == Suspendido()
    assert not local.esta_abierto(VIERNES_21)

    local.reactivar()

    assert local.esta_abierto(VIERNES_21)


def test_reemplazar_horario_que_corta_la_hora_de_corte_falla(local: Local) -> None:
    horario = Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(20), time(8)),))

    with pytest.raises(FranjaCortaLaHoraDeCorte):
        local.reemplazar_horario(horario, VIERNES_21)

    assert local.horario == NOCHES


def test_cambiar_hora_de_corte_rige_desde_la_proxima_jornada(local: Local) -> None:
    desde = local.cambiar_hora_de_corte(time(2), VIERNES_21)

    assert desde == local.jornada_de(VIERNES_21) + timedelta(days=1)

    assert local.jornada == JornadaConCambioPendiente(
        ReglasDeJornada.por_defecto(),
        ReglasDeJornada.por_defecto().con_corte(time(2)),
        local.jornada_de(VIERNES_21) + timedelta(days=1),
    )


def test_cambiar_hora_de_corte_que_cortaria_una_franja_falla(local: Local) -> None:
    with pytest.raises(FranjaCortaLaHoraDeCorte, match="00:30"):
        local.cambiar_hora_de_corte(time(0, 30), VIERNES_21)

    assert local.jornada == JornadaFija(ReglasDeJornada.por_defecto())


def test_cambiar_zona_horaria_queda_pendiente_y_funciona_suspendido(local: Local) -> None:
    local.suspender()

    local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), VIERNES_21)

    assert local.jornada.reglas_destino.zona == ZonaHoraria("America/Santiago")


def test_cambiar_imagen_no_devuelve_la_anterior(local: Local) -> None:
    local.cambiar_imagen(TipoDeImagen.LOGO, LOGO)

    assert local.imagenes == {TipoDeImagen.LOGO: LOGO}


@pytest.mark.parametrize(
    "modificar",
    [
        lambda local: local.actualizar_datos(replace(local.datos, nombre="Otro")),
        lambda local: local.reemplazar_horario(Horario.vacio(), VIERNES_21),
        lambda local: local.cambiar_hora_de_corte(time(5), VIERNES_21),
        lambda local: local.cerrar_por_hoy(VIERNES_21),
        lambda local: local.cerrar_hasta_nuevo_aviso(),
        lambda local: local.reabrir(),
        lambda local: local.cambiar_imagen(TipoDeImagen.PORTADA, LOGO),
    ],
)
def test_modificar_desde_el_panel_un_local_suspendido_falla(
    local: Local, modificar: Callable[[Local], object]
) -> None:
    local.suspender()

    with pytest.raises(LocalSuspendido):
        modificar(local)


def test_cambiar_slug_funciona_con_el_local_suspendido(local: Local) -> None:
    local.suspender()

    local.cambiar_slug(Slug("esquina-nueva"))

    assert local.slug == Slug("esquina-nueva")


def test_registrar_guardado_avanza_la_version(local: Local) -> None:
    version = local.version

    local.registrar_guardado()

    assert local.version == version + 1


def test_zona_horaria_en_devuelve_la_que_rige_en_ese_instante(local: Local) -> None:
    desde = local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), VIERNES_21)

    assert local.zona_horaria_en(VIERNES_21) == ZonaHoraria("America/Argentina/Buenos_Aires")
    assert local.zona_horaria_en(VIERNES_21 + timedelta(days=2)) == ZonaHoraria("America/Santiago")
    assert desde == local.jornada_de(VIERNES_21) + timedelta(days=1)
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_local.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.local'`

## Paso 3: Implementación

`src/minutas/locales/dominio/datos_del_local.py`:

```python
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
```

`src/minutas/locales/dominio/local.py`:

```python
"""Agregado Local: la tienda, sus datos, sus horarios y si está abierta."""

from collections.abc import Mapping
from datetime import date, datetime, time
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
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_local.py -v && uv run mypy`
Expected: PASS (27 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/datos_del_local.py src/minutas/locales/dominio/local.py tests/unitarios/locales/test_local.py
git commit -m "feat(locales): agregado local con horario, jornada, cierre y suspensión" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
