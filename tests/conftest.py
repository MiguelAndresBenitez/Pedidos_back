import pytest

from soporte.servicios_en_memoria import ServiciosEnMemoria, crear_servicios_en_memoria


@pytest.fixture
def memoria() -> ServiciosEnMemoria:
    """Servicios con dobles en memoria, compartidos por los tests de API y de consola."""
    return crear_servicios_en_memoria()
