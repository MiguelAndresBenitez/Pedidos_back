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
