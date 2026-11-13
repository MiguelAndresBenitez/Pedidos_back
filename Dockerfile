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
# El volumen de imágenes hereda este dueño al crearse vacío.
RUN mkdir -p /var/lib/minutas/imagenes && chown minutas /var/lib/minutas/imagenes
USER minutas

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# `--proxy-headers`: la IP real llega del proxy; `FORWARDED_ALLOW_IPS` dice cuál es el proxy.
ENV FORWARDED_ALLOW_IPS=127.0.0.1
CMD ["uvicorn", "--factory", "minutas.api.app:crear_app_desde_entorno", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
