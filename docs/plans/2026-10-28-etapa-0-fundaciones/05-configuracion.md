# Tarea 5: Configuración por entorno

**Archivos:**
- Crear: `src/minutas/compartido/infraestructura/configuracion.py`
- Test: `tests/unitarios/compartido/test_configuracion.py`

---

## Decisiones de diseño

**¿Por qué pydantic-settings en infraestructura y no en el dominio?**
- Leer variables de entorno es un detalle de infraestructura; el dominio no sabe de dónde salen los valores.
- Valida tipos y valores permitidos al arrancar: una configuración rota corta el arranque, no un request.

**¿Por qué dos clases, `Configuracion` y `ConfiguracionDeMigraciones`?**
- La spec separa roles: la API usa `minutas_app` (sin `BYPASSRLS`) y las migraciones usan `minutas_owner`, el único rol que puede apagar RLS.
- Si la API exigiera también la URL del owner, su contenedor tendría esa credencial y una falla en la API la expondría. Cada proceso pide solo lo que usa: la API, `Configuracion`; Alembic, `ConfiguracionDeMigraciones`.

**¿Por qué no se lee un archivo `.env`?**
- En Docker Compose las variables llegan por el entorno del contenedor; leer `.env` desde el código haría que los tests dependan de un archivo local.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_configuracion.py`:

```python
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
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_configuracion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.infraestructura.configuracion'`

## Paso 3: Implementación mínima

`src/minutas/compartido/infraestructura/configuracion.py`:

```python
"""Configuración leída de variables de entorno MINUTAS_*, una clase por proceso."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

NivelDeRegistro = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Entorno = Literal["desarrollo", "pruebas", "produccion"]


class Configuracion(BaseSettings):
    """Configuración de la API. Solo conoce la credencial del rol minutas_app."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos: str
    nivel_de_registro: NivelDeRegistro = "INFO"
    entorno: Entorno = "desarrollo"


class ConfiguracionDeMigraciones(BaseSettings):
    """Configuración de Alembic. Solo conoce la credencial del rol minutas_owner."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos_migraciones: str
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/compartido/test_configuracion.py -v && uv run mypy`
Expected: PASS (5 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/configuracion.py tests/unitarios/compartido/test_configuracion.py
git commit -m "feat(compartido): configuración por entorno separada para API y migraciones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
