import pytest
from pydantic import ValidationError

from minutas.compartido.infraestructura.configuracion import (
    Configuracion,
    ConfiguracionDeMigraciones,
)

URL_APP = "postgresql+asyncpg://minutas_app:clave@db:5432/minutas"
URL_OWNER = "postgresql+asyncpg://minutas_owner:clave@db:5432/minutas"


@pytest.fixture(autouse=True)
def entorno_vacio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINUTAS_URL_BASE_DE_DATOS", raising=False)
    monkeypatch.delenv("MINUTAS_URL_BASE_DE_DATOS_MIGRACIONES", raising=False)
    monkeypatch.delenv("MINUTAS_NIVEL_DE_REGISTRO", raising=False)
    monkeypatch.delenv("MINUTAS_ENTORNO", raising=False)


def test_configuracion_lee_variables_con_prefijo_minutas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS", URL_APP)

    configuracion = Configuracion()

    assert configuracion.url_base_de_datos == URL_APP
    assert configuracion.nivel_de_registro == "INFO"
    assert configuracion.entorno == "desarrollo"


def test_configuracion_ignora_la_url_del_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS", URL_APP)
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS_MIGRACIONES", URL_OWNER)

    assert "url_base_de_datos_migraciones" not in Configuracion().model_dump()


def test_configuracion_con_nivel_de_registro_desconocido_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS", URL_APP)
    monkeypatch.setenv("MINUTAS_NIVEL_DE_REGISTRO", "CHARLATAN")

    with pytest.raises(ValidationError, match="nivel_de_registro"):
        Configuracion()


def test_configuracion_sin_url_de_base_de_datos_falla() -> None:
    with pytest.raises(ValidationError, match="url_base_de_datos"):
        Configuracion()


def test_configuracion_de_migraciones_lee_solo_la_url_del_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS_MIGRACIONES", URL_OWNER)

    configuracion = ConfiguracionDeMigraciones()

    assert configuracion.model_dump() == {"url_base_de_datos_migraciones": URL_OWNER}
