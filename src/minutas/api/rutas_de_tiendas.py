"""Rutas públicas de la tienda."""

from fastapi import APIRouter

from minutas.api.dependencias import AhoraInyectado, CasosInyectados
from minutas.api.esquemas_de_tienda import TiendaHttp, TiendaNoDisponibleHttp, crear_tienda_http
from minutas.locales.dominio.errores import LocalNoEncontrado, SlugInvalido
from minutas.locales.dominio.slug import Slug

router_de_tiendas = APIRouter(prefix="/api/v1/tiendas", tags=["tiendas"])


@router_de_tiendas.get("/{slug}")
async def obtener_tienda(
    slug: str, casos: CasosInyectados, ahora: AhoraInyectado
) -> TiendaHttp | TiendaNoDisponibleHttp:
    """Un slug mal formado no puede ser de ningún local: responde 404, no 422."""
    try:
        valido = Slug(slug)
    except SlugInvalido as error:
        raise LocalNoEncontrado(f"No hay un local con el slug '{slug}'") from error
    return crear_tienda_http(await casos.obtener_tienda.ejecutar(valido, ahora))
