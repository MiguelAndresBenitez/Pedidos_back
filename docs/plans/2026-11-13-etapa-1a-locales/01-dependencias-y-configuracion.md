# Tarea 1: Dependencias y configuración

**Archivos:**
- Modificar: `pyproject.toml`
- Modificar: `uv.lock`
- Modificar: `src/minutas/compartido/infraestructura/configuracion.py`
- Modificar: `migraciones/env.py`
- Test: `tests/unitarios/compartido/test_configuracion.py`

---

## Decisiones de diseño

**¿Por qué `SecretStr` para las URLs de conexión?**
- Llevan la contraseña del rol. Con `SecretStr`, ni `repr` ni `model_dump()` la muestran, así un log o un traceback no la filtra. Quien la usa la pide con `get_secret_value()`. Es un pendiente de la etapa 0.

**¿Por qué `directorio_de_imagenes` con valor por defecto?**
- En Docker es el volumen `/var/lib/minutas/imagenes` (tarea 22). Los tests lo apuntan a una carpeta temporal.

**¿Qué no entra todavía?**
- El client ID de Google, los orígenes permitidos y la política de sesión llegan con la etapa 1b, que es la que los usa.

**Dependencias nuevas:** `phonenumbers` (WhatsApp, tarea 4) y `pillow` (imágenes, tarea 15). Las dos traen sus tipos.

---

## Paso 1: Agregar las dependencias

```bash
uv add phonenumbers pillow
```

## Paso 2: Escribir el test que falla

`tests/unitarios/compartido/test_configuracion.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from minutas.compartido.infraestructura.configuracion import (
    Configuracion,
    ConfiguracionDeMigraciones,
)

URL_APP = "postgresql+asyncpg://minutas_app:clave@db:5432/minutas"
URL_OWNER = "postgresql+asyncpg://minutas_owner:clave@db:5432/minutas"
VARIABLES = (
    "URL_BASE_DE_DATOS",
    "URL_BASE_DE_DATOS_MIGRACIONES",
    "NIVEL_DE_REGISTRO",
    "ENTORNO",
    "DIRECTORIO_DE_IMAGENES",
)


@pytest.fixture(autouse=True)
def entorno_vacio(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in VARIABLES:
        monkeypatch.delenv(f"MINUTAS_{variable}", raising=False)


def test_configuracion_lee_variables_con_prefijo_minutas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS", URL_APP)

    configuracion = Configuracion()

    assert configuracion.url_base_de_datos.get_secret_value() == URL_APP
    assert configuracion.nivel_de_registro == "INFO"
    assert configuracion.entorno == "desarrollo"
    assert configuracion.directorio_de_imagenes == Path("/var/lib/minutas/imagenes")


def test_configuracion_oculta_la_url_al_mostrarse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINUTAS_URL_BASE_DE_DATOS", URL_APP)

    configuracion = Configuracion()

    assert "clave" not in repr(configuracion)
    assert "clave" not in str(configuracion.model_dump())


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

    assert list(configuracion.model_dump()) == ["url_base_de_datos_migraciones"]
    assert configuracion.url_base_de_datos_migraciones.get_secret_value() == URL_OWNER
```

## Paso 3: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_configuracion.py -v`
Expected: FAIL con `AttributeError: 'str' object has no attribute 'get_secret_value'`

## Paso 4: Implementación

`src/minutas/compartido/infraestructura/configuracion.py`:

```python
"""Configuración leída de variables de entorno MINUTAS_*, una clase por proceso."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

NivelDeRegistro = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Entorno = Literal["desarrollo", "pruebas", "produccion"]


class Configuracion(BaseSettings):
    """Configuración de la API y la consola. Solo conoce la credencial del rol minutas_app."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos: SecretStr
    nivel_de_registro: NivelDeRegistro = "INFO"
    entorno: Entorno = "desarrollo"
    directorio_de_imagenes: Path = Path("/var/lib/minutas/imagenes")


class ConfiguracionDeMigraciones(BaseSettings):
    """Configuración de Alembic. Solo conoce la credencial del rol minutas_owner."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos_migraciones: SecretStr
```

`migraciones/env.py`: la URL del owner ahora es secreta.

```python
def obtener_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    return url or ConfiguracionDeMigraciones().url_base_de_datos_migraciones.get_secret_value()
```

## Paso 5: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios -v && uv run ruff check && uv run ruff format --check && uv run mypy`
Expected: PASS (6 passed en `test_configuracion.py`) y `Success: no issues found`

## Paso 6: Commit

```bash
git add pyproject.toml uv.lock src/minutas/compartido/infraestructura/configuracion.py migraciones/env.py tests/unitarios/compartido/test_configuracion.py
git commit -m "feat(compartido): url de conexión secreta y directorio de imágenes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
