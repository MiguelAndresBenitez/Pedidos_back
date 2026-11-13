# Etapa 1a — Locales: plan de implementación

> **Para Claude:** cargar cada archivo de tarea cuando toque. Usar el flujo de superpowers:executing-plans o superpowers:subagent-driven-development. Leer `docs/plans/00-conventions.md` antes de cada tarea.

**Objetivo:** que un local dado de alta por consola tenga su tienda pública respondiendo si está abierta y cuándo abre, con todo el dominio de Locales y sus casos de uso listos para el panel de la 1b.

**Arquitectura:** el contexto Locales sobre las fundaciones de la etapa 0.
- **Dominio:** el agregado `Local` con datos, horario por franjas, jornada con zona y hora de corte (los cambios rigen desde la próxima jornada), cierre manual y suspensión, todo con variantes polimórficas y la hora recibida como dato.
- **Persistencia:** `locales` con RLS por operación y `franjas_horarias` con RLS completo, bloqueo optimista (`version`) y dos unidades de trabajo: la del local, que fija `app.local_id`, y la del directorio, que solo resuelve slugs.
- **Entradas:** `GET /api/v1/tiendas/{slug}`, `GET /api/v1/imagenes/{nombre}` y la consola del owner. `minutas/composicion.py` arma adaptadores y casos de uso para las dos.

**Stack nuevo:** `phonenumbers` (WhatsApp) y `pillow` (imágenes).

**Spec:** `docs/superpowers/specs/2026-11-03-etapa-1-identidad-y-locales-design.md` (parte 1a y Sección 4 de la 1a), sobre `docs/superpowers/specs/2026-10-07-backend-minutas-design.md`.

**Revisión DDD/OOP (Opus y Sonnet) aplicada:** la tienda devuelve una vista de lectura calculada en la aplicación, los códigos de las columnas viven en la infraestructura, la versión es de solo lectura, la regla de suspensión se consulta en el agregado, los casos de uso del owner comparten `LocalesPorSlug`, la ruta de imágenes pasa por el puerto y las franjas solo se reescriben si cambia el horario.

**Código verificado:** todo el código del plan se probó en un prototipo antes de escribirlo: ruff, `ruff format`, `mypy --strict` y 272 tests (los de integración contra PostgreSQL 17), más `docker compose up` con el alta y el cambio de zona por consola y la tienda.

---

## Tareas

| # | Tarea | Archivo | Estado |
|---|-------|---------|--------|
| 1 | Dependencias y configuración | [01-dependencias-y-configuracion.md](01-dependencias-y-configuracion.md) | Pendiente |
| 2 | Categorías de error 401 y 403 | [02-errores-401-y-403.md](02-errores-401-y-403.md) | Pendiente |
| 3 | Reloj y unidad de trabajo de plataforma | [03-reloj-y-unidad-de-plataforma.md](03-reloj-y-unidad-de-plataforma.md) | Pendiente |
| 4 | Errores y valores del local | [04-valores-del-local.md](04-valores-del-local.md) | Pendiente |
| 5 | Momento de la semana, franjas y horario | [05-horario.md](05-horario.md) | Pendiente |
| 6 | Reglas de jornada y cambios pendientes | [06-jornada.md](06-jornada.md) | Pendiente |
| 7 | Cierre manual y estado del local | [07-cierre-y-estado.md](07-cierre-y-estado.md) | Pendiente |
| 8 | Tipos, medidas y nombre de imagen | [08-imagen.md](08-imagen.md) | Pendiente |
| 9 | Agregado Local | [09-agregado-local.md](09-agregado-local.md) | Pendiente |
| 10 | Próxima apertura | [10-proxima-apertura.md](10-proxima-apertura.md) | Pendiente |
| 11 | Puertos, unidades de trabajo y casos de uso del owner | [11-casos-de-uso-del-owner.md](11-casos-de-uso-del-owner.md) | Pendiente |
| 12 | Casos de uso del panel del admin | [12-casos-de-uso-del-panel.md](12-casos-de-uso-del-panel.md) | Pendiente |
| 13 | Tablas, migración 0002 y políticas de RLS | [13-tablas-y-migracion.md](13-tablas-y-migracion.md) | Pendiente |
| 14 | Repositorio, directorio y unidades de trabajo sobre SQLAlchemy | [14-repositorio-y-directorio.md](14-repositorio-y-directorio.md) | Pendiente |
| 15 | Procesador de imágenes y almacén en disco | [15-procesador-y-almacen.md](15-procesador-y-almacen.md) | Pendiente |
| 16 | Raíz de composición y fábrica de la app | [16-composicion-y-app.md](16-composicion-y-app.md) | Pendiente |
| 17 | Tienda pública | [17-tienda-publica.md](17-tienda-publica.md) | Pendiente |
| 18 | Imágenes servidas por la API | [18-imagenes-por-http.md](18-imagenes-por-http.md) | Pendiente |
| 19 | Consola del owner | [19-consola-del-owner.md](19-consola-del-owner.md) | Pendiente |
| 20 | Prueba de punta a punta de la 1a | [20-punta-a-punta.md](20-punta-a-punta.md) | Pendiente |
| 21 | Logs de uvicorn en JSON y tipos sin ignore | [21-logs-de-uvicorn-y-tipos.md](21-logs-de-uvicorn-y-tipos.md) | Pendiente |
| 22 | Volumen de imágenes, proxy, CI con Compose y README | [22-docker-ci-y-readme.md](22-docker-ci-y-readme.md) | Pendiente |

## Dependencias

- **Base:** la 1 va antes que todo; la 2 y la 3 dependen de la 1.
- **Dominio:** de la 4 a la 10 van en orden (la 4 depende de la 2).
- **Aplicación:** la 11 depende de la 3 y la 10; la 12 de la 11.
- **Persistencia:** la 13 depende de la 3 y la 4; la 14 de la 11 y la 13.
- **Imágenes:** la 15 depende de la 12.
- **Entradas:** la 16 depende de la 14 y la 15; de la 17 a la 19 van en orden después de la 16 (cada una modifica `app.py` o usa la composición).
- **Cierre:** la 20 depende de la 19; la 21 solo de la 1; la 22 de la 19.

Orden recomendado: correlativo, de la 1 a la 22.

## Criterio de cierre de la etapa 1a

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` y `uv run pytest` pasan, sin ningún `# type: ignore` en `src/` ni en `tests/`.
- La prueba de punta a punta pasa contra PostgreSQL real: alta por consola, horario y logo por caso de uso, tienda abierta con el logo servido y suspensión.
- Las políticas de `locales` están probadas: lectura sin local fijado, ninguna escritura sin él ni con el de otro local, ningún borrado.
- Una edición concurrente con una suspensión falla con `local_modificado_en_paralelo` y no la revierte.
- `alembic check` no encuentra diferencias entre las tablas y las migraciones.
- Con `docker compose up --build`, la consola da de alta un local, `GET /api/v1/tiendas/{slug}` lo devuelve y los logs de uvicorn salen en JSON.
- Revisión con `ddd-workflow:code-review` sin hallazgos bloqueantes.

## Fuera de esta etapa

- **Etapa 1b:** usuarios, membresías, login con Google, sesiones y cookie, control de `Origin`, la consola de admins y sesiones, y los endpoints del panel (incluida la subida de imágenes con el límite de 2 MB al recibir) sobre los casos de uso de la tarea 12.
- **Después:** feriados, horarios por modalidad, adaptador S3 + CDN, restricción de exclusión de franjas en la base.
