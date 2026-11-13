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
