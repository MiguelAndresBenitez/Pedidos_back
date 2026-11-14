# Tarea 16: Raíz de composición y fábrica de la app

**Archivos:**
- Crear: `src/minutas/composicion.py`
- Crear: `src/minutas/api/rutas_publicas.py`
- Crear: `src/minutas/api/dependencias.py`
- Crear: `tests/soporte/servicios_en_memoria.py`
- Crear: `tests/conftest.py`
- Modificar: `src/minutas/api/app.py`
- Modificar: `tests/api/conftest.py`
- Modificar: `tests/api/test_errores_http.py`
- Test: `tests/api/test_app.py`

---

## Decisiones de diseño

**¿Qué arma `composicion.py`?**
- `Servicios`: los adaptadores (fábricas de unidades, reloj, procesador, almacén y cómo cerrar). `crear_servicios` arma los reales.
- `CasosDeUso`: cada caso de uso ya cableado con lo que necesita, una sola vez (no tienen estado). La API y la consola solo hacen `casos.<caso>.ejecutar(...)`: si cambia un constructor, se toca un solo archivo (convención "raíz de composición con casos de uso armados").

**¿Por qué `crear_app` recibe los servicios?**
- Los tests de API usan `crear_servicios_en_memoria()`: corren sin base ni Docker. La prueba de punta a punta usa los reales. El `lifespan` llama a `servicios.cerrar()` al apagar, que libera el pool.

**¿Cómo se lee la hora?**
- `AhoraInyectado` lee el reloj una vez por solicitud (FastAPI resuelve cada dependencia una vez por request) y se pasa a los casos de uso como `ahora`.

**¿Qué reciben las rutas?**
- Solo lo que usan: `CasosInyectados`, `AhoraInyectado` y, para servir imágenes, `LectorInyectado`. Nunca `Servicios` entero.

**¿Por qué `api/rutas_publicas.py`?**
- La ruta donde se publican las imágenes la usan la API y el almacén (para armar las URLs). Un módulo sin dependencias evita que `composicion.py` importe los routers.

**`tests/conftest.py`** define el fixture `memoria` para los tests de API y de consola.

---

## Paso 1: Escribir el test que falla

`tests/api/test_app.py`:

```python
from dataclasses import replace

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion
from soporte.servicios_en_memoria import ServiciosEnMemoria


def test_crear_app_guarda_configuracion_servicios_y_casos_de_uso(
    configuracion: Configuracion, memoria: ServiciosEnMemoria
) -> None:
    app = crear_app(configuracion, memoria.servicios)

    assert app.state.configuracion is configuracion
    assert app.state.servicios is memoria.servicios
    assert app.state.casos_de_uso.obtener_tienda is not None


async def test_apagar_la_app_cierra_los_servicios(
    configuracion: Configuracion, memoria: ServiciosEnMemoria
) -> None:
    cierres: list[str] = []

    async def cerrar() -> None:
        cierres.append("cerrado")

    app = crear_app(configuracion, replace(memoria.servicios, cerrar=cerrar))
    async with app.router.lifespan_context(app):
        assert cierres == []

    assert cierres == ["cerrado"]
```

`tests/soporte/servicios_en_memoria.py`:

