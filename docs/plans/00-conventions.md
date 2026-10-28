# Convenciones de los planes

> **Para Claude:** leer esto ANTES de escribir o ejecutar cualquier tarea. PREGUNTAR al usuario antes de modificarlo.

Fuente de diseño: `docs/superpowers/specs/2026-10-07-backend-minutas-design.md`.

## Idioma

Todo el código va en español: clases, métodos, variables, tests, tablas, columnas, archivos y directorios. Es el mismo lenguaje que el negocio y que la spec (lenguaje ubicuo).

- Identificadores en ASCII, sin tildes ni eñes: `categoria`, `aplicacion`, `anio`. Los textos para personas (mensajes, docstrings, comentarios) sí llevan tildes.
- Lo que viene de Python o de una librería queda como es: `__init__`, `__aenter__`, `session`, `pytest`, `event` (clave de structlog), `request_id`.
- Los commits van en español con el prefijo convencional en inglés: `feat(pedidos): confirmar pedido`.

## Convenciones de nombres

### Métodos y funciones
- Guard clauses: `asegurar_<condicion>`. No devuelven nada y lanzan un error de dominio si no se cumple (`asegurar_tienda_abierta`).
- Fábricas: `crear_<sustantivo>` como función, y `generar` o `desde_<origen>` como classmethod (`LocalId.generar()`, `LocalId.desde_texto(...)`).
- Consultas: `obtener_<sustantivo>_por_<clave>` (`obtener_local_por_slug`).
- Comandos: `<verbo>_<sustantivo>` en infinitivo (`confirmar_pedido`, `cancelar_pedido`).

### Tests
- Patrón: `test_<accion_o_metodo>_<escenario>`.
- Ejemplos: `test_generar_crea_uuid_version_7`, `test_crear_con_uuid_version_4_falla`.

### Archivos y directorios
- Capas por contexto: `src/minutas/<contexto>/{dominio,aplicacion,infraestructura}/`.
- Contextos: `identidad`, `locales`, `carta`, `pedidos`. Lo común a todos va en `compartido`.
- `src/minutas/api/` es la raíz de composición HTTP: fábrica de la app, middleware y manejadores de errores.
- Entidades y value objects: `<nombre>.py` (`pedido.py`, `local_id.py`).
- Casos de uso: `<accion>_<sustantivo>.py` (`confirmar_pedido.py`).
- Repositorios: `repositorio_de_<plural>.py` (`repositorio_de_pedidos.py`).
- Adaptadores: `<puerto>_<tecnologia>.py` (`unidad_de_trabajo_sqlalchemy.py`).
- Tests: `tests/unitarios/<contexto>/`, `tests/integracion/` (PostgreSQL real) y `tests/api/` (HTTP). Los archivos son `test_<tema>.py`, sin `__init__.py` (pytest corre con `--import-mode=importlib`).
- Código de apoyo para tests: `tests/soporte/` (paquete con `__init__.py`), importable como `soporte.*` gracias a `pythonpath = ["tests"]`. Los fixtures se tipan con esas clases, nunca con `Any`. Ejemplo: `base_de_prueba: BaseDePrueba`.
- Cada módulo de `tests/integracion/` declara `pytestmark = pytest.mark.integracion`.
- Migraciones: `migraciones/versions/NNNN_<slug>.py`, con revisión numérica correlativa (`--rev-id 0002`).

### Base de datos
- Tablas en plural y `snake_case` (`productos`, `contadores_pedido`). Columnas en `snake_case` (`local_id`, `eliminado_en`).
- Roles: `minutas_owner` (dueño de las tablas, corre migraciones) y `minutas_app` (la API, sin `BYPASSRLS`).
- SQL escrito a mano en código de producción: constantes a nivel de módulo, en mayúsculas, con `text(...)` y parámetros con nombre (`FIJAR_LOCAL`, `INSERTAR_NOTA`). Nunca se interpola un valor en el SQL.

### Commits
- Formato: `tipo(alcance): descripción en español`, con tipo en inglés (`feat`, `fix`, `test`, `refactor`, `chore`, `docs`, `ci`).
- Alcances: `proyecto`, `ci`, `compartido`, `api`, `infra`, `identidad`, `locales`, `carta`, `pedidos`.

## Patrones de diseño

