# Tarea 17: Tienda pública

**Archivos:**
- Crear: `src/minutas/api/esquemas_de_tienda.py`
- Crear: `src/minutas/api/rutas_de_tiendas.py`
- Modificar: `src/minutas/api/app.py`
- Test: `tests/api/test_tiendas.py`

---

## Decisiones de diseño

**¿Qué hace la ruta?**
- Ejecuta `ObtenerTienda` con `ahora` y traduce la vista. No calcula nada ni decide la disponibilidad: eso ya viene en la vista (tarea 11).

**¿Qué responde `GET /api/v1/tiendas/{slug}`?**
- Los datos públicos, las franjas en hora local, la zona horaria que rige, las URLs de las imágenes, `abierto_ahora` y `proxima_apertura` (UTC o `null`).
- Suspendido: `200 {"disponible": false, "slug": ...}`, sin decir por qué. Inexistente: `404 local_no_encontrado`. Slug mal formado: `422 slug_invalido`.

**¿Cómo se traduce cada variante sin `if`?**
- `crear_tienda_http` es un `functools.singledispatch`: despacho por el tipo de la vista, una traducción por variante.

---

## Paso 1: Escribir el test que falla

`tests/api/test_tiendas.py`:

```python
from datetime import time

import httpx
import pytest

from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from soporte.servicios_en_memoria import INSTANTE_DE_PRUEBA, ServiciosEnMemoria

LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


@pytest.fixture
async def local(memoria: ServiciosEnMemoria) -> Local:
    local = await DarDeAltaLocal(memoria.servicios.crear_unidad_del_local).ejecutar(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )
    guardado = memoria.locales.locales[local.id]
    guardado.reemplazar_horario(
        Horario(
            (
                FranjaHoraria(DiaDeLaSemana.VIERNES, time(19), time(1)),
                FranjaHoraria(DiaDeLaSemana.SABADO, time(19), time(1)),
            )
        ),
        INSTANTE_DE_PRUEBA,
    )
    guardado.cambiar_imagen(TipoDeImagen.LOGO, LOGO)
    return guardado


@pytest.mark.usefixtures("local")
async def test_obtener_tienda_abierta_devuelve_los_datos_publicos(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/la-esquina")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "disponible": True,
        "slug": "la-esquina",
        "nombre": "La Esquina",
        "descripcion": None,
        "direccion": None,
        "whatsapp": "5493515123456",
        "color": "#000000",
        "modalidades": ["retiro"],
        "zona_horaria": "America/Argentina/Buenos_Aires",
        "horarios": [
            {"dia": 4, "apertura": "19:00", "cierre": "01:00"},
            {"dia": 5, "apertura": "19:00", "cierre": "01:00"},
        ],
        "logo_url": f"/api/v1/imagenes/{LOGO}",
        "portada_url": None,
        "abierto_ahora": True,
        "proxima_apertura": None,
    }


async def test_obtener_tienda_cerrada_por_hoy_anuncia_la_proxima_apertura(
    cliente: httpx.AsyncClient, local: Local
) -> None:
    local.cerrar_por_hoy(INSTANTE_DE_PRUEBA)

    cuerpo = (await cliente.get("/api/v1/tiendas/la-esquina")).json()

    assert cuerpo["abierto_ahora"] is False
    # Sábado 7/11 a las 19:00 en Buenos Aires.
    assert cuerpo["proxima_apertura"] == "2026-11-07T22:00:00Z"


async def test_obtener_tienda_suspendida_solo_dice_que_no_esta_disponible(
    cliente: httpx.AsyncClient, local: Local
) -> None:
    local.suspender()

    respuesta = await cliente.get("/api/v1/tiendas/la-esquina")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"disponible": False, "slug": "la-esquina"}


async def test_obtener_tienda_inexistente_responde_404(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.json()["code"] == "local_no_encontrado"


async def test_obtener_tienda_con_slug_mal_formado_responde_422(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/tiendas/La_Esquina")

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "slug_invalido"
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/api/test_tiendas.py -v`
Expected: FAIL: `assert 404 == 200`