```python
"""Servicios de la app armados con dobles en memoria, para la API y la consola sin base."""

from dataclasses import dataclass
from datetime import UTC, datetime

from minutas.composicion import Servicios
from soporte.imagenes_en_memoria import (
    AlmacenDeImagenesEnMemoria,
    LectorSinImagenes,
    ProcesadorDeImagenesFalso,
)
from soporte.locales_en_memoria import BaseDeLocalesEnMemoria
from soporte.reloj_fijo import RelojFijo

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
INSTANTE_DE_PRUEBA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)


@dataclass
class ServiciosEnMemoria:
    locales: BaseDeLocalesEnMemoria
    reloj: RelojFijo
    almacen: AlmacenDeImagenesEnMemoria
    servicios: Servicios


async def no_cerrar_nada() -> None:
    return None


def crear_servicios_en_memoria() -> ServiciosEnMemoria:
    locales = BaseDeLocalesEnMemoria()
    reloj = RelojFijo(INSTANTE_DE_PRUEBA)
    almacen = AlmacenDeImagenesEnMemoria()
    servicios = Servicios(
        crear_unidad_del_local=locales.crear_unidad_del_local,
        crear_unidad_del_directorio=locales.crear_unidad_del_directorio,
        reloj=reloj,
        procesador_de_imagenes=ProcesadorDeImagenesFalso(),
        almacen_de_imagenes=almacen,
        lector_de_imagenes=LectorSinImagenes(),
        cerrar=no_cerrar_nada,
    )
    return ServiciosEnMemoria(locales, reloj, almacen, servicios)
```

`tests/conftest.py`:

```python
import pytest

from soporte.servicios_en_memoria import ServiciosEnMemoria, crear_servicios_en_memoria


@pytest.fixture
def memoria() -> ServiciosEnMemoria:
    """Servicios con dobles en memoria, compartidos por los tests de API y de consola."""
    return crear_servicios_en_memoria()
```

`tests/api/conftest.py` (versión completa):

```python
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from minutas.api.app import crear_app
from minutas.compartido.infraestructura.configuracion import Configuracion
from soporte.servicios_en_memoria import ServiciosEnMemoria

URL_APP = "postgresql+asyncpg://minutas_app:clave@localhost:5432/minutas"


@pytest.fixture
def configuracion(tmp_path: Path) -> Configuracion:
    return Configuracion(
        url_base_de_datos=SecretStr(URL_APP),
        entorno="pruebas",
        directorio_de_imagenes=tmp_path / "imagenes",
    )


@pytest.fixture
def app(configuracion: Configuracion, memoria: ServiciosEnMemoria) -> FastAPI:
    return crear_app(configuracion, memoria.servicios)


@pytest.fixture
async def cliente(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente
```

`tests/api/test_errores_http.py`: el fixture `app` pasa los servicios en memoria.

```python
from soporte.servicios_en_memoria import ServiciosEnMemoria


@pytest.fixture
def app(configuracion: Configuracion, memoria: ServiciosEnMemoria) -> FastAPI:
    app = crear_app(configuracion, memoria.servicios)
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/api -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.composicion'`

## Paso 3: Implementación

`src/minutas/api/rutas_publicas.py`:

```python
"""Rutas públicas que otras capas necesitan conocer, sin importar los routers."""

# Donde la API publica el directorio del almacén en disco.
RUTA_DE_IMAGENES = "/api/v1/imagenes"
```

`src/minutas/composicion.py`:

```python
"""Raíz de composición compartida por la API y la consola: arma adaptadores y casos de uso."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from minutas.api.rutas_publicas import RUTA_DE_IMAGENES
from minutas.compartido.aplicacion.reloj import Reloj
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.base_de_datos import (
    crear_fabrica_de_sesiones,
    crear_motor,
)
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.reloj_del_sistema import RelojDelSistema
from minutas.locales.aplicacion.actualizar_datos_del_local import ActualizarDatosDelLocal
from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.cambiar_hora_de_corte import CambiarHoraDeCorte
from minutas.locales.aplicacion.cambiar_slug import CambiarSlug
from minutas.locales.aplicacion.cambiar_zona_horaria import CambiarZonaHoraria
from minutas.locales.aplicacion.cerrar_manualmente import CerrarManualmente
from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.aplicacion.lector_de_imagenes import LectorDeImagenes
from minutas.locales.aplicacion.locales_por_slug import LocalesPorSlug
from minutas.locales.aplicacion.obtener_local_del_panel import ObtenerLocalDelPanel
from minutas.locales.aplicacion.obtener_tienda import ObtenerTienda
from minutas.locales.aplicacion.procesador_de_imagenes import ProcesadorDeImagenes
from minutas.locales.aplicacion.reabrir import Reabrir
from minutas.locales.aplicacion.reactivar_local import ReactivarLocal
from minutas.locales.aplicacion.reemplazar_horario import ReemplazarHorario
from minutas.locales.aplicacion.subir_imagen_del_local import SubirImagenDelLocal
from minutas.locales.aplicacion.suspender_local import SuspenderLocal
from minutas.locales.aplicacion.unidades_de_trabajo import (
    FabricaDeUnidadesDelDirectorio,
    FabricaDeUnidadesDelLocal,
    UnidadDeTrabajoDelDirectorio,
    UnidadDeTrabajoDelLocal,
)
from minutas.locales.infraestructura.almacen_de_imagenes_en_disco import AlmacenDeImagenesEnDisco
from minutas.locales.infraestructura.procesador_de_imagenes_con_pillow import (
    ProcesadorDeImagenesConPillow,
)
from minutas.locales.infraestructura.unidades_de_trabajo_sqlalchemy import (
    UnidadDelDirectorioSQLAlchemy,
    UnidadDelLocalSQLAlchemy,
)


@dataclass(frozen=True, kw_only=True)
class Servicios:
    """Adaptadores de los casos de uso; los tests los reemplazan por dobles en memoria."""

    crear_unidad_del_local: FabricaDeUnidadesDelLocal
    crear_unidad_del_directorio: FabricaDeUnidadesDelDirectorio
    reloj: Reloj
    procesador_de_imagenes: ProcesadorDeImagenes
    almacen_de_imagenes: AlmacenDeImagenes
    lector_de_imagenes: LectorDeImagenes
    cerrar: Callable[[], Awaitable[None]]


def crear_servicios(configuracion: Configuracion) -> Servicios:
    motor = crear_motor(configuracion.url_base_de_datos.get_secret_value())
    fabrica = crear_fabrica_de_sesiones(motor)

    def crear_unidad_del_local(local_id: LocalId) -> UnidadDeTrabajoDelLocal:
        return UnidadDelLocalSQLAlchemy(fabrica, local_id)

    def crear_unidad_del_directorio() -> UnidadDeTrabajoDelDirectorio:
        return UnidadDelDirectorioSQLAlchemy(fabrica)

    imagenes = AlmacenDeImagenesEnDisco(configuracion.directorio_de_imagenes, RUTA_DE_IMAGENES)
    return Servicios(
        crear_unidad_del_local=crear_unidad_del_local,
        crear_unidad_del_directorio=crear_unidad_del_directorio,
        reloj=RelojDelSistema(),
        procesador_de_imagenes=ProcesadorDeImagenesConPillow(),
        almacen_de_imagenes=imagenes,
        lector_de_imagenes=imagenes,
        cerrar=motor.dispose,
    )


@dataclass(frozen=True, kw_only=True)
class CasosDeUso:
    """Casos de uso ya armados: la API y la consola solo los ejecutan. No tienen estado."""

    dar_de_alta_local: DarDeAltaLocal
    cambiar_slug: CambiarSlug
    cambiar_zona_horaria: CambiarZonaHoraria
    suspender_local: SuspenderLocal
    reactivar_local: ReactivarLocal
    obtener_tienda: ObtenerTienda
    actualizar_datos_del_local: ActualizarDatosDelLocal
    reemplazar_horario: ReemplazarHorario
    cambiar_hora_de_corte: CambiarHoraDeCorte
    cerrar_manualmente: CerrarManualmente
    reabrir: Reabrir
    subir_imagen_del_local: SubirImagenDelLocal
    obtener_local_del_panel: ObtenerLocalDelPanel


def crear_casos_de_uso(servicios: Servicios) -> CasosDeUso:
    del_local = servicios.crear_unidad_del_local
    por_slug = LocalesPorSlug(servicios.crear_unidad_del_directorio, del_local)
    return CasosDeUso(
        dar_de_alta_local=DarDeAltaLocal(del_local),
        cambiar_slug=CambiarSlug(por_slug),
        cambiar_zona_horaria=CambiarZonaHoraria(por_slug),
        suspender_local=SuspenderLocal(por_slug),
        reactivar_local=ReactivarLocal(por_slug),
        obtener_tienda=ObtenerTienda(por_slug, servicios.almacen_de_imagenes),
        actualizar_datos_del_local=ActualizarDatosDelLocal(del_local),
        reemplazar_horario=ReemplazarHorario(del_local),
        cambiar_hora_de_corte=CambiarHoraDeCorte(del_local),
        cerrar_manualmente=CerrarManualmente(del_local),
        reabrir=Reabrir(del_local),
        subir_imagen_del_local=SubirImagenDelLocal(
            del_local, servicios.procesador_de_imagenes, servicios.almacen_de_imagenes
        ),
        obtener_local_del_panel=ObtenerLocalDelPanel(del_local),
    )
```

