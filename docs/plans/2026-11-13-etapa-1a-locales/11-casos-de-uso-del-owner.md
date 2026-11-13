# Tarea 11: Puertos, unidades de trabajo y casos de uso del owner

**Archivos:**
- Crear: `src/minutas/locales/aplicacion/repositorio_de_locales.py`
- Crear: `src/minutas/locales/aplicacion/directorio_de_locales.py`
- Crear: `src/minutas/locales/aplicacion/unidades_de_trabajo.py`
- Crear: `src/minutas/locales/aplicacion/almacen_de_imagenes.py`
- Crear: `src/minutas/locales/aplicacion/lector_de_imagenes.py`
- Crear: `src/minutas/locales/aplicacion/locales_por_slug.py`
- Crear: `src/minutas/locales/aplicacion/vista_de_tienda.py`
- Crear: `src/minutas/locales/aplicacion/dar_de_alta_local.py`
- Crear: `src/minutas/locales/aplicacion/cambiar_slug.py`
- Crear: `src/minutas/locales/aplicacion/cambiar_zona_horaria.py`
- Crear: `src/minutas/locales/aplicacion/suspender_local.py`
- Crear: `src/minutas/locales/aplicacion/reactivar_local.py`
- Crear: `src/minutas/locales/aplicacion/obtener_tienda.py`
- Crear: `tests/soporte/locales_en_memoria.py`
- Crear: `tests/soporte/imagenes_en_memoria.py`
- Test: `tests/unitarios/locales/test_casos_de_uso_del_owner.py`

---

## Decisiones de diseño

**¿Por qué dos unidades de trabajo en Locales?**
- `UnidadDeTrabajoDelLocal` fija `app.local_id` y expone el repositorio, que trabaja solo sobre ese local: `obtener`, `agregar`, `guardar`. `UnidadDeTrabajoDelDirectorio` no fija nada y solo resuelve slugs. Así, toda escritura tiene el local fijado, como pide el diseño.
- Las fábricas son `Callable[[LocalId], ...]` y `Callable[[], ...]`: la API y la consola pasan las de SQLAlchemy, los tests las de memoria.

**¿Por qué `LocalesPorSlug`?**
- Los casos de uso del owner y la tienda reciben un slug: el directorio lo resuelve y la unidad del local carga el local. `LocalesPorSlug` concentra esos dos pasos (`obtener` y `modificar`, que devuelve lo que devuelva el cambio), y cada caso de uso recibe solo ese colaborador y dice qué cambia. Si el slug cambia entre los dos pasos, la respuesta es "no existe": la carrera es inofensiva.

**¿Qué devuelve `ObtenerTienda`?**
- Una vista de lectura de la aplicación, no el agregado: `TiendaDisponible`, con todo ya calculado con `ahora` (abierto ahora, próxima apertura, zona que rige, URLs de las imágenes), o `TiendaNoDisponible`. La variante la decide el estado del local con una tabla de despacho por tipo (`VISTAS_POR_ESTADO`). La API solo la traduce (tarea 17).

**Los puertos de imágenes entran acá** (`AlmacenDeImagenes`, para guardar y dar la URL pública, y `LectorDeImagenes`, para que la API sirva el archivo) porque la tienda arma las URLs. Sus adaptadores están en la tarea 15.

**¿Cómo se hace el alta con RLS?**
- El id se genera en el dominio (`crear_local`) y la unidad se abre con ese id, así el `INSERT` cumple la política `alta_propia`.

**¿Qué reproducen los dobles en memoria?**
- La transacción (lo no confirmado no se ve), el RLS (el repositorio ve solo el local fijado), la unicidad del slug y el bloqueo optimista: `guardar` incrementa la versión y falla con `LocalModificadoEnParalelo` si otro guardó antes. El último test es el caso "el owner suspende mientras el admin edita".

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_casos_de_uso_del_owner.py`:

```python
from datetime import UTC, date, datetime

import pytest

from minutas.locales.aplicacion.cambiar_slug import CambiarSlug
from minutas.locales.aplicacion.cambiar_zona_horaria import CambiarZonaHoraria
from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.aplicacion.obtener_tienda import ObtenerTienda
from minutas.locales.aplicacion.reactivar_local import ReactivarLocal
from minutas.locales.aplicacion.suspender_local import SuspenderLocal
from minutas.locales.aplicacion.vista_de_tienda import TiendaDisponible, TiendaNoDisponible
from minutas.locales.dominio.errores import (
    LocalModificadoEnParalelo,
    LocalNoEncontrado,
    SlugEnUso,
)
from minutas.locales.dominio.estado_del_local import Activo, Suspendido
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from soporte.imagenes_en_memoria import AlmacenDeImagenesEnMemoria
from soporte.locales_en_memoria import BaseDeLocalesEnMemoria