## Paso 3: Implementación

`src/minutas/api/esquemas_de_tienda.py`:

```python
"""Esquemas HTTP de la tienda pública: traducen la vista de la aplicación, sin calcular nada."""

from datetime import datetime, time
from functools import singledispatch
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

from minutas.locales.aplicacion.vista_de_tienda import (
    TiendaDisponible,
    TiendaNoDisponible,
    VistaDeTienda,
)
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.modalidad import Modalidad

Hora = Annotated[time, PlainSerializer(lambda hora: hora.strftime("%H:%M"), return_type=str)]


class FranjaHttp(BaseModel):
    dia: DiaDeLaSemana
    apertura: Hora
    cierre: Hora


class TiendaHttp(BaseModel):
    disponible: Literal[True] = True
    slug: str
    nombre: str
    descripcion: str | None
    direccion: str | None
    whatsapp: str
    color: str
    modalidades: list[Modalidad]
    zona_horaria: str
    horarios: list[FranjaHttp]
    logo_url: str | None
    portada_url: str | None
    abierto_ahora: bool
    proxima_apertura: datetime | None


class TiendaNoDisponibleHttp(BaseModel):
    disponible: Literal[False] = False
    slug: str


@singledispatch
def crear_tienda_http(vista: VistaDeTienda) -> TiendaHttp | TiendaNoDisponibleHttp:
    """Despacho por tipo de vista (sin `if`): cada variante tiene su traducción."""
    raise TypeError(f"Vista de tienda desconocida: {type(vista).__name__}")


@crear_tienda_http.register
def _(vista: TiendaDisponible) -> TiendaHttp:
    return TiendaHttp(
        slug=vista.slug,
        nombre=vista.nombre,
        descripcion=vista.descripcion,
        direccion=vista.direccion,
        whatsapp=vista.whatsapp,
        color=vista.color,
        modalidades=list(vista.modalidades),
        zona_horaria=vista.zona_horaria,
        horarios=[
            FranjaHttp(dia=franja.dia, apertura=franja.apertura, cierre=franja.cierre)
            for franja in vista.franjas
        ],
        logo_url=vista.logo_url,
        portada_url=vista.portada_url,
        abierto_ahora=vista.abierto_ahora,
        proxima_apertura=vista.proxima_apertura,
    )


@crear_tienda_http.register
def _(vista: TiendaNoDisponible) -> TiendaNoDisponibleHttp:
    return TiendaNoDisponibleHttp(slug=vista.slug)
```

`src/minutas/api/rutas_de_tiendas.py`:

```python
"""Rutas públicas de la tienda."""

from fastapi import APIRouter

from minutas.api.dependencias import AhoraInyectado, CasosInyectados
from minutas.api.esquemas_de_tienda import TiendaHttp, TiendaNoDisponibleHttp, crear_tienda_http
from minutas.locales.dominio.slug import Slug

router_de_tiendas = APIRouter(prefix="/api/v1/tiendas", tags=["tiendas"])


@router_de_tiendas.get("/{slug}")
async def obtener_tienda(
    slug: str, casos: CasosInyectados, ahora: AhoraInyectado
) -> TiendaHttp | TiendaNoDisponibleHttp:
    return crear_tienda_http(await casos.obtener_tienda.ejecutar(Slug(slug), ahora))
```

`src/minutas/api/app.py`: registrar el router.

```python
from minutas.api.rutas_de_tiendas import router_de_tiendas
...
    app.include_router(router_de_salud)
    app.include_router(router_de_tiendas)
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/api -v && uv run mypy`
Expected: PASS (5 passed en `test_tiendas.py`) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/api/esquemas_de_tienda.py src/minutas/api/rutas_de_tiendas.py src/minutas/api/app.py tests/api/test_tiendas.py
git commit -m "feat(api): tienda pública con abierto ahora y próxima apertura" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