`src/minutas/api/dependencias.py`:

```python
"""Dependencias de FastAPI: casos de uso, la hora de la solicitud y el lector de imágenes.

Las rutas no reciben `Servicios` entero: piden solo lo que usan.
"""

from datetime import datetime
from typing import Annotated, cast

from fastapi import Depends, Request

from minutas.composicion import CasosDeUso, Servicios
from minutas.locales.aplicacion.lector_de_imagenes import LectorDeImagenes


def obtener_servicios(request: Request) -> Servicios:
    return cast(Servicios, request.app.state.servicios)


def obtener_casos_de_uso(request: Request) -> CasosDeUso:
    return cast(CasosDeUso, request.app.state.casos_de_uso)


ServiciosInyectados = Annotated[Servicios, Depends(obtener_servicios)]
CasosInyectados = Annotated[CasosDeUso, Depends(obtener_casos_de_uso)]


def obtener_ahora(servicios: ServiciosInyectados) -> datetime:
    """Un solo instante por solicitud: FastAPI resuelve cada dependencia una vez por request."""
    return servicios.reloj.ahora()


AhoraInyectado = Annotated[datetime, Depends(obtener_ahora)]


def obtener_lector_de_imagenes(servicios: ServiciosInyectados) -> LectorDeImagenes:
    return servicios.lector_de_imagenes


LectorInyectado = Annotated[LectorDeImagenes, Depends(obtener_lector_de_imagenes)]
```

`src/minutas/api/app.py`:

```python
"""Fábrica de la aplicación FastAPI: raíz de composición HTTP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from minutas import __version__
from minutas.api.errores_http import registrar_manejadores_de_errores
from minutas.api.middleware_de_solicitud import MiddlewareDeSolicitud
from minutas.api.salud import router_de_salud
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios


def crear_app(configuracion: Configuracion, servicios: Servicios) -> FastAPI:
    configurar_registro(configuracion.nivel_de_registro)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        yield
        await servicios.cerrar()

    app = FastAPI(title="Minutas", version=__version__, lifespan=ciclo_de_vida)
    app.state.configuracion = configuracion
    app.state.servicios = servicios
    app.state.casos_de_uso = crear_casos_de_uso(servicios)
    app.add_middleware(MiddlewareDeSolicitud)
    app.include_router(router_de_salud)
    registrar_manejadores_de_errores(app)
    return app


def crear_app_desde_entorno() -> FastAPI:
    """Entrada para uvicorn: `uvicorn --factory minutas.api.app:crear_app_desde_entorno`."""
    configuracion = Configuracion()
    return crear_app(configuracion, crear_servicios(configuracion))
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/api -v && uv run mypy`
Expected: PASS (2 passed en `test_app.py`; salud y errores siguen verdes) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/composicion.py src/minutas/api/rutas_publicas.py src/minutas/api/dependencias.py src/minutas/api/app.py tests/soporte/servicios_en_memoria.py tests/conftest.py tests/api/conftest.py tests/api/test_errores_http.py tests/api/test_app.py
git commit -m "feat(api): raíz de composición con servicios y casos de uso" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
