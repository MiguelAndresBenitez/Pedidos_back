# Tarea 22: Volumen de imágenes, proxy, CI con Compose y README

**Archivos:**
- Modificar: `Dockerfile`
- Modificar: `compose.yaml`
- Modificar: `.github/workflows/ci.yml`
- Modificar: `README.md`

---

## Decisiones de diseño

**¿Por qué crear el directorio de imágenes en la imagen de Docker?**
- Un volumen con nombre que se monta vacío hereda el dueño del directorio de la imagen. Sin él, Docker lo crearía como root y la API (usuario 10001) no podría escribir.

**¿Por qué `--proxy-headers`?**
- El diseño despliega detrás de un proxy en un solo dominio: la IP real llega en `X-Forwarded-For` y la usa el límite de pedidos de la etapa 3. `FORWARDED_ALLOW_IPS` dice qué IP es la del proxy; por defecto, solo `127.0.0.1`, y en producción se configura con la del proxy.

**¿Qué prueba el job `compose` de la CI?**
- Lo que los tests no cubren: que la imagen construya, que las migraciones corran con el owner, que la API arranque, que la consola funcione dentro del contenedor y que la tienda responda. Es el pendiente de la etapa 0.

**¿Por qué verificación y no TDD?**
- Es configuración sin lógica propia, como las tareas de infraestructura de la etapa 0.

---

## Paso 1: Cambiar la imagen y Compose

`Dockerfile` (cambios):

```diff
@@ -15,7 +15,11 @@ RUN uv sync --frozen --no-dev
 
 RUN useradd --system --uid 10001 minutas
+# El volumen de imágenes hereda este dueño al crearse vacío.
+RUN mkdir -p /var/lib/minutas/imagenes && chown minutas /var/lib/minutas/imagenes
 USER minutas
 
 ENV PATH="/app/.venv/bin:$PATH"
 EXPOSE 8000
-CMD ["uvicorn", "--factory", "minutas.api.app:crear_app_desde_entorno", "--host", "0.0.0.0", "--port", "8000"]
+# `--proxy-headers`: la IP real llega del proxy; `FORWARDED_ALLOW_IPS` dice cuál es el proxy.
+ENV FORWARDED_ALLOW_IPS=127.0.0.1
+CMD ["uvicorn", "--factory", "minutas.api.app:crear_app_desde_entorno", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

`compose.yaml` (cambios):

```diff
@@ -37,4 +37,6 @@ services:
       MINUTAS_NIVEL_DE_REGISTRO: ${MINUTAS_NIVEL_DE_REGISTRO:-INFO}
       MINUTAS_ENTORNO: desarrollo
+    volumes:
+      - imagenes:/var/lib/minutas/imagenes
     ports:
       - "127.0.0.1:8000:8000"
@@ -50,2 +52,3 @@ services:
 volumes:
   datos-postgres:
+  imagenes:
```

## Paso 2: Agregar el job de CI

`.github/workflows/ci.yml` (cambios):

```diff
@@ -25,2 +25,25 @@ jobs:
       - name: Tests
         run: uv run pytest -v
+
+  compose:
+    runs-on: ubuntu-latest
+    steps:
+      - uses: actions/checkout@v4
+      - name: Preparar el entorno
+        run: cp .env.ejemplo .env
+      - name: Levantar base, migraciones y API
+        run: docker compose up --build --detach --wait api
+      - name: Salud
+        run: curl --fail --silent --show-error http://127.0.0.1:8000/salud
+      - name: Alta de un local por consola
+        run: >-
+          docker compose exec -T api python -m minutas.cli alta-local
+          --slug demo --nombre Demo --whatsapp "0351 15 512-3456"
+      - name: Tienda pública
+        run: curl --fail --silent --show-error http://127.0.0.1:8000/api/v1/tiendas/demo
+      - name: Logs
+        if: failure()
+        run: docker compose logs
+      - name: Bajar
+        if: always()
+        run: docker compose down --volumes
```

## Paso 3: Documentar la consola del owner

`README.md` (cambios):

```diff
@@ -25,2 +25,14 @@ curl localhost:8000/salud
 Las contraseñas solo pueden tener letras, números, `-` y `_`: van dentro de URLs de conexión.
 Los roles se crean con el volumen vacío: si cambiás claves después del primer arranque, corré `docker compose down -v`.
+
+## Operaciones del owner
+
+La consola corre dentro del contenedor de la API, con su misma configuración:
+
+```bash
+docker compose exec api python -m minutas.cli alta-local --slug la-esquina --nombre "La Esquina" --whatsapp "0351 15 512-3456"
+docker compose exec api python -m minutas.cli cambiar-zona-horaria --slug la-esquina --zona America/Santiago
+docker compose exec api python -m minutas.cli --help
+```
+
+Comandos: `alta-local`, `cambiar-slug`, `cambiar-zona-horaria`, `suspender-local` y `reactivar-local`.
```

## Paso 4: Verificar con Docker Compose

```bash
cp .env.ejemplo .env
docker compose up --build --detach --wait api
curl -fsS http://127.0.0.1:8000/salud
docker compose exec -T api python -m minutas.cli alta-local --slug demo --nombre Demo --whatsapp "0351 15 512-3456"
docker compose exec -T api python -m minutas.cli cambiar-zona-horaria --slug demo --zona America/Santiago
curl -fsS http://127.0.0.1:8000/api/v1/tiendas/demo
docker compose logs api | tail -2
docker compose down --volumes
```

Expected:
- `{"estado":"ok"}`.
- `Local 'demo' dado de alta con id ...`, con su línea JSON `comando_ejecutado`.
- `El local 'demo' pasa a America/Santiago desde la jornada del <mañana>`.
- La tienda con `"whatsapp":"5493515123456"`, `"zona_horaria":"America/Argentina/Buenos_Aires"` (el cambio todavía no rige), `"abierto_ahora":false` y `"proxima_apertura":null` (sin horarios).
- Los logs de uvicorn en JSON, con `request_id`.

## Paso 5: Commit

```bash
git add Dockerfile compose.yaml .github/workflows/ci.yml README.md
git commit -m "ci(infra): volumen de imágenes, proxy y job de compose" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
