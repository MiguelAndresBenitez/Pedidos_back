# Tarea 14: Docker Compose

**Archivos:**
- Crear: `Dockerfile`, `.dockerignore`
- Crear: `compose.yaml`
- Crear: `docker/postgres/02-claves.sh`
- Crear: `.env.ejemplo`
- Crear: `README.md`

---

## Decisiones de diseño

**¿Por qué las migraciones son un servicio aparte y no parte del arranque de la API?**
- La spec pide migrar como paso separado y con el rol dueño. La API arranca solo cuando `migraciones` terminó bien (`service_completed_successfully`).
- Con varias instancias de la API, ninguna compite por migrar.

**¿Por qué una sola imagen para la API y las migraciones?**
- La spec pide una imagen para desarrollo y producción. Cambia solo el comando y las variables de entorno.

**¿Por qué `roles.sql` y `02-claves.sh` en `docker-entrypoint-initdb.d`?**
- PostgreSQL los corre una sola vez, al crear el volumen. `roles.sql` es el mismo archivo que usan los tests (tarea 9); las contraseñas salen de `.env`.

**¿Por qué el healthcheck de `db` usa `-h 127.0.0.1`?**
- Mientras corren los scripts de `initdb.d`, PostgreSQL levanta un servidor temporal que escucha solo por socket unix. Sin `-h`, `pg_isready` respondería "listo" antes de que existan los roles y antes de que `db:5432` acepte conexiones TCP, y `migraciones` fallaría en el primer arranque.
- El primer arranque (`initdb` más los scripts) puede tardar decenas de segundos: `start_period: 60s` no cuenta esos fallos y `start_interval: 1s` detecta enseguida cuando la base está lista.

**¿Por qué cada servicio recibe solo su credencial?**
- `migraciones` recibe la URL de `minutas_owner`; `api`, la de `minutas_app` (ver tarea 5). La API nunca ve la credencial que puede apagar RLS.
- `${VAR:?mensaje}` corta el `docker compose up` si falta una contraseña, en lugar de crear roles con contraseña vacía.

**¿Por qué los puertos se publican solo en `127.0.0.1` y la imagen corre sin root?**
- La base y la API de desarrollo no quedan expuestas a la red local.
- La imagen es la misma que irá a producción: `uv` fijado en una versión y la app como usuario sin privilegios.

**¿Por qué `.env.ejemplo` versionado y `.env` ignorado?**
- El ejemplo documenta qué variables hacen falta; las contraseñas reales nunca entran al repo (`.gitignore` de la tarea 1).

---

## Paso 1: Imagen

`Dockerfile`:

```dockerfile
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migraciones ./migraciones
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 minutas
USER minutas

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "--factory", "minutas.api.app:crear_app_desde_entorno", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`:

```
.venv
.git
.env
**/__pycache__
.mypy_cache
.ruff_cache
.pytest_cache
tests
docs
```

## Paso 2: Servicios

`docker/postgres/02-claves.sh`:

```sh
#!/bin/sh
# Fija las contraseñas de los roles creados por 01-roles.sql, desde el entorno.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v clave_owner="$MINUTAS_CLAVE_OWNER" -v clave_app="$MINUTAS_CLAVE_APP" <<'SQL'
ALTER ROLE minutas_owner PASSWORD :'clave_owner';
ALTER ROLE minutas_app PASSWORD :'clave_app';
SQL
```

`compose.yaml`:

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: minutas
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?falta POSTGRES_PASSWORD en .env}
      MINUTAS_CLAVE_OWNER: ${MINUTAS_CLAVE_OWNER:?falta MINUTAS_CLAVE_OWNER en .env}
      MINUTAS_CLAVE_APP: ${MINUTAS_CLAVE_APP:?falta MINUTAS_CLAVE_APP en .env}
    volumes:
      - datos-postgres:/var/lib/postgresql/data
      - ./docker/postgres/roles.sql:/docker-entrypoint-initdb.d/01-roles.sql:ro
      - ./docker/postgres/02-claves.sh:/docker-entrypoint-initdb.d/02-claves.sh:ro
    ports:
      - "127.0.0.1:${PUERTO_DB:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U postgres -d minutas"]
      start_period: 60s
      start_interval: 1s
      interval: 5s
      timeout: 3s
      retries: 5

  migraciones:
    build: .
    command: ["alembic", "upgrade", "head"]
    environment:
      MINUTAS_URL_BASE_DE_DATOS_MIGRACIONES: postgresql+asyncpg://minutas_owner:${MINUTAS_CLAVE_OWNER}@db:5432/minutas
    depends_on:
      db:
        condition: service_healthy

  api:
    build: .
    environment:
      MINUTAS_URL_BASE_DE_DATOS: postgresql+asyncpg://minutas_app:${MINUTAS_CLAVE_APP}@db:5432/minutas
      MINUTAS_NIVEL_DE_REGISTRO: ${MINUTAS_NIVEL_DE_REGISTRO:-INFO}
      MINUTAS_ENTORNO: desarrollo
    ports:
      - "127.0.0.1:8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud')"]
      interval: 5s
      timeout: 3s
      retries: 10
    depends_on:
      migraciones:
        condition: service_completed_successfully

volumes:
  datos-postgres:
```

`.env.ejemplo` (las contraseñas van dentro de una URL: usar solo letras, números y `-`):

```
POSTGRES_PASSWORD=cambiar-postgres
MINUTAS_CLAVE_OWNER=cambiar-owner
MINUTAS_CLAVE_APP=cambiar-app
MINUTAS_NIVEL_DE_REGISTRO=INFO
```

## Paso 3: Levantar y verificar

Run:
```bash
cp .env.ejemplo .env
docker compose up --build -d
curl -s --retry 15 --retry-delay 2 --retry-all-errors localhost:8000/salud
```
Expected: `{"estado":"ok"}`

Run: `docker compose ps -a`
Expected: `db` y `api` con `(healthy)` en el estado, `migraciones` en `Exited (0)`

Run: `docker compose exec db psql -U postgres -d minutas -tAc "SELECT version_num FROM alembic_version"`
Expected: `0001`

Run: `docker compose logs api | tail -n 3`
Expected: líneas de uvicorn, incluida `Uvicorn running on http://0.0.0.0:8000`

Run: `docker compose down -v`

## Paso 4: README

`README.md`:

````markdown
# Minutas — backend

API del SaaS de pedidos online Minutas. Diseño en `docs/superpowers/specs/`, planes en `docs/plans/`.

## Requisitos

uv y Docker (ver `docs/plans/2026-10-28-etapa-0-fundaciones/00-prerrequisitos.md`).

## Desarrollo

```bash
uv sync
uv run pre-commit install
uv run pytest            # los tests de integración levantan PostgreSQL con Docker
```

## Levantar con Docker Compose

```bash
cp .env.ejemplo .env     # y cambiar las contraseñas
docker compose up --build
curl localhost:8000/salud
```
````

## Paso 5: Commit

```bash
chmod +x docker/postgres/02-claves.sh
git add Dockerfile .dockerignore compose.yaml docker/postgres/02-claves.sh .env.ejemplo README.md
git commit -m "feat(infra): Docker Compose con base, migraciones y API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
