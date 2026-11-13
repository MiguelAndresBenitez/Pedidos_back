# Tarea 2: Calidad automatizada (pre-commit y CI)

**Archivos:**
- Crear: `.pre-commit-config.yaml`
- Crear: `.github/workflows/ci.yml`

---

## Decisiones de diseño

**¿Por qué hooks `local` que llaman a `uv run` en lugar de los repos oficiales de ruff y mypy?**
- Usan exactamente las versiones fijadas en `uv.lock`: el hook, la CI y el editor dan el mismo resultado.
- mypy necesita las dependencias del proyecto para chequear tipos; el entorno aislado de pre-commit no las tiene.

**¿Por qué la CI corre los tests de integración?**
- Los runners `ubuntu-latest` de GitHub traen Docker, así que testcontainers funciona sin configuración extra.
- El aislamiento entre locales es la garantía más importante del backend: se prueba en cada push.

---

## Paso 1: Configurar pre-commit

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        types: [python]
        pass_filenames: false
```

## Paso 2: Instalar y correr los hooks

Run: `uv run pre-commit install && uv run pre-commit run --all-files`
Expected:
```
pre-commit installed at .git/hooks/pre-commit
ruff check...............................................................Passed
ruff format..............................................................Passed
mypy.....................................................................Passed
```

## Paso 3: Configurar GitHub Actions

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  calidad:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - name: Instalar dependencias
        run: uv sync --frozen
      - name: Lint
        run: uv run ruff check
      - name: Formato
        run: uv run ruff format --check
      - name: Tipos
        run: uv run mypy
      - name: Tests
        run: uv run pytest -v
```

## Paso 4: Verificar el YAML localmente

Run: `uv run python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text()); print('ok')"`
Expected: `ok` (PyYAML llega como dependencia de pre-commit)

## Paso 5: Commit

```bash
git add .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "ci(proyecto): pre-commit con ruff y mypy, y workflow de GitHub Actions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Paso 6: Verificar la CI en GitHub

Se verifica al primer push a `main` o al abrir un PR (lo decide la persona).
Run: `gh run list --workflow ci.yml --limit 1`
Expected: estado `completed` y conclusión `success`