| Patrón | Cuándo | Ejemplo |
|--------|--------|---------|
| Value Object | Valores inmutables con validación propia | `Identificador`, `LocalId` (`@dataclass(frozen=True, slots=True)`) |
| Puerto (`typing.Protocol`) | La aplicación necesita algo de infraestructura | `UnidadDeTrabajo` |
| Adapter | Implementación concreta de un puerto | `UnidadDeTrabajoSQLAlchemy` |
| Jerarquía de errores por categoría | Errores de dominio que el borde traduce | `TiendaCerrada(ReglaDeNegocioIncumplida)` |
| Tabla de despacho (dict) | Elegir comportamiento según tipo, sin `if` encadenados | `ESTADOS_POR_CATEGORIA` en `api/errores_http.py` |
| State | El comportamiento de una entidad cambia según su estado | Estados de `Pedido` (etapa 4) |

## Requisitos de detalle

**Cada archivo de tarea DEBE incluir:**
- [ ] Código de test exacto, con sus asserts (no "escribir tests para X")
- [ ] Código de implementación exacto (no "implementar la funcionalidad")
- [ ] Salida esperada de los comandos (mensajes de error concretos)
- [ ] Rutas exactas desde la raíz del repo
- [ ] Mensaje de commit con formato convencional y el trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

Las tareas de configuración sin lógica propia (herramientas, CI, Docker) reemplazan el ciclo rojo-verde por pasos de verificación con comandos y salida esperada.

## Decisiones transversales

| Decisión | Motivo | Aplica a |
|----------|--------|----------|
| Los identificadores son UUIDv7 y se generan en el dominio | Ordenables en el tiempo; spec D02 | Toda entidad |
| El dominio usa dataclasses y Python puro, sin pydantic, FastAPI ni SQLAlchemy | Dominio aislado de la infraestructura | `*/dominio/` |
| Los errores de dominio no conocen HTTP; el borde los traduce por categoría | Separación de capas | `compartido/dominio/errores.py`, `api/errores_http.py` |
| Los puertos son `typing.Protocol` | Tipado estructural sin herencia | `*/aplicacion/` |
| Todo es asíncrono (SQLAlchemy async + asyncpg) | SSE y `LISTEN` necesitan conexiones async | Infraestructura y API |
| El tenant se fija con `set_config('app.local_id', ..., true)` dentro de la transacción | Vale solo para esa transacción y no se filtra entre conexiones del pool | Unidad de trabajo |
| El aislamiento usa filtro en los repositorios y además RLS | Si una consulta olvida el filtro, la base devuelve cero filas | Toda tabla del local |
| `mypy --strict` y `ruff` sin excepciones salvo las listadas en `pyproject.toml` | Errores de tipo en CI, no en producción | Todo el código |

## Reglas de arquitectura

### Dependencias entre capas
```
api → aplicacion → dominio
infraestructura → aplicacion → dominio
```
- Un contexto no importa el `dominio` de otro contexto. Se comunican por interfaces definidas por quien consume.
- Todos pueden importar `compartido`.
- `api` es la raíz de composición y puede importar cualquier capa.

### Condicionales permitidos
- Mappers de infraestructura (base → dominio)
- Manejadores de excepciones (excepción → HTTP)
- Validación dentro de value objects (`if not valido: raise`)
- Tests

### Condicionales prohibidos
- Métodos de entidades (usar State)
- Lógica de casos de uso (delegar en el dominio)
- Orquestación de servicios

## Registro de decisiones

| Fecha | Decisión | Motivo | Tareas afectadas |
|-------|----------|--------|------------------|
| 2026-10-28 | Código íntegramente en español, con identificadores ASCII | Lenguaje ubicuo con el negocio y la spec | Todas |
| 2026-10-28 | Python 3.13, `uv`, `uuid-utils`, testcontainers, GitHub Actions y pre-commit | Aprobado para la etapa 0 | Etapa 0 |
| 2026-10-28 | Las tareas de configuración se verifican con comandos en lugar de TDD | No tienen lógica que testear | Etapa 0: 00, 02, 14 |
| 2026-10-28 | `tests/soporte/` con `pythonpath = ["tests"]` para tipar fixtures; marca `integracion`; SQL como constantes `text(...)`; alcances de commit fijos | Extracción tras 10 tareas, aprobada por el usuario | Etapa 0: 01, 09, 10, 12, 13 |
