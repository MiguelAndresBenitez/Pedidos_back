# Spec backend — Minutas

2026-10-07 · Miguel

> Versión exportada del doc colaborativo [Spec backend — Minutas](https://claude.ai/code/artifact/a10170a2-6af5-400b-8901-763c27b3c263).

## Contexto y objetivo

El backend de Minutas es la API única que sirve a la tienda del cliente, al panel del local y al panel interno del owner, con los datos de cada local aislados. Se versiona en el repo [Pedidos_back](https://github.com/MiguelAndresBenitez/Pedidos_back), rama `main`.

Minutas es un SaaS de venta online para locales de comida de cualquier rubro. Cada local tiene su tienda en un link propio que comparte en redes; el cliente arma el pedido desde el celular, lo confirma, y el pedido queda en el panel del local y además le llega por WhatsApp, donde se acuerdan pago y envío. El alcance y las decisiones de producto están en el [Brief de proyecto v4](https://claude.ai/code/artifact/aea8ec2c-f8c1-4c0d-a626-6f4fff11b97a) del 06/10/2026; este documento no las repite, define cómo las resuelve el backend.

**Criterio de éxito del MVP:** un local dado de alta por el owner carga su carta, un cliente hace un pedido desde el link sin crear cuenta, y el local lo ve en tiempo real, le cambia el estado y lo imprime.

**Fuera de este documento:** el frontend (tienda y paneles), que se asume en un repo aparte y consume esta API.

## Decisiones del brief que condicionan el backend

De las 15 decisiones y el flujo de estados del brief v4, estas son las que fijan la forma del backend.

| Brief | Qué exige al backend |
| --- | --- |
| D01 — Datos aislados por local | Todo dato de negocio pertenece a un local; ninguna consulta cruza locales |
| D02 — UUIDv7 | Identificadores generados en el dominio, no por la base |
| D04 — Alta por CLI | Comando de consola que invoca los mismos casos de uso que un futuro panel del owner |
| D05 — Un admin, preparado para roles | Usuario–local con rol desde el inicio |
| D06 — Login solo con Google | Verificación de ID token de Google detrás de un puerto de proveedor de identidad; el email debe existir |
| D07 — Grupos de opciones con mín./máx. | Validación de la selección del cliente en el dominio de la carta y del pedido |
| D08 — Copia de nombres y precios | El pedido guarda un snapshot de cada línea y sus opciones |
| D09 — Panel + WhatsApp | La API devuelve el número correlativo y el texto para el link `wa.me` |
| D11 — Sin cálculo de envío | Solo modalidades ofrecidas (delivery, retiro o ambas); el total es el subtotal |
| D12 — Horarios y cierre manual | Franjas semanales que cruzan medianoche, en la zona horaria del local; la API rechaza confirmar con la tienda cerrada |
| D13 — Impresión desde el navegador | La API expone la comanda; el formato de 80/58 mm lo arma el front |
| Estados del pedido | Máquina de estados por modalidad: solo avanzar al siguiente o cancelar con motivo; finales sin reapertura |

## Preguntas abiertas

El brief deja una sola pregunta de producto sin cerrar; el resto son decisiones de arquitectura que este documento tiene que tomar.

- Pedido mínimo: ¿no hay, o cada local puede fijar uno? Está comentada en el brief y sin respuesta. Se asume que no hay.
- Resuelto, ver Modelo de dominio (cuatro contextos) — separación en contextos y sus dependencias.
- Resuelto, ver Multi-tenancy (`local_id` + RLS) — estrategia de aislamiento entre locales: columna `local_id` con filtro en repositorios, Row Level Security de PostgreSQL, o ambas.
- Resuelto, ver Tiempo real (SSE + LISTEN/NOTIFY) — tiempo real del panel: Server-Sent Events o WebSocket, y cómo se publica el evento de pedido nuevo.
- Resuelto, ver Modelo de dominio (contador por jornada) — numeración correlativa por local sin huecos ni duplicados bajo concurrencia.

## Stack

El stack ya está fijado en el brief v4: Python con DDD en el backend, todo en contenedores. La arquitectura interna se define en las secciones siguientes.

| Capa | Elección | Consecuencia en el diseño |
| --- | --- | --- |
| API | FastAPI | Los routers son adaptadores de entrada; el dominio es Python puro, sin FastAPI ni SQLAlchemy |
| Persistencia | PostgreSQL + SQLAlchemy 2.0 + Alembic | Mapeo imperativo en infraestructura; las entidades no heredan de modelos ORM |
| Login | Google (OpenID Connect) | Puerto de proveedor de identidad con un adaptador de Google |
| Imágenes | Puerto de almacenamiento | Adaptador de disco local en desarrollo y de S3 en producción |
| Entorno | Docker Compose | Configuración por variables de entorno; misma imagen para desarrollo y deploy |
| Calidad | Plugin ddd-workflow | Plan por partes con revisión de diseño, y revisión DDD + OOP al cerrar cada etapa |

## Modelo de dominio

El backend es un monolito modular: una API y una base, con cuatro bounded contexts separados por paquete. Cada contexto tiene sus capas `domain/`, `application/` e `infrastructure/` y no importa entidades de otro.

| Contexto | Qué contiene | Agregados |
| --- | --- | --- |
| Identidad | Usuarios, membresías (usuario, local, rol), sesiones, login con Google | `Usuario`, `Sesion` |
| Locales | Datos del local, slug, branding, modalidades, horarios semanales, cierre manual, zona horaria | `Local` |
| Carta | Categorías ordenables, productos, grupos de opciones con mínimo y máximo, sin stock | `Categoria`, `Producto` (con sus grupos y opciones) |
| Pedidos | Pedido con líneas copiadas, numeración correlativa, máquina de estados, cancelación con motivo, texto de WhatsApp, comanda | `Pedido` |

**Dependencias.** Solo Pedidos depende de otros contextos. Al confirmar, consulta a Locales si la tienda está abierta y ofrece la modalidad, y le pide a Carta que valide la selección y devuelva los precios vigentes. Esas consultas son interfaces definidas por Pedidos e implementadas por la capa de aplicación de cada contexto, así Pedidos nunca toca una entidad `Producto`.

**Eventos de dominio.** Pedidos emite `PedidoConfirmado` y `EstadoPedidoCambiado`. El tiempo real del panel se engancha en esos eventos, y a futuro también las notificaciones al cliente.

**Numeración del pedido.** El número es correlativo por local y se reinicia cada jornada: corto para cantarlo en el mostrador, sin huecos ni duplicados bajo concurrencia.

- Jornada = fecha en la zona horaria del local, corrida por una hora de corte configurable por local (por defecto 06:00). Así un turno de 20:00 a 02:00 no se parte en dos numeraciones a medianoche.
- Tabla `contadores_pedido (local_id, jornada, ultimo_numero)`, con RLS como toda tabla del local.
- Dentro de la misma transacción que guarda el pedido: `INSERT … ON CONFLICT (local_id, jornada) DO UPDATE SET ultimo_numero = contadores_pedido.ultimo_numero + 1 RETURNING ultimo_numero`. El bloqueo de fila serializa los pedidos de un mismo local; locales distintos no se bloquean entre sí.
- Si la transacción falla, el incremento se deshace: no quedan huecos.
- El pedido guarda `jornada` y `numero`, con restricción única `(local_id, jornada, numero)`. Su identidad sigue siendo el UUIDv7; el número es solo para personas.
- El panel y la comanda muestran el número con tres dígitos (`#042`); el historial lo acompaña con la fecha de la jornada.

**Alternativa descartada.** Fusionar Locales y Carta en un contexto Tienda: más simple al inicio, pero mezcla configuración del local y carta, que cambian por motivos distintos.

## Multi-tenancy, autenticación y roles

Cada local es un tenant dentro de una sola base y un solo esquema, aislado en dos capas: los repositorios filtran por `local_id` y PostgreSQL lo vuelve a exigir con Row Level Security (RLS). Si una consulta olvida el filtro, la base devuelve cero filas en vez de datos de otro local.

**Tablas de plataforma y tablas del local.** `locales`, `usuarios` y `membresias` (usuario, local, rol) son de plataforma y no llevan RLS: se consultan antes de saber de qué local se trata (resolver un slug, validar un login). Todo lo demás (categorías, productos, opciones, horarios, pedidos, contadores) lleva `local_id` no nulo, indexado, con RLS activado y forzado.

**Cómo se fija el tenant en cada request:**

1. Tienda pública: el slug de la URL se resuelve contra `locales` y da el `local_id`.
2. Panel: el `local_id` sale de la membresía del usuario autenticado, nunca de un parámetro del cliente.
3. La unidad de trabajo abre la transacción y ejecuta `SET LOCAL app.local_id = '<uuid>'`. Al ser `LOCAL`, el valor muere con la transacción y no se filtra entre conexiones del pool.
4. Los repositorios reciben el `local_id` en su construcción y lo aplican en cada consulta.

**Política RLS** en cada tabla del local:

```sql
ALTER TABLE productos ENABLE ROW LEVEL SECURITY;
ALTER TABLE productos FORCE ROW LEVEL SECURITY;
CREATE POLICY aislamiento_local ON productos
  USING (local_id = current_setting('app.local_id')::uuid)
  WITH CHECK (local_id = current_setting('app.local_id')::uuid);
```

**Roles de base de datos.** La app se conecta con un rol sin `BYPASSRLS` que no es dueño de las tablas. Las migraciones de Alembic corren con un rol dueño, separado. Si `app.local_id` no está seteado, `current_setting` falla y la consulta se corta: falla cerrado.

**Autenticación.** El front obtiene un ID token de Google y lo envía a la API. El adaptador de Google verifica firma, audiencia, expiración y `email_verified`; el caso de uso busca el email en `usuarios` y rechaza si no está dado de alta. Si el email existe, se crea una sesión en la base.

**Sesión.** La sesión vive en la base y el navegador solo guarda un ID opaco: se revoca al instante borrando la fila, y rol y membresía se leen frescos en cada request.

- Tabla `sesiones`, de plataforma y sin RLS: id, usuario, hash SHA-256 del token, creada, último uso, expira, IP y user-agent.
- Token aleatorio de 256 bits; en la base se guarda solo su hash, así un volcado de la tabla no sirve para entrar.
- Cookie `httpOnly`, `Secure`, `SameSite=Lax`, sin datos del usuario.
- Expiración deslizante: cada uso extiende la sesión, con un tope absoluto; el panel abierto todo el día en la tablet no se desloguea.
- Logout borra la fila (borrado físico, única excepción al borrado lógico); el CLI puede revocar todas las sesiones de un usuario.
- Las sesiones vencidas se rechazan al validar y se purgan periódicamente.
- Los valores de expiración y tope son configuración por variables de entorno.

**Roles.** La membresía guarda el rol; hoy existe solo `admin`. Los permisos se chequean en la capa de aplicación por caso de uso, así sumar cajero o cocina es agregar un rol y sus permisos.

**Owner de la plataforma.** En el MVP el owner no tiene usuario en la app: opera por CLI dentro del contenedor, y su barrera es el acceso a la infraestructura. El CLI es un adaptador de entrada más, que invoca los mismos casos de uso que usará el futuro panel (`DarDeAltaLocal`, `DarDeAltaAdmin`, `RevocarSesiones`) sobre tablas de plataforma, sin fijar tenant, y registra cada comando en el log.

El panel del owner y el acceso de soporte a los datos de un local quedan para una versión posterior, con estos puntos de enganche ya previstos:

- Rol de plataforma `owner` en `Usuario`, separado de las membresías porque no está atado a un local.
- Acceso de soporte como caso de uso explícito: el owner elige un local, la sesión fija ese `local_id` por un tiempo acotado y cada acción queda auditada con el owner como actor.
- RLS no cambia: el owner también opera con un tenant fijado, nunca con acceso global a los datos de los locales.

**Tests de aislamiento.** Dos locales con datos: ningún repositorio devuelve datos del otro, y una consulta SQL cruda con el tenant de A no ve filas de B.

## API

La API es REST bajo `/api/v1`, en JSON, con OpenAPI generado por FastAPI y tres superficies: tienda pública, autenticación y panel.

**Convenciones**

- Precios en pesos argentinos como enteros.
- Errores en `application/problem+json` (RFC 9457) con un `code` del dominio: `tienda_cerrada`, `seleccion_invalida`, `transicion_invalida`, `limite_de_pedidos`, etc.
- Listados con paginación por cursor sobre el UUIDv7.
- Todos los borrados son lógicos salvo el de sesiones (ver abajo).

**Tienda pública** (sin login; el local se resuelve por slug)

| Método | Ruta | Para qué |
| --- | --- | --- |
| GET | `/tiendas/{slug}` | Datos del local, si está abierto ahora y modalidades |
| GET | `/tiendas/{slug}/carta` | Categorías, productos, grupos y opciones |
| POST | `/tiendas/{slug}/pedidos` | Confirmar el pedido; devuelve id, número y link `wa.me` armado |
| GET | `/tiendas/{slug}/pedidos/{id}` | Pantalla de pedido enviado |

**Autenticación**

| Método | Ruta | Para qué |
| --- | --- | --- |
| POST | `/auth/google` | Recibe el ID token de Google y crea la sesión |
| POST | `/auth/logout` | Revoca la sesión |
| GET | `/auth/me` | Usuario y local de la sesión |

**Panel** (con sesión; el local sale de la membresía)

| Método | Ruta | Para qué |
| --- | --- | --- |
| GET, PATCH | `/panel/local` | Datos, branding, modalidades, zona horaria, hora de corte |
| PUT | `/panel/local/horarios` | Reemplazar las franjas semanales |
| POST | `/panel/local/cierre-manual` | Cerrar o reabrir la tienda |
| POST | `/panel/local/logo`, `/panel/local/portada` | Subir imágenes |
| GET, POST | `/panel/categorias` | Listar y crear |
| PATCH, DELETE | `/panel/categorias/{id}` | Editar y borrar (lógico) |
| PUT | `/panel/categorias/orden` | Reordenar |
| GET, POST | `/panel/productos` | Listar y crear, con grupos y opciones |
| GET, PUT, DELETE | `/panel/productos/{id}` | Ver, reemplazar el agregado completo y borrar (lógico) |
| POST | `/panel/productos/{id}/foto` | Subir foto |
| PATCH | `/panel/productos/{id}/stock` | Marcar o desmarcar sin stock |
| GET | `/panel/pedidos` | Historial con filtros: estado, modalidad, jornada, rango de fechas |
| GET | `/panel/pedidos/{id}` | Detalle |
| POST | `/panel/pedidos/{id}/avanzar` | Siguiente estado; recibe el estado actual esperado para evitar dobles clics |
| POST | `/panel/pedidos/{id}/cancelar` | Cancelar con motivo |
| GET | `/panel/pedidos/{id}/comanda` | Datos de la comanda para imprimir |
| GET | `/panel/pedidos/stream` | SSE |

**Producto como agregado completo.** Grupos y opciones se editan con un `PUT` del producto entero, así las reglas de mínimo y máximo se validan juntas y el agregado nunca queda a medio armar.

**Borrado lógico.** Nada se borra físicamente: cada entidad borrable lleva `eliminado_en` (nulo mientras está activa) y los repositorios excluyen las eliminadas por defecto.

- Las restricciones únicas son parciales (`WHERE eliminado_en IS NULL`), así un slug o nombre borrado se puede volver a usar.
- Una categoría con productos activos no se puede borrar: responde `409 categoria_con_productos`.
- Los pedidos no se borran: se cancelan. Un producto borrado no afecta pedidos viejos, que guardan su copia (D08).
- Única excepción: las sesiones se borran físicamente al hacer logout, al revocarlas o al vencer; no se guarda historial de accesos.
- Las imágenes reemplazadas quedan en el almacenamiento; no se eliminan.

**Límite de pedidos.** `POST /tiendas/{slug}/pedidos` acepta hasta 5 pedidos cada 15 minutos por IP en un mismo local; el sexto responde `429 limite_de_pedidos`. Se resuelve contando en la base los pedidos recientes con el mismo hash de IP, sin infraestructura extra; el pedido guarda ese hash, no la IP en claro. El backend recalcula todos los precios: el total que manda el cliente se ignora.

## Tiempo real e impresión

El panel recibe los pedidos por Server-Sent Events (SSE), y las instancias de la API se enteran de los cambios por `LISTEN/NOTIFY` de PostgreSQL, sin broker extra. El estado de los pedidos siempre se lee por REST; el stream solo avisa que algo cambió.

**Recorrido de un evento:**

1. El agregado `Pedido` registra `PedidoConfirmado` o `EstadoPedidoCambiado`.
2. Al cerrar la unidad de trabajo, un despachador entrega los eventos a sus handlers dentro de la misma transacción.
3. El handler de tiempo real ejecuta `pg_notify('pedidos', <json>)`. PostgreSQL entrega la notificación solo si la transacción hace commit: nunca se avisa un pedido que no quedó guardado.
4. Cada instancia de la API mantiene una conexión dedicada con `LISTEN pedidos` y reparte el evento en memoria a los streams abiertos de ese `local_id`.
5. El panel recibe el evento, pide el pedido por REST y dispara el aviso sonoro (eso es del front).

**Payload de la notificación:** `local_id`, `pedido_id`, tipo de evento, número y estado. Solo identificadores y datos mínimos, lejos del límite de 8000 bytes de `NOTIFY`, y sin datos personales del cliente en el canal.

**Endpoint SSE** `GET /panel/pedidos/stream`:

- Autenticado con la cookie de sesión; el `local_id` sale de la membresía, igual que en el resto del panel.
- Un comentario de keep-alive cada 20 segundos, para que proxies y balanceadores no corten la conexión.
- Sin replay de eventos: al reconectar, el panel vuelve a pedir la lista de pedidos activos. Es más simple que `Last-Event-ID` y no pierde nada porque la verdad está en la base.

**Notificaciones al cliente:** ninguna en el MVP (brief v4). El handler de eventos es el punto de enganche para sumar WhatsApp oficial después.

**Impresión.** `GET /panel/pedidos/{id}/comanda` devuelve la comanda como datos estructurados (número, modalidad, cliente, líneas con opciones y notas, subtotal). El front la maqueta para 80 o 58 mm y la imprime desde el navegador; el backend no genera PDF.

**Supuesto técnico:** la API es asíncrona de punta a punta (SQLAlchemy async sobre el driver `asyncpg`), porque SSE mantiene conexiones abiertas y el `LISTEN` necesita una conexión async dedicada.

## Errores, testing y despliegue

El dominio falla con excepciones propias que solo se traducen a HTTP en el borde; los tests van de reglas puras a PostgreSQL real; y todo corre en contenedores, sin atarse a un proveedor de nube.

**Errores**

- El dominio lanza excepciones propias (`TiendaCerrada`, `SeleccionInvalida`, `TransicionInvalida`). Un manejador de FastAPI las traduce a `problem+json` con su código HTTP: 404, 409, 422 o 429.
- Un error no previsto devuelve un 500 genérico sin detalles internos y se loguea con su `request_id`.
- Logs estructurados en JSON con `request_id` y `local_id` en cada línea.

**Testing**

| Nivel | Qué cubre | Cómo |
| --- | --- | --- |
| Dominio | Reglas de mínimo y máximo, máquina de estados, horarios que cruzan medianoche, jornada y hora de corte | Unitarios puros, sin base ni framework |
| Aplicación | Casos de uso y permisos | Repositorios en memoria |
| Integración | Repositorios, RLS, contador concurrente, `LISTEN/NOTIFY` | PostgreSQL real con testcontainers |
| Aislamiento | Un local no ve datos de otro | Por repositorio y con SQL crudo |
| API | Flujos de punta a punta | Cliente HTTP de FastAPI (`httpx`), Google reemplazado por un falso detrás del puerto de identidad |

Herramientas: `pytest`, `ruff` y `mypy`.

**Despliegue**

- Docker Compose con API y PostgreSQL; una sola imagen para desarrollo y producción, configurada por variables de entorno.
- Migraciones de Alembic como paso separado del arranque, con el rol dueño de las tablas.
- Nube a definir, probablemente AWS (brief D15); el diseño no depende del proveedor.

## Plan de módulos

El backend se entrega en cinco etapas verticales, en orden de dependencia; al cerrar la etapa 4 se cumple el criterio de éxito del MVP. Cada etapa tiene su propio plan con `ddd-workflow:plan-create` y su revisión DDD + OOP al cerrarla.

| # | Etapa | Qué incluye | Queda funcionando |
| --- | --- | --- | --- |
| 0 | Fundaciones | Paquetes por contexto, Docker Compose, configuración por entorno, roles de base, Alembic, unidad de trabajo con `SET LOCAL app.local_id`, base de RLS, UUIDv7, errores `problem+json`, logs, `pytest`, `ruff` y `mypy` | La API arranca, migra y tiene el aislamiento probado con una tabla de ejemplo |
| 1 | Identidad y Locales | CLI de alta de local y admin, login con Google, sesiones, membresía, `/panel/local`, horarios, cierre manual, jornada con hora de corte, almacenamiento de imágenes, `GET /tiendas/{slug}` | Un local dado de alta por CLI, con su admin logueado y configurándolo |
| 2 | Carta | Categorías ordenables, productos con grupos y opciones, sin stock, foto, borrado lógico, `GET /tiendas/{slug}/carta` | El admin carga la carta y la tienda la muestra |
| 3 | Pedidos: checkout | Confirmación del pedido, validación contra Carta y Locales, copia de precios, numeración por jornada, link `wa.me`, límite de 5 pedidos cada 15 minutos por IP, pantalla de pedido enviado | Un cliente confirma un pedido real |
| 4 | Pedidos: gestión | Historial con filtros, avanzar y cancelar, máquina de estados, SSE con `LISTEN/NOTIFY`, comanda | El local recibe el pedido en vivo, lo avanza y lo imprime |

Próximo paso: con este spec aprobado, se versiona como `.md` en `Pedidos_back/docs/superpowers/specs/` y se escribe el plan de la etapa 0.
