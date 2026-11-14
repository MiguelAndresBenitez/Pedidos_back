# Tarea 1: Andamiaje del proyecto

**Archivos:**
- Crear: `pyproject.toml`, `.python-version`, `.gitignore`, `uv.lock` (lo genera uv)
- Crear: `src/minutas/__init__.py`, `src/minutas/py.typed`
- Crear: `src/minutas/api/__init__.py`
- Crear: `src/minutas/{compartido,identidad,locales,carta,pedidos}/__init__.py` y `.../{dominio,aplicacion,infraestructura}/__init__.py`
- Test: `tests/unitarios/test_paquete.py`

---

## Decisiones de diseño

**¿Por qué layout `src/`?**
- Los tests importan el paquete instalado, no la carpeta suelta: detecta errores de empaquetado.
- `uv sync` instala el proyecto en modo editable con hatchling.

**¿Por qué estas reglas de ruff, e ignorar `N818`?**
- `N818` exige que las excepciones terminen en `Error`; con nombres en español (`TiendaCerrada`) no aplica. Ver `docs/plans/00-conventions.md`, sección Idioma.
- `S101` (uso de `assert`) se ignora solo en tests.

**¿Por qué `--import-mode=importlib`?**
- Permite archivos de test con el mismo nombre en carpetas distintas sin `__init__.py`.

**¿Por qué `explicit_package_bases` y `mypy_path` en mypy?**
- Sin `__init__.py` en `tests/`, mypy toma `tests/api/conftest.py` y `tests/integracion/conftest.py` como el mismo módulo `conftest` y falla con "Duplicate module". Con esta opción los nombra `api.conftest` e `integracion.conftest`.
- `tests` en `mypy_path` permite tipar los imports de `soporte` (tarea 9).

---

## Paso 1: Configuración base

`pyproject.toml`:

```toml
[project]
name = "minutas"
version = "0.1.0"
description = "Backend de Minutas: SaaS de pedidos online para locales de comida"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/minutas"]

[tool.ruff]
line-length = 100
target-version = "py313"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "N", "SIM", "RUF", "ASYNC", "S"]
ignore = ["N818"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.mypy]
python_version = "3.13"
strict = true
files = ["src", "tests"]
mypy_path = ["src", "tests"]
explicit_package_bases = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["asyncpg.*", "testcontainers.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --import-mode=importlib"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = ["integracion: requiere Docker (PostgreSQL con testcontainers)"]
```

`.python-version`:

```
3.13
```

`.gitignore`:

```
.venv/
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
.env
dist/
```

`src/minutas/__init__.py` (vacío por ahora, para que el paquete se pueda construir):

```python
"""Backend de Minutas."""
```

## Paso 2: Instalar dependencias

Run:
```bash
touch src/minutas/py.typed
uv add fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" asyncpg alembic pydantic-settings structlog uuid-utils
uv add --dev pytest pytest-asyncio httpx "testcontainers[postgres]" ruff mypy pre-commit
```
Expected: `uv.lock` creado y `Installed N packages`.

## Paso 3: Escribir el test que falla

`tests/unitarios/test_paquete.py`:

```python
import importlib

import pytest

import minutas

CONTEXTOS = ("compartido", "identidad", "locales", "carta", "pedidos")
CAPAS = ("dominio", "aplicacion", "infraestructura")
MODULOS = [f"minutas.{contexto}.{capa}" for contexto in CONTEXTOS for capa in CAPAS]


def test_importar_paquete_expone_version_0_1_0() -> None:
    assert minutas.__version__ == "0.1.0"


@pytest.mark.parametrize("modulo", [*MODULOS, "minutas.api"])
def test_importar_capa_de_contexto_existe(modulo: str) -> None:
    assert importlib.import_module(modulo).__name__ == modulo
```

## Paso 4: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/test_paquete.py -v`
Expected: FAIL, con `AttributeError: module 'minutas' has no attribute '__version__'` y `ModuleNotFoundError: No module named 'minutas.compartido'`

## Paso 5: Implementación mínima

`src/minutas/__init__.py`:

```python
"""Backend de Minutas."""

__version__ = "0.1.0"
```

Paquetes de capas:

```bash
mkdir -p src/minutas/api && echo '"""Raíz de composición HTTP."""' > src/minutas/api/__init__.py
for contexto in compartido identidad locales carta pedidos; do
  mkdir -p "src/minutas/$contexto"
  echo "\"\"\"Contexto $contexto.\"\"\"" > "src/minutas/$contexto/__init__.py"
  for capa in dominio aplicacion infraestructura; do
    mkdir -p "src/minutas/$contexto/$capa"
    echo "\"\"\"Capa de $capa del contexto $contexto.\"\"\"" > "src/minutas/$contexto/$capa/__init__.py"
  done
done
```

## Paso 6: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/test_paquete.py -v`
Expected: PASS (17 passed)

## Paso 7: Verificar lint y tipos

Run: `uv run ruff check && uv run ruff format --check && uv run mypy`
Expected: `All checks passed!`, `N files already formatted`, `Success: no issues found in N source files`

## Paso 8: Commit

```bash
git add pyproject.toml uv.lock .python-version .gitignore src tests
git commit -m "chore(proyecto): andamiaje con uv, paquetes por contexto y herramientas de calidad" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
