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

Las contraseñas solo pueden tener letras, números, `-` y `_`: van dentro de URLs de conexión.
Los roles se crean con el volumen vacío: si cambiás claves después del primer arranque, corré `docker compose down -v`.