# Viernes 6/11/2026 a las 12:00 en Buenos Aires.
AHORA = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


@pytest.fixture
def base() -> BaseDeLocalesEnMemoria:
    return BaseDeLocalesEnMemoria()


@pytest.fixture
def por_slug(base: BaseDeLocalesEnMemoria) -> LocalesPorSlug:
    return LocalesPorSlug(base.crear_unidad_del_directorio, base.crear_unidad_del_local)


async def dar_de_alta(base: BaseDeLocalesEnMemoria, slug: str = "la-esquina") -> Local:
    return await DarDeAltaLocal(base.crear_unidad_del_local).ejecutar(
        Slug(slug), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )


async def test_dar_de_alta_local_lo_guarda(base: BaseDeLocalesEnMemoria) -> None:
    local = await dar_de_alta(base)

    assert base.locales[local.id].slug == Slug("la-esquina")


async def test_dar_de_alta_local_con_slug_en_uso_falla(base: BaseDeLocalesEnMemoria) -> None:
    await dar_de_alta(base)

    with pytest.raises(SlugEnUso, match="la-esquina"):
        await dar_de_alta(base)

    assert len(base.locales) == 1


async def test_cambiar_slug_lo_reemplaza(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    local = await dar_de_alta(base)

    await CambiarSlug(por_slug).ejecutar(Slug("la-esquina"), Slug("esquina-centro"))

    assert base.locales[local.id].slug == Slug("esquina-centro")


async def test_cambiar_slug_a_uno_en_uso_falla(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    await dar_de_alta(base)
    await dar_de_alta(base, "el-rincon")

    with pytest.raises(SlugEnUso):
        await CambiarSlug(por_slug).ejecutar(Slug("el-rincon"), Slug("la-esquina"))


async def test_cambiar_slug_de_local_inexistente_falla(por_slug: LocalesPorSlug) -> None:
    with pytest.raises(LocalNoEncontrado, match="no-existe"):
        await CambiarSlug(por_slug).ejecutar(Slug("no-existe"), Slug("otro"))


async def test_cambiar_zona_horaria_devuelve_desde_cuando_rige(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    local = await dar_de_alta(base)

    desde = await CambiarZonaHoraria(por_slug).ejecutar(
        Slug("la-esquina"), ZonaHoraria("America/Santiago"), AHORA
    )

    assert desde == date(2026, 11, 7)
    assert base.locales[local.id].jornada.reglas_destino.zona == ZonaHoraria("America/Santiago")


async def test_suspender_y_reactivar_local_cambian_su_estado(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    local = await dar_de_alta(base)

    await SuspenderLocal(por_slug).ejecutar(Slug("la-esquina"))
    assert base.locales[local.id].estado == Suspendido()

    await ReactivarLocal(por_slug).ejecutar(Slug("la-esquina"))
    assert base.locales[local.id].estado == Activo()


async def test_obtener_tienda_activa_devuelve_la_vista_disponible(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    await dar_de_alta(base)

    vista = await ObtenerTienda(por_slug, AlmacenDeImagenesEnMemoria()).ejecutar(
        Slug("la-esquina"), AHORA
    )

    assert isinstance(vista, TiendaDisponible)
    assert (vista.slug, vista.abierto_ahora, vista.proxima_apertura) == ("la-esquina", False, None)
    assert vista.zona_horaria == "America/Argentina/Buenos_Aires"


async def test_obtener_tienda_suspendida_devuelve_la_vista_no_disponible(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    await dar_de_alta(base)
    await SuspenderLocal(por_slug).ejecutar(Slug("la-esquina"))

    vista = await ObtenerTienda(por_slug, AlmacenDeImagenesEnMemoria()).ejecutar(
        Slug("la-esquina"), AHORA
    )

    assert vista == TiendaNoDisponible("la-esquina")


async def test_guardar_un_local_que_otro_guardo_antes_falla(
    base: BaseDeLocalesEnMemoria, por_slug: LocalesPorSlug
) -> None:
    local = await dar_de_alta(base)
    edicion_del_admin = base.crear_unidad_del_local(local.id)
    leido_por_el_admin = await edicion_del_admin.locales.obtener()

    await SuspenderLocal(por_slug).ejecutar(Slug("la-esquina"))

    with pytest.raises(LocalModificadoEnParalelo):
        await edicion_del_admin.locales.guardar(leido_por_el_admin)
    assert base.locales[local.id].estado == Suspendido()
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_casos_de_uso_del_owner.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.aplicacion.cambiar_slug'`

## Paso 3: Implementación

`src/minutas/locales/aplicacion/repositorio_de_locales.py`:

```python
"""Puerto del repositorio de locales. Trabaja sobre el local fijado en la unidad de trabajo."""

from typing import Protocol

from minutas.locales.dominio.local import Local


class RepositorioDeLocales(Protocol):
    async def obtener(self) -> Local:
        """El local fijado, con sus franjas. Lanza `LocalNoEncontrado`."""
        ...

    async def agregar(self, local: Local) -> None:
        """Lanza `SlugEnUso` si otro local ya tiene ese slug."""
        ...

    async def guardar(self, local: Local) -> None:
        """Bloqueo optimista: lanza `LocalModificadoEnParalelo` si cambió desde que se leyó.

        Lanza `SlugEnUso` si otro local ya tiene ese slug. Incrementa `local.version`.
        """
        ...
```

`src/minutas/locales/aplicacion/directorio_de_locales.py`:

```python
"""Puerto del directorio de locales: resuelve un slug sin tener un local fijado."""

from typing import Protocol

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.slug import Slug


class DirectorioDeLocales(Protocol):
    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        """Lanza `LocalNoEncontrado`."""
        ...
```

`src/minutas/locales/aplicacion/unidades_de_trabajo.py`:

```python
"""Unidades de trabajo del contexto Locales: la del local (con RLS) y la del directorio."""

from collections.abc import Callable
from typing import Protocol

from minutas.compartido.aplicacion.unidad_de_trabajo import (
    UnidadDeTrabajo,
    UnidadDeTrabajoDePlataforma,
)
from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.directorio_de_locales import DirectorioDeLocales
from minutas.locales.aplicacion.repositorio_de_locales import RepositorioDeLocales


class UnidadDeTrabajoDelLocal(UnidadDeTrabajo, Protocol):
    """Fija `app.local_id`: toda escritura del local pasa por acá."""

    @property
    def locales(self) -> RepositorioDeLocales: ...


class UnidadDeTrabajoDelDirectorio(UnidadDeTrabajoDePlataforma, Protocol):
    """Sin local fijado: solo resuelve slugs, de solo lectura."""

    @property
    def directorio(self) -> DirectorioDeLocales: ...


type FabricaDeUnidadesDelLocal = Callable[[LocalId], UnidadDeTrabajoDelLocal]
type FabricaDeUnidadesDelDirectorio = Callable[[], UnidadDeTrabajoDelDirectorio]
```

`src/minutas/locales/aplicacion/almacen_de_imagenes.py`:

```python
"""Puerto del almacén de imágenes de los locales."""

from typing import Protocol

from minutas.locales.dominio.imagen import NombreDeImagen


class AlmacenDeImagenes(Protocol):
    async def guardar(self, contenido: bytes) -> NombreDeImagen:
        """Guarda una imagen WebP con un nombre nuevo y único."""
        ...

    def obtener_url_publica(self, nombre: NombreDeImagen) -> str:
        """URL completa con la que el front muestra la imagen."""
        ...
```

`src/minutas/locales/aplicacion/lector_de_imagenes.py`:

```python
"""Puerto para servir imágenes guardadas en disco: lo usa la API, no los casos de uso."""

from pathlib import Path
from typing import Protocol

from minutas.locales.dominio.imagen import NombreDeImagen


class LectorDeImagenes(Protocol):
    async def obtener_ruta(self, nombre: NombreDeImagen) -> Path:
        """Lanza `ImagenNoEncontrada` si no existe."""
        ...
```

`src/minutas/locales/aplicacion/locales_por_slug.py`:

```python
"""Acceso a un local por su slug: el directorio lo resuelve y la unidad del local lo carga."""

from collections.abc import Callable

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import (
    FabricaDeUnidadesDelDirectorio,
    FabricaDeUnidadesDelLocal,
)
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class LocalesPorSlug:
    """Colaborador de los casos de uso que reciben un slug (consola del owner y tienda)."""

    def __init__(
        self,
        crear_unidad_del_directorio: FabricaDeUnidadesDelDirectorio,
        crear_unidad_del_local: FabricaDeUnidadesDelLocal,
    ) -> None:
        self._crear_unidad_del_directorio = crear_unidad_del_directorio
        self._crear_unidad_del_local = crear_unidad_del_local

    async def obtener(self, slug: Slug) -> Local:
        """Dos pasos de solo lectura. Si el slug cambia en el medio, responde que no existe."""
        async with self._crear_unidad_del_local(await self._resolver(slug)) as unidad:
            return await unidad.locales.obtener()

    async def modificar[T](self, slug: Slug, cambio: Callable[[Local], T]) -> T:
        """Aplica el cambio en una transacción del local y devuelve lo que el cambio devuelva."""
        async with self._crear_unidad_del_local(await self._resolver(slug)) as unidad:
            local = await unidad.locales.obtener()
            resultado = cambio(local)
            await unidad.locales.guardar(local)
            await unidad.confirmar()
        return resultado

    async def _resolver(self, slug: Slug) -> LocalId:
        async with self._crear_unidad_del_directorio() as unidad:
            return await unidad.directorio.obtener_local_id_por_slug(slug)
```

`src/minutas/locales/aplicacion/vista_de_tienda.py`:

```python
"""Modelo de lectura de la tienda pública: todo lo que muestra, ya calculado."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from minutas.locales.dominio.estado_del_local import Activo, EstadoDelLocal, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad

type UrlDeImagen = Callable[[NombreDeImagen], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class TiendaDisponible:
    slug: str
    nombre: str
    descripcion: str | None
    direccion: str | None
    whatsapp: str
    color: str
    modalidades: tuple[Modalidad, ...]
    zona_horaria: str
    franjas: tuple[FranjaHoraria, ...]
    logo_url: str | None
    portada_url: str | None
    abierto_ahora: bool
    proxima_apertura: datetime | None


@dataclass(frozen=True, slots=True)
class TiendaNoDisponible:
    """Un local suspendido: la tienda no dice por qué."""

    slug: str


type VistaDeTienda = TiendaDisponible | TiendaNoDisponible


def _url(local: Local, tipo: TipoDeImagen, url_de: UrlDeImagen) -> str | None:
    nombre = local.imagenes.get(tipo)
    return None if nombre is None else url_de(nombre)


def _disponible(local: Local, ahora: datetime, url_de: UrlDeImagen) -> VistaDeTienda:
    datos = local.datos
    return TiendaDisponible(
        slug=local.slug.valor,
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        direccion=datos.direccion,
        whatsapp=datos.whatsapp.numero,
        color=datos.color.hexadecimal,
        modalidades=tuple(sorted(datos.modalidades)),
        zona_horaria=local.zona_horaria_en(ahora).nombre,
        franjas=local.horario.franjas,
        logo_url=_url(local, TipoDeImagen.LOGO, url_de),
        portada_url=_url(local, TipoDeImagen.PORTADA, url_de),
        abierto_ahora=local.esta_abierto(ahora),
        proxima_apertura=local.proxima_apertura(ahora),
    )


def _no_disponible(local: Local, _ahora: datetime, _url_de: UrlDeImagen) -> VistaDeTienda:
    return TiendaNoDisponible(local.slug.valor)


VISTAS_POR_ESTADO: dict[
    type[EstadoDelLocal], Callable[[Local, datetime, UrlDeImagen], VistaDeTienda]
] = {
    Activo: _disponible,
    Suspendido: _no_disponible,
}


def crear_vista_de_tienda(local: Local, ahora: datetime, url_de: UrlDeImagen) -> VistaDeTienda:
    """La variante la decide el estado del local, con una tabla de despacho."""
    return VISTAS_POR_ESTADO[type(local.estado)](local, ahora, url_de)
```

`src/minutas/locales/aplicacion/dar_de_alta_local.py`:

```python
"""Caso de uso del owner: dar de alta un local."""

from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp


class DarDeAltaLocal:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(
        self, slug: Slug, nombre: str, whatsapp: Whatsapp, modalidades: frozenset[Modalidad]
    ) -> Local:
        """El id se genera en el dominio y se fija antes del INSERT, como pide RLS."""
        local = crear_local(slug, nombre, whatsapp, modalidades)
        async with self._crear_unidad(local.id) as unidad:
            await unidad.locales.agregar(local)
            await unidad.confirmar()
        return local
```

`src/minutas/locales/aplicacion/cambiar_slug.py`:

```python
"""Caso de uso del owner: cambiar el link de la tienda. Los links viejos dejan de funcionar."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.slug import Slug


class CambiarSlug:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug, nuevo: Slug) -> None:
        await self._locales.modificar(slug, lambda local: local.cambiar_slug(nuevo))
```

`src/minutas/locales/aplicacion/cambiar_zona_horaria.py`:

```python
"""Caso de uso del owner: cambiar la zona horaria. Rige desde la próxima jornada."""

from datetime import date, datetime

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.zona_horaria import ZonaHoraria


class CambiarZonaHoraria:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug, zona: ZonaHoraria, ahora: datetime) -> date:
        """Devuelve la jornada desde la que rige la zona nueva."""
        return await self._locales.modificar(
            slug, lambda local: local.cambiar_zona_horaria(zona, ahora)
        )
```

`src/minutas/locales/aplicacion/suspender_local.py`:

```python
"""Caso de uso del owner: suspender un local, por ejemplo por falta de pago."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class SuspenderLocal:
    """Los datos no se tocan: reactivar lo deja como estaba."""

    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug) -> None:
        await self._locales.modificar(slug, Local.suspender)
```

`src/minutas/locales/aplicacion/reactivar_local.py`:

```python
"""Caso de uso del owner: reactivar un local suspendido. Sus datos quedaron intactos."""

from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class ReactivarLocal:
    def __init__(self, locales: LocalesPorSlug) -> None:
        self._locales = locales

    async def ejecutar(self, slug: Slug) -> None:
        await self._locales.modificar(slug, Local.reactivar)
```

`src/minutas/locales/aplicacion/obtener_tienda.py`:

```python
"""Consulta pública: la tienda detrás de un slug, lista para mostrar."""

from datetime import datetime

from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.aplicacion.vista_de_tienda import VistaDeTienda, crear_vista_de_tienda
from minutas.locales.dominio.slug import Slug


class ObtenerTienda:
    def __init__(self, locales: LocalesPorSlug, almacen: AlmacenDeImagenes) -> None:
        self._locales = locales
        self._almacen = almacen

    async def ejecutar(self, slug: Slug, ahora: datetime) -> VistaDeTienda:
        local = await self._locales.obtener(slug)
        return crear_vista_de_tienda(local, ahora, self._almacen.obtener_url_publica)
```

`tests/soporte/locales_en_memoria.py`:

```python
"""Dobles en memoria del contexto Locales: transacciones, RLS y bloqueo optimista como la base."""

from copy import deepcopy
from types import TracebackType
from typing import Self

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.errores import LocalModificadoEnParalelo, LocalNoEncontrado, SlugEnUso
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class BaseDeLocalesEnMemoria:
    """Estado confirmado. Cada unidad de trabajo trabaja sobre una copia que aplica al confirmar."""

    def __init__(self) -> None:
        self.locales: dict[LocalId, Local] = {}

    def crear_unidad_del_local(self, local_id: LocalId) -> "UnidadDelLocalEnMemoria":
        return UnidadDelLocalEnMemoria(self, local_id)

    def crear_unidad_del_directorio(self) -> "UnidadDelDirectorioEnMemoria":
        return UnidadDelDirectorioEnMemoria(self)


class _Transaccion:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        return None


class RepositorioDeLocalesEnMemoria:
    """Ve solo el local fijado, como el repositorio real con RLS."""

    def __init__(self, base: BaseDeLocalesEnMemoria, local_id: LocalId) -> None:
        self._base = base
        self._local_id = local_id
        self.pendiente: Local | None = None
        self.version_leida: int | None = None

    async def obtener(self) -> Local:
        guardado = self._base.locales.get(self._local_id)
        if guardado is None:
            raise LocalNoEncontrado("El local no existe")
        self.version_leida = guardado.version
        return deepcopy(guardado)

    async def agregar(self, local: Local) -> None:
        assert local.id == self._local_id, "RLS: solo se inserta el local fijado"
        self._asegurar_slug_libre(local)
        self.pendiente = deepcopy(local)

    async def guardar(self, local: Local) -> None:
        guardado = self._base.locales.get(local.id)
        if guardado is None:
            raise LocalNoEncontrado("El local no existe")
        if guardado.version != local.version:
            raise LocalModificadoEnParalelo("El local cambió mientras lo editabas")
        self._asegurar_slug_libre(local)
        local.registrar_guardado()
        self.pendiente = deepcopy(local)

    def _asegurar_slug_libre(self, local: Local) -> None:
        if any(
            otro.slug == local.slug and otro.id != local.id for otro in self._base.locales.values()
        ):
            raise SlugEnUso(f"El slug '{local.slug}' ya está en uso")


class UnidadDelLocalEnMemoria(_Transaccion):
    def __init__(self, base: BaseDeLocalesEnMemoria, local_id: LocalId) -> None:
        self._base = base
        self.local_id = local_id
        self.locales = RepositorioDeLocalesEnMemoria(base, local_id)

    async def confirmar(self) -> None:
        """Aplica el cambio, salvo que otra unidad haya guardado el local antes (como el UPDATE)."""
        pendiente = self.locales.pendiente
        if pendiente is None:
            return
        confirmado = self._base.locales.get(pendiente.id)
        if confirmado is not None and confirmado.version != pendiente.version - 1:
            raise LocalModificadoEnParalelo("El local cambió mientras lo editabas")
        self._base.locales[pendiente.id] = pendiente


class DirectorioEnMemoria:
    def __init__(self, base: BaseDeLocalesEnMemoria) -> None:
        self._base = base

    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        encontrado = next(
            (local.id for local in self._base.locales.values() if local.slug == slug), None
        )
        if encontrado is None:
            raise LocalNoEncontrado(f"No hay un local con el slug '{slug}'")
        return encontrado


class UnidadDelDirectorioEnMemoria(_Transaccion):
    def __init__(self, base: BaseDeLocalesEnMemoria) -> None:
        self.directorio = DirectorioEnMemoria(base)

    async def confirmar(self) -> None:
        return None
```

`tests/soporte/imagenes_en_memoria.py`:

```python
"""Dobles del procesador, el almacén y el lector de imágenes."""

from pathlib import Path

from minutas.compartido.dominio.identificador import Identificador
from minutas.locales.dominio.errores import ImagenNoEncontrada
from minutas.locales.dominio.imagen import Medidas, NombreDeImagen


class ProcesadorDeImagenesFalso:
    """Devuelve el contenido marcado con las medidas pedidas, sin procesar nada."""

    async def procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        return f"webp {medidas_maximas.ancho}x{medidas_maximas.alto}:".encode() + contenido


class AlmacenDeImagenesEnMemoria:
    def __init__(self) -> None:
        self.imagenes: dict[NombreDeImagen, bytes] = {}

    async def guardar(self, contenido: bytes) -> NombreDeImagen:
        nombre = NombreDeImagen(f"{Identificador.generar()}.webp")
        self.imagenes[nombre] = contenido
        return nombre

    def obtener_url_publica(self, nombre: NombreDeImagen) -> str:
        return f"/api/v1/imagenes/{nombre}"


class LectorSinImagenes:
    """Para los tests que no sirven archivos: ninguna imagen existe."""

    async def obtener_ruta(self, nombre: NombreDeImagen) -> Path:
        raise ImagenNoEncontrada("La imagen no existe")
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_casos_de_uso_del_owner.py -v && uv run mypy`
Expected: PASS (10 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/aplicacion/repositorio_de_locales.py src/minutas/locales/aplicacion/directorio_de_locales.py src/minutas/locales/aplicacion/unidades_de_trabajo.py src/minutas/locales/aplicacion/almacen_de_imagenes.py src/minutas/locales/aplicacion/lector_de_imagenes.py src/minutas/locales/aplicacion/locales_por_slug.py src/minutas/locales/aplicacion/vista_de_tienda.py src/minutas/locales/aplicacion/dar_de_alta_local.py src/minutas/locales/aplicacion/cambiar_slug.py src/minutas/locales/aplicacion/cambiar_zona_horaria.py src/minutas/locales/aplicacion/suspender_local.py src/minutas/locales/aplicacion/reactivar_local.py src/minutas/locales/aplicacion/obtener_tienda.py tests/soporte/locales_en_memoria.py tests/soporte/imagenes_en_memoria.py tests/unitarios/locales/test_casos_de_uso_del_owner.py
git commit -m "feat(locales): casos de uso del owner y tienda pública" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
