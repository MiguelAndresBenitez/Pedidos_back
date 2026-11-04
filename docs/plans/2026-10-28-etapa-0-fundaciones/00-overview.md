# Etapa 0 — Fundaciones: plan de implementación

> **Para Claude:** cargar cada archivo de tarea cuando toque. Usar el flujo de superpowers:executing-plans o superpowers:subagent-driven-development. Leer `docs/plans/00-conventions.md` antes de cada tarea.

**Objetivo:** que la API arranque, migre y tenga el aislamiento entre locales probado con una tabla de ejemplo, sobre una base de calidad automatizada.

**Arquitectura:** monolito modular con cuatro contextos (`identidad`, `locales`, `carta`, `pedidos`) más `compartido`, cada uno con `dominio/`, `aplicacion/` e `infraestructura/`. Esta etapa construye solo lo común: identificadores UUIDv7, errores de dominio y su traducción a `problem+json`, configuración, registro JSON, la unidad de trabajo que fija el tenant y las políticas RLS en PostgreSQL. Los contextos quedan como paquetes vacíos.

**Stack:** Python 3.13 · uv · FastAPI · SQLAlchemy 2.0 async + asyncpg · Alembic · PostgreSQL 17 · pydantic-settings · structlog · uuid-utils · pytest + pytest-asyncio + httpx + testcontainers · ruff · mypy · pre-commit · GitHub Actions · Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-07-backend-minutas-design.md` (secciones Stack, Multi-tenancy, Errores, testing y despliegue, Plan de módulos fila 0).

---

## Tareas

| # | Tarea | Archivo | Estado |
|---|-------|---------|--------|
| 0 | Prerrequisitos del entorno | [00-prerrequisitos.md](00-prerrequisitos.md) | Pendiente |
| 1 | Andamiaje del proyecto | [01-andamiaje-del-proyecto.md](01-andamiaje-del-proyecto.md) | Pendiente |
| 2 | Calidad automatizada (pre-commit y CI) | [02-calidad-automatizada.md](02-calidad-automatizada.md) | Pendiente |
| 3 | Errores de dominio | [03-errores-de-dominio.md](03-errores-de-dominio.md) | Pendiente |
| 4 | Identificadores UUIDv7 | [04-identificadores-uuid7.md](04-identificadores-uuid7.md) | Pendiente |
| 5 | Configuración por entorno | [05-configuracion.md](05-configuracion.md) | Pendiente |
| 6 | Registro estructurado | [06-registro-estructurado.md](06-registro-estructurado.md) | Pendiente |
| 7 | App FastAPI, salud e id de solicitud | [07-app-y-salud.md](07-app-y-salud.md) | Pendiente |
| 8 | Errores HTTP en `problem+json` | [08-errores-http.md](08-errores-http.md) | Pendiente |
| 9 | Roles de base de datos | [09-roles-de-base-de-datos.md](09-roles-de-base-de-datos.md) | Pendiente |
| 10 | Migraciones con Alembic | [10-migraciones-alembic.md](10-migraciones-alembic.md) | Pendiente |
| 11 | Sentencias de Row Level Security | [11-sentencias-rls.md](11-sentencias-rls.md) | Pendiente |
| 12 | Unidad de trabajo con tenant | [12-unidad-de-trabajo.md](12-unidad-de-trabajo.md) | Pendiente |
| 13 | Prueba de aislamiento entre locales | [13-aislamiento-entre-locales.md](13-aislamiento-entre-locales.md) | Pendiente |
| 14 | Docker Compose | [14-docker-compose.md](14-docker-compose.md) | Pendiente |

## Dependencias

- La 0 va antes que todo; la 1 antes que todo lo demás.
- La 2 depende de la 1.
- La 4 depende de la 3.
- Las 5 y 6 dependen solo de la 1 y pueden ir en paralelo.
- La 7 depende de la 5 y la 6; la 8 depende de la 3 y la 7.
- La 9 depende de la 1. La 10 depende de la 5 y la 9.
- La 11 depende solo de la 1.
- La 12 depende de la 4 y la 9; la 13 depende de la 11 y la 12.
- La 14 depende de la 7 y la 10.

## Criterio de cierre de la etapa

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest` pasan en local y en GitHub Actions.
- `docker compose up --build` levanta PostgreSQL, corre las migraciones y la API responde `{"estado": "ok"}` en `/salud`.
- Los tests de integración prueban que un local no ve ni escribe filas de otro y que una consulta sin tenant falla.
- Revisión con `ddd-workflow:code-review` sin hallazgos bloqueantes.

## Fuera de esta etapa

- Unidad de trabajo de plataforma, sin tenant, para `locales`, `usuarios` y `sesiones`: etapa 1.
- Metadata de SQLAlchemy y mapeo imperativo para autogenerar migraciones: etapa 1, con las primeras tablas reales.
- Despacho de eventos de dominio al cerrar la unidad de trabajo: etapa 3.
- Paginación por cursor: con el primer listado (etapa 2).
- Logs de uvicorn y de la librería estándar en JSON (`structlog.stdlib.ProcessorFormatter` y `--log-config`): etapa 1. En la etapa 0 solo los eventos propios salen en JSON.
- Job de CI que levante `docker compose` y consulte `/salud`: etapa 1.
