# Minutas — Etapa 1 (Identidad y Locales): diseño

2026-11-03 · Miguel

> Reemplaza a la minuta "Etapa 1 (Identidad y Locales): diseño en curso" (PDF). Incorpora la revisión de esa minuta y completa la Sección 3.
>
> **Actualizado el 2026-11-13:** se cierran los pendientes de la 1a (bloqueo optimista, WhatsApp, próxima apertura, superposición de franjas, comando y cambio pendiente de zona horaria, alcance de 1a y 1b) y se suma la Sección 4 de la 1a. La Sección 4 de la 1b sigue pendiente.
> Spec general: [`2026-10-07-backend-minutas-design.md`](2026-10-07-backend-minutas-design.md).

## Contexto

Al terminar la etapa 1, un local dado de alta por consola queda con su administrador logueado con Google y configurando la tienda. La etapa se entrega en dos partes:

| Parte | Qué incluye | Queda funcionando |
| --- | --- | --- |
| **1a — Locales** | Agregado `Local` (datos, branding, modalidades, horarios, jornada, hora de corte, zona horaria, cierre manual, suspensión) con todos sus casos de uso, procesamiento y almacén de imágenes, consola del owner para locales, `GET /api/v1/tiendas/{slug}` y `GET /api/v1/imagenes/{nombre}` | Un local dado de alta por consola, con su tienda pública respondiendo si está abierta y cuándo abre |
| **1b — Identidad** | Usuarios, membresía (rol admin), login con Google, sesiones y logout, consola para admins y sesiones, y los endpoints del panel del local sobre los casos de uso de la 1a | El admin se loguea y configura su local desde el panel |

La 1a es dominio puro y de bajo riesgo; la 1b suma lo que depende de Google, cookies y despliegue. Los endpoints del panel (datos, horarios, cierre, imágenes) van en la 1b porque necesitan login: en la 1a los casos de uso del admin existen y se prueban, pero sin entrada HTTP.

## Decisiones tomadas

| Tema | Decisión | Descartado y por qué |
| --- | --- | --- |
| Cierre manual | Dos acciones: "cerrar por hoy" (vale hasta que empieza la jornada siguiente) y "cerrar hasta nuevo aviso" (hasta que alguien reabra). | Solo una de las dos: o se olvidan de reabrir, o no cubre vacaciones. |
| Horarios | Varias franjas por día, pueden cruzar medianoche, sin superponerse. El panel reemplaza la semana entera de una vez. Se guardan en una tabla propia, una fila por franja. | Una franja por día (no sirve a quien corta al mediodía); franjas por modalidad (se puede sumar después); `jsonb` dentro de `locales` (la base no ve el contenido). |
| Hora de corte | Un cambio rige **desde la próxima jornada**: la jornada nunca retrocede. | Cambio inmediato: correr el corte para más tarde hace retroceder la jornada, reabre un "cerrar por hoy" y rompe la numeración de pedidos. |
| Tiempo | Los instantes (sesiones, pedidos, cierres) se guardan en UTC; las franjas y la hora de corte, en hora local, con la zona horaria del local. | Todo en UTC: "abre a las 20:00" se correría sola si el país cambia de huso u horario de verano. |
| Zona horaria | Una por local, por defecto `America/Argentina/Buenos_Aires`; la cambia solo el owner con `cambiar-zona-horaria`. Como la hora de corte, el cambio rige **desde la próxima jornada**. | Sin campo: habría que migrar al salir del país. Editable en el panel: no hace falta hoy. Cambio inmediato: pasar a una zona con menos horas hace retroceder la jornada. |
| Logo y portada | Disco, detrás del puerto `AlmacenDeImagenes`, servidas por la API con caché permanente; S3 + CDN entra después como otro adaptador. Se re-codifican a WebP con tamaño máximo. | Guardar el original: puede traer el GPS de la foto y pesar de más. Servirlas desde el proxy: obliga a compartir disco entre servidores. |
| Instancias | Una sola instancia de la API mientras las imágenes estén en disco. Antes de escalar, se pasa a S3. | — |
| Login | Botón de Google en el panel; el backend verifica el ID token con `google-auth`, atado al navegador con un `nonce`. Solo entra quien el owner dio de alta. El primer login vincula la cuenta de Google (`sub`); los siguientes se buscan por `sub`. | Flujo con redirección y client secret: más código y un secreto que guardar. Identificar solo por email: el email de una cuenta de Google puede cambiar o reasignarse. |
| Sesiones | Cookie `__Host-sesion` `HttpOnly` con token opaco; vencen tras 7 días sin uso y a los 30 días sí o sí. CSRF: `SameSite=Lax` + `Origin` permitido en toda escritura. El prefijo `__Host-` (y por lo tanto `Secure`) va siempre, también en desarrollo y en los tests. | Cookie configurable por entorno (sin `Secure` en desarrollo): una configuración equivocada en producción mandaría la sesión sin protección. Chrome y Firefox aceptan `Secure` en `http://localhost`; Safari no, y el equipo no lo usa (quien lo necesite levanta el front con HTTPS local). |
| Despliegue | Un solo dominio (`minutas.app`, provisorio) con un proxy que reparte por ruta: `/api/*` al backend, el resto al front. Front y back en servidores distintos. | Subdominios: obliga a configurar CORS y cualquier subdominio cuenta como "mismo sitio". Dominios distintos: la cookie `Lax` no viaja. |
| Edición del panel | Bloqueo optimista entre solicitudes: el panel recibe la versión del local en un `ETag` y la devuelve en `If-Match` en toda escritura, obligatorio. | Bloqueo solo dentro de la transacción: un formulario viejo (la compu abierta desde hace rato mientras se editó desde el celular) pisaría los cambios sin aviso, sobre todo con el `PUT` de horarios que reemplaza la semana entera. |
| Slug | Lo fija y lo cambia solo el owner por consola. 3 a 40 caracteres `a-z 0-9 -`, único, sin palabras reservadas (`api`, `panel`, `admin`…). Las reservadas se controlan al elegir el slug (alta y cambio), no al cargarlo: la lista puede crecer sin dejar locales existentes sin poder abrirse. | Que lo cambie el admin: rompería el link publicado en redes sin querer. |
| Aislamiento | Toda escritura exige el local fijado en la transacción, sin excepción. Se leen sin local fijado solo `locales`, para resolver el slug, y `membresias`, para saber de qué local es el usuario de la sesión. | `locales` sin RLS: un descuido permitiría que un local escriba datos de otro. |
| Concurrencia | Bloqueo optimista del `Local`: columna `version`; si otro lo guardó desde que se leyó, `409 local_modificado_en_paralelo` y se recarga. | Bloqueo pesimista (`FOR UPDATE`): una lectura especial por repositorio. Nada: una edición del panel podía revertir una suspensión hecha al mismo tiempo. |
| WhatsApp | Se interpreta con `phonenumbers` (Argentina por defecto), tiene que ser un celular y se guarda en el formato de WhatsApp (`549…`). | Regex genérico: acepta números con los que el link `wa.me` no funciona. Exigir el formato final: el admin no sabe quitar el 0 y el 15. |
| Próxima apertura | La calcula el dominio y la devuelve la tienda pública. | Calcularla en el front: no conoce el cierre manual y anunciaría una apertura que no va a pasar. |
| Superposición de franjas | La controla solo el dominio (`Horario`). | Restricción de exclusión en la base: extensión, `multirange` y restricción diferida para un camino de escritura que no existe. Se agrega si aparece otro. |
| Suspensión | El local está activo o suspendido; lo cambia el owner por consola cuando ve que el abono no entró. Suspendido: la tienda figura "no disponible" sin decir por qué; el admin entra pero solo ve el aviso y no puede modificar nada. Los datos no se tocan. | Cobro automático: el cobro sigue fuera del sistema. Si se suma, solo cambia quién suspende el local. |

## Sección 1: módulos y responsabilidades

El backend suma dos módulos independientes, Identidad y Locales, que la API web y la consola del owner usan por igual.

- **Identidad** no importa nada de Locales: cuando da de alta un admin, convierte el slug en `LocalId` a través de un puerto (`LocalesDeLaPlataforma`). Que el local exista lo garantiza la clave foránea de `membresias`.
- **El reloj es un puerto**, así horarios, jornadas y vencimientos se prueban con una hora fija.
- **La raíz de composición** (`minutas/composicion.py`) arma los adaptadores (`Servicios`) y los casos de uso listos para usar (`CasosDeUso`); la API y la consola solo ejecutan `casos.<caso>.ejecutar(...)`.
- **Dos tipos de unidad de trabajo,** con protocolos propios de cada contexto: ninguno importa la unidad de otro.
  - **Del local** (fija `app.local_id`): en Locales, el agregado `Local` completo (fila de `locales` y sus franjas), y después la carta y los pedidos. En Identidad, la del alta de admin: usuario y membresía en una sola transacción.
  - **De plataforma** (sin local fijado): en Locales, la resolución del slug; en Identidad, usuarios, sesiones y la lectura de membresías.
- **La consola del owner tiene ocho comandos:** alta de local, alta de admin, cambio de slug, cambio de zona horaria, revocar sesiones, purgar sesiones vencidas, suspender local y reactivar local (argumentos en las Secciones 4 de la 1a y de la 1b). Todo comando que toca un local fija ese local; en el alta, el id se genera en el dominio y se fija antes del `INSERT`. Cada comando queda registrado en el log.

## Sección 2: el dominio de Locales

Todo el comportamiento del local vive en el agregado `Local`, que recibe la hora actual como dato.

### Datos del local

| Campo | Regla |
| --- | --- |
| Nombre | 1 a 80 caracteres |
| Descripción | Hasta 500 caracteres, opcional |
| Dirección | Opcional |
| WhatsApp | Se acepta como lo escribe una persona (`0351 15 123-4567`, `+54 9 351…`); se interpreta con `phonenumbers` (región AR), tiene que ser celular y se guarda en formato WhatsApp (`5493511234567`). Al cargarlo de la base solo se valida ese formato, así un cambio en la tabla de numeración no deja un local sin poder abrirse |
| Color | `#RRGGBB` |
| Modalidades | Delivery, retiro o ambas; nunca ninguna |
| Zona horaria | IANA; por defecto `America/Argentina/Buenos_Aires`; solo por consola, rige desde la próxima jornada |
| Hora de corte | Por defecto 06:00 |
| Logo y portada | Opcionales; se guarda el nombre del archivo |
| Estado | Activo o suspendido; solo lo cambia el owner por consola |
| Versión | Número para el bloqueo optimista. No es parte del agregado: el repositorio recuerda la versión que leyó en la unidad de trabajo y la incrementa al guardar |

### Horarios

Tres objetos de valor:

- **`MomentoDeLaSemana`** (día y hora, sin fecha). Por dentro se cuenta en minutos desde el lunes 00:00 (0 a 10079), con aritmética circular: el domingo a la noche sigue con el lunes a la mañana. Se construye desde un `datetime` ya pasado a la zona del local.
- **`FranjaHoraria`** (día, apertura, cierre, con precisión de minutos).
  - Se valida al construirse: apertura igual a cierre se rechaza por ambigua. Si el cierre es menor que la apertura, la franja cruza la medianoche.
  - Incluye la apertura y excluye el cierre: de 20:00 a 00:30 está abierta a las 20:00 y cerrada a las 00:30.
  - `contiene(momento)`: el momento cae dentro de la franja.
  - `se_superpone_con(otra)`: una contiene el inicio de la otra. Cubre medianoche y el paso de domingo a lunes sin casos especiales.
  - `corta(momento)`: el momento cae estrictamente adentro. Empezar o terminar justo ahí está permitido.
- **`Horario`** (la semana de franjas).
  - Se valida al construirse: ninguna franja se superpone con otra.
  - `asegurar_respeta_corte(hora_de_corte)`: ninguna franja corta ninguna de las siete horas de corte de la semana. Así una jornada nunca se mete en la siguiente, crucen o no la medianoche.
  - Una semana sin franjas es válida: el local está siempre cerrado hasta que cargue horarios.

### Jornada, hora de corte y zona horaria

La jornada es el "día de trabajo" del local y termina en la hora de corte, no a la medianoche:

> jornada = fecha de (ahora en la hora del local − hora de corte)

Con corte a las 06:00, el sábado a las 02:00 sigue siendo la jornada del viernes; el sábado a las 06:00 empieza la del sábado. La misma regla numera los pedidos en la etapa 3.

Lo que define la jornada es el par **reglas de jornada** = (zona horaria, hora de corte), un objeto de valor `ReglasDeJornada(zona, corte)`. Cambiar la zona o el corte tiene el mismo problema (la jornada podría retroceder), así que los dos cambian por el mismo mecanismo. Hay dos variantes, con los métodos `jornada_de(ahora)` y `zona_en(ahora)`:

- **`JornadaFija(reglas)`:** calcula la jornada con la fórmula de arriba y la zona de sus reglas.
- **`JornadaConCambioPendiente(vigentes, pendientes, desde_jornada)`:** `desde_jornada` es la jornada en la que empiezan a regir las reglas nuevas, siempre la jornada actual + 1.
  - Antes del instante en que empieza `desde_jornada` según las reglas vigentes, calcula con las vigentes.
  - Desde ese instante, calcula con las pendientes, sin bajar nunca de `desde_jornada`. `zona_en(ahora)` devuelve la zona que rige en ese instante: las franjas pasan a la zona nueva en el mismo momento que la jornada.

Cambiar el corte (`cambiar_hora_de_corte`) o la zona (`cambiar_zona_horaria`) desde una `JornadaFija` crea una `JornadaConCambioPendiente`. Las reglas:

- La jornada de transición puede durar más o menos de 24 h.
- Un segundo cambio el mismo día reemplaza al pendiente, combinado con él: cambiar el corte y después la zona deja pendientes los dos. No se acumulan transiciones.
- No hace falta ningún proceso: cuando el cambio ya rige, la próxima modificación del local lo convierte en `JornadaFija(pendientes)`.
- Mientras haya un pendiente, las franjas se validan contra los dos cortes. El `Local` valida las franjas tanto al reemplazarlas como al cambiar el corte.
- El panel muestra desde cuándo rigen las reglas nuevas.

Ejemplo: un local en Buenos Aires (UTC−3) con corte 06:00 pasa a `America/Santiago` (UTC−4 en invierno) un sábado a las 06:30 de Buenos Aires. Si rigiera al instante, en Santiago serían las 05:30 y la jornada volvería al viernes. Con el cambio pendiente, el sábado sigue en Buenos Aires; el domingo empieza a las 06:00 de Buenos Aires (05:00 en Santiago) y dura 25 h, hasta las 06:00 de Santiago del lunes.

### Cierre manual

Tres variantes con el mismo método `permite_abrir(jornada)`:

| Clase | `permite_abrir(jornada)` | Se obtiene con |
| --- | --- | --- |
| `SinCierre` | `True` | "Reabrir", o el alta del local |
| `CierrePorJornada(j)` | `jornada != j` | "Cerrar por hoy", que guarda la jornada actual |
| `CierreHastaNuevoAviso` | `False` | "Cerrar hasta nuevo aviso" |

- **"Cerrar por hoy"** vale mientras la jornada actual sea la guardada. Cuando empieza la siguiente, deja de valer solo; no hace falta ningún proceso que lo limpie. Apretado a las 05:30 con corte a las 06:00, cierra la jornada que termina a las 06:00.
- **"Cerrar hasta nuevo aviso"** vale hasta que alguien toque "reabrir".
- **"Reabrir"** reemplaza cualquiera de los dos por `SinCierre`.
- Un cambio de hora de corte no acorta ni alarga un cierre ya hecho, porque rige recién desde la próxima jornada.
- Un cambio de zona horaria tampoco lo afecta, por la misma razón: rige desde la próxima jornada.

### Suspensión

El estado tiene dos variantes:

| Clase | `permite_abrir()` | `asegurar_modificable()` |
| --- | --- | --- |
| `Activo` | `True` | No hace nada |
| `Suspendido` | `False` | Lanza `LocalSuspendido` (403) |

Todo comando del panel sobre el `Local` empieza llamando a `self._estado.asegurar_modificable()`; así la regla de suspensión vive en un solo lugar y sin `if`. Los comandos de la consola (suspender, reactivar, cambiar slug, cambiar zona horaria) no la llaman.

- Un local suspendido está cerrado siempre, sin importar horarios ni cierre manual.
- La tienda pública responde solo que no está disponible y rechaza pedidos, sin mostrar el motivo.
- El admin puede iniciar sesión y ver el aviso; cualquier cambio en el panel se rechaza.
- Suspender y reactivar no borra ni modifica ningún dato del local.

### Cómo se decide "abierto ahora"

El `Local` no pregunta nada: cada parte contesta la suya y el resultado es la conjunción de las tres respuestas.

```python
class Local:
    def esta_abierto(self, ahora: datetime) -> bool:
        jornada = self._jornada.jornada_de(ahora)
        momento = MomentoDeLaSemana.desde_instante(ahora, self._jornada.zona_en(ahora))
        return (
            self._estado.permite_abrir()
            and self._cierre_manual.permite_abrir(jornada)
            and self._horario.contiene(momento)
        )
```

1. El estado: un local suspendido no abre.
2. El cierre manual: no abre si hay un cierre vigente para esta jornada.
3. El horario: abre si alguna franja contiene el momento actual, pasado a la zona del local.

### Próxima apertura

`Local.proxima_apertura(ahora) -> datetime | None` (instante UTC):

- `None` si está abierto ahora, suspendido, cerrado hasta nuevo aviso o sin franjas.
- Si no, recorre los inicios de franja de los próximos 7 días en orden, en la zona que rija en cada instante, y devuelve el primero en el que el local abriría: con un "cerrar por hoy", saltea los inicios que caen en la jornada cerrada.
- La responde cada parte, como `esta_abierto`: el estado y el cierre deciden si una apertura cuenta y el horario dice cuándo empiezan las franjas.

### Condicionales en el dominio

El dominio no tiene ningún `if` que elija comportamiento: las variantes son clases que responden (estado, cierre manual, hora de corte, y en Identidad el usuario vinculado o sin vincular). Quedan permitidos la validación al construir objetos de valor, las guard clauses `asegurar_*` y las expresiones booleanas. El traductor de infraestructura elige la clase a partir de la columna guardada con una tabla de despacho. Regla completa en `docs/plans/00-conventions.md`.

## Sección 3: persistencia, identidad y sesiones

### Tablas

**`locales`** (RLS por operación):

| Columna | Tipo | Nota |
| --- | --- | --- |
| `id` | `uuid` PK | UUIDv7 generado en el dominio |
| `slug` | `text` UNIQUE | |
| `nombre`, `descripcion`, `direccion`, `whatsapp`, `color` | `text` | |
| `ofrece_delivery`, `ofrece_retiro` | `boolean` | `CHECK (ofrece_delivery OR ofrece_retiro)` |
| `zona_horaria` | `text` | Vigente |
| `hora_de_corte` | `time` | Vigente |
| `zona_horaria_pendiente`, `hora_de_corte_pendiente`, `reglas_desde_jornada` | `text`, `time`, `date` | Nulos juntos o no nulos juntos |
| `cierre_manual` | `text NULL` | `por_jornada` o `hasta_nuevo_aviso` |
| `cierre_manual_jornada` | `date NULL` | No nulo solo si el cierre es `por_jornada` |
| `logo`, `portada` | `text NULL` | Nombre de la imagen |
| `estado` | `text` | `activo` o `suspendido` |
| `version` | `integer` | Bloqueo optimista |
| `creado_en`, `actualizado_en` | `timestamptz` | UTC |

**`franjas_horarias`** (RLS completo): `id`, `local_id`, `dia` (0 a 6), `apertura`, `cierre` (`time`). Reemplazar el horario borra y vuelve a insertar las franjas del local en la misma transacción que actualiza `locales`. La no superposición la garantiza el dominio; la base no la controla (ver Decisiones tomadas).

**Guardar el `Local`** actualiza `locales` con `WHERE id = :id AND version = :version_leida` y suma uno a la versión. Si no actualizó exactamente una fila, lanza `LocalModificadoEnParalelo` (409) y no toca las franjas.

**Versión esperada (1b):** la versión sigue fuera del agregado. Es un objeto de valor de la aplicación de Locales, `VersionDelLocal` (entero ≥ 0).
- `obtener(esperada: VersionDelLocal | None = None)`: si recibe una versión y la fila tiene otra, lanza `LocalModificadoEnParalelo` sin cargar las franjas. El `UPDATE` sigue comparando contra la versión leída, así que también cubre una edición que se cruce después de la lectura.
- Los casos de uso del panel que escriben reciben `esperada` y devuelven la versión nueva (el repositorio la expone después de `guardar`), para que la respuesta lleve el `ETag` actualizado y el front pueda seguir editando sin volver a pedir el local.
- Los comandos de la consola no mandan versión: el owner actúa sobre lo último que hay.

**`usuarios`** (plataforma, sin RLS): `id`, `email` (en minúsculas), `google_sub` UNIQUE NULL, `creado_en`. El email es único solo entre los usuarios pendientes (sin `sub`): es lo que identifica a alguien hasta su primer login. Después manda el `sub`, y el email queda como un dato para mostrar que puede repetirse entre usuarios vinculados (por ejemplo, un email viejo que nadie actualizó). Ningún flujo busca usuarios vinculados por email.

```sql
-- No sirve UNIQUE (google_sub, email): el sub ya es único solo, y con sub NULL Postgres acepta emails repetidos.
CREATE UNIQUE INDEX uq_usuarios_email_pendiente ON usuarios (email) WHERE google_sub IS NULL;
```

**`membresias`** (RLS por operación, como `locales`): `usuario_id` UNIQUE, `local_id` (FK a `locales`), `rol` (hoy solo `admin`), `creada_en`. Un usuario tiene un solo local: el `UNIQUE` se quita cuando exista "elegir local". La FK ignora el RLS, así que garantiza que el local exista.

```sql
-- membresias: lectura abierta (resolver el local de la sesión), escritura solo con ese local fijado, sin DELETE
CREATE POLICY lectura_abierta    ON membresias FOR SELECT USING (true);
CREATE POLICY alta_en_el_local   ON membresias FOR INSERT
  WITH CHECK (local_id = current_setting('app.local_id')::uuid);
CREATE POLICY cambio_en_el_local ON membresias FOR UPDATE
  USING (local_id = current_setting('app.local_id')::uuid)
  WITH CHECK (local_id = current_setting('app.local_id')::uuid);
```

**`sesiones`** (plataforma, sin RLS): `id`, `usuario_id` (FK a `usuarios`, con índice), `hash_del_token` (SHA-256, UNIQUE), `creada_en`, `ultimo_uso_en`, `expira_en` (el tope absoluto: `creada_en` + 30 días; los 7 días sin uso se calculan desde `ultimo_uso_en`), `ip` (`inet`), `user_agent` (truncado a 512 caracteres).

### Políticas de RLS

```sql
-- locales: lectura abierta (resolver el slug), escritura solo con ese local fijado
CREATE POLICY lectura_publica  ON locales FOR SELECT USING (true);
CREATE POLICY alta_propia      ON locales FOR INSERT
  WITH CHECK (id = current_setting('app.local_id')::uuid);
CREATE POLICY escritura_propia ON locales FOR UPDATE
  USING (id = current_setting('app.local_id')::uuid)
  WITH CHECK (id = current_setting('app.local_id')::uuid);

-- franjas_horarias: la política estándar de la etapa 0 (lectura y escritura aisladas)
```

Sobre `locales` no se crea política de `DELETE`: con RLS forzado, sin política no se puede borrar ninguna fila.

### Flujos de acceso

- **Tienda pública:** con la unidad de plataforma se resuelve el slug y se obtiene el `local_id`; después, con la unidad del local, se carga el agregado `Local`. Las dos son de solo lectura.
- **Panel:** el `local_id` sale de la membresía del usuario de la sesión, nunca de un parámetro del cliente. Lo resuelve un solo caso de uso de Identidad, `ObtenerSesionVigente.ejecutar(token, ahora) -> SesionDelPanel(usuario_id, local_id, rol)`, en una sola transacción de plataforma:
  1. busca la sesión por el hash del token y verifica que esté vigente con el `ahora` de la solicitud (sin sesión, vencida o revocada: `401 sesion_requerida`);
  2. lee la membresía del usuario (sin membresía: `403 usuario_no_habilitado`, el mismo error del login);
  3. chequea el rol (`rol.asegurar_puede_administrar()`): Locales no conoce roles.

  En la API, una dependencia lo ejecuta y entrega el `LocalId`; se aplica una sola vez a todo el router `/api/v1/panel` (`APIRouter(dependencies=...)`), así ninguna ruta del panel puede olvidarla. Las rutas pasan ese `LocalId` a los casos de uso de la 1a, que no cambian.
- **Alta de admin:** `alta-admin --slug --email` resuelve el slug a `LocalId` con un puerto de Identidad (`LocalesDeLaPlataforma`), cuyo adaptador vive en `composicion.py` (único lugar que importa los dos contextos) y usa el directorio de Locales. Después, en la unidad del alta de admin (con ese local fijado), crea el usuario y su membresía en la misma transacción: o quedan los dos, o ninguno. Si ya hay un usuario pendiente con ese email, el índice `uq_usuarios_email_pendiente` lo rechaza y el repositorio lo traduce a `AdminYaInvitado` (409), como hace `SlugEnUso` con `viola_restriccion`. Un email que ya tiene un usuario vinculado sí se puede invitar: es el caso de una dirección que la empresa reasignó a otra persona.
- **Consola:** fija el local sobre el que opera.

### Login con Google

1. **Antes del botón, el `nonce`:** el panel llama a `POST /api/v1/auth/nonce`. El backend genera un secreto al azar (`GeneradorDeTokens`), lo devuelve en la cookie `__Host-nonce_de_login` (`HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=900`) y responde con su SHA-256, que es el `nonce`. El panel se lo pasa al botón (`google.accounts.id.initialize({ nonce })`) y Google lo incluye en el ID token que firma.
2. El panel envía el ID token a `POST /api/v1/auth/google`. La cookie del nonce viaja sola.
3. **El puerto `VerificadorDeIdentidad`** recibe el token y el `nonce` esperado (el SHA-256 de la cookie), y devuelve una `IdentidadVerificada(sub, email)` o lanza `TokenInvalido`. El adaptador usa `google-auth`:
   - verifica firma, audiencia (`MINUTAS_GOOGLE_CLIENT_ID`), emisor y vencimiento; `email_verified` no lo chequea la librería, así que el adaptador lo exige a mano;
   - compara el `nonce` del token con el esperado (en tiempo constante); sin cookie, o con otro valor, es `TokenInvalido`;
   - corre en un hilo aparte para no bloquear el loop, con tolerancia de unos segundos de desfase de reloj. El caché de las claves públicas de Google no viene activado: el adaptador usa un transporte con caché (por ejemplo `CacheControl` sobre `requests`) para no pedirlas en cada login;
   - **ningún error de `google-auth` sale como 500:** un token malformado, vencido o con firma inválida es `TokenInvalido` (401); si no se pueden obtener las claves de Google (red caída, timeout), es `ServicioDeGoogleNoDisponible` (503), para que el front muestre "probá en un rato" y no "tu cuenta no sirve".
4. **El repositorio busca primero por `sub`** (`obtener_por_identidad`): si no lo encuentra, busca por email **solo entre los pendientes**. El `sub` es el identificador permanente de la cuenta de Google; el email puede cambiar (renombre en Workspace, cuentas con email que no es de Gmail) o pasar a otra persona (una dirección reasignada), así que nunca identifica a un usuario ya vinculado.
5. **El usuario se resuelve en el dominio,** con dos variantes que responden a `ingresar_con(identidad)`: `UsuarioSinVincular`, que pasa a `UsuarioVinculado` guardando el `sub` y el email, y `UsuarioVinculado`, que actualiza el email si cambió en Google:

| Situación | Resultado |
| --- | --- |
| Se encuentra por `sub` | Entra; si el email cambió en Google, se actualiza (no choca con nadie: el email solo es único entre pendientes) |
| No hay `sub`, pero hay un usuario pendiente con ese email | Se guarda el `sub`: la cuenta queda vinculada |
| No hay coincidencia (incluye un email que solo coincide con un usuario vinculado a otro `sub`) | `usuario_no_habilitado` (403) |

   Si el email nuevo de un usuario vinculado coincide con un usuario pendiente, ese pendiente queda huérfano: nadie puede reclamarlo, porque esa dirección ahora es de la cuenta que entra por su `sub`. No se borra solo; el owner lo puede dar de baja.

6. Se crea la sesión y se devuelve la cookie. La respuesta del login, salga bien o mal, borra la cookie del nonce: cada nonce sirve para un solo intento.

**Qué cubre el `nonce`:** un ID token vale alrededor de una hora, y la firma de Google no impide que lo use otro. Con el nonce, el token solo sirve en el navegador que tiene la cookie que le dio origen: uno robado (por una extensión, un log del front, un error que lo exponga) no se puede reusar desde otro lado. También impide que otro sitio loguee al navegador con una cuenta ajena, porque el token del atacante no coincide con la cookie de la víctima. No hace falta tabla ni clave de firma: otro sitio no puede plantar una cookie `__Host-`, y en la cookie va el secreto, no el nonce. Si el panel queda abierto más de 15 minutos, el login falla con `401 token_invalido` y el front pide un nonce nuevo y reintenta.

Un local suspendido no impide el login: la suspensión se chequea al escribir. La sesión es del usuario, no del local, así que si algún día un usuario tiene más de un local, alcanza con sumar un "elegir local".

### Sesión y cookie

```
Set-Cookie: __Host-sesion=<token>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000
```

- **El token:** lo genera un puerto `GeneradorDeTokens` (el adaptador usa `secrets.token_urlsafe(32)`, 256 bits; los tests inyectan uno fijo). En la base se guarda solo su SHA-256.
- **Vencimiento:** 7 días sin uso y 30 días como tope absoluto. Los plazos viven en un objeto de valor `PoliticaDeSesiones`, que arma `composicion.py` desde la configuración: el dominio no lee variables de entorno. El `Max-Age` de la cookie es el tope; los 7 días sin uso los controla el servidor.
- **La entidad `Sesion`** decide su vigencia: `Sesion.iniciar(usuario_id, token, ahora, politica)`, `asegurar_vigente(ahora)` (lanza `SesionRequerida` si pasó el tope o los días sin uso) y `registrar_uso(ahora)`.
- **El último uso** se actualiza como mucho una vez por hora, con una sentencia que no se pisa entre requests simultáneas: `UPDATE sesiones SET ultimo_uso_en = :ahora WHERE id = :id AND ultimo_uso_en < :ahora - interval '1 hour'`.
- **Casos de uso separados,** sin un servicio que lo haga todo: `IniciarSesionConGoogle` (login), `ObtenerSesionVigente` (cada request del panel), `CerrarSesion` (logout), `RevocarSesiones` (consola, todas las de un usuario) y `PurgarSesionesVencidas` (consola).
- **Logout:** borra la fila y devuelve la cookie con `Max-Age=0`. Sin sesión, o con una ya vencida, responde igual `204`: cerrar sesión es idempotente.
- **Sesión vencida o revocada:** `401 sesion_requerida`, y la respuesta también borra la cookie (`Max-Age=0`), para que el navegador no la siga mandando.
- **Purga:** las sesiones vencidas se rechazan al validar, y el comando `purgar-sesiones` borra las que ya pasaron su vencimiento (se programa con cron en el servidor).
- **Logs:** nunca se registran la cookie, el token ni su hash; el middleware de solicitud no vuelca cabeceras.
- **CSRF:** un middleware exige que toda request `POST`, `PUT`, `PATCH` o `DELETE` traiga una cabecera `Origin` que esté en `MINUTAS_ORIGENES_PERMITIDOS`; si no, responde `403 origen_no_permitido`. Ningún `GET` modifica datos.
  - `Origin` ausente o `null` se rechaza;
  - la comparación es exacta contra cada origen permitido (esquema, host y puerto), sin prefijos ni comodines;
  - cubre también `POST /auth/google`, para que otro sitio no pueda loguear al navegador con una cuenta ajena;
  - se registra dentro del middleware de solicitud, así el 403 sale en `problem+json` con su `request_id`.

### Despliegue detrás del proxy

```
minutas.app/api/...   → servidores de la API
minutas.app/panel/... → front del panel
minutas.app/{slug}    → front de la tienda
```

- La app define sus rutas con `/api/v1`; el proxy no recorta el prefijo. `/salud` queda fuera de `/api`, para el balanceador.
- **IP real del cliente:** uvicorn corre con `--proxy-headers` y `--forwarded-allow-ips` apuntando solo al proxy. Lo necesita el límite de pedidos por IP de la etapa 3.
- **El proxy tiene que soportar SSE** (etapa 4): en nginx, `proxy_buffering off`. El keep-alive de 20 s alcanza para los tiempos de espera de CloudFront y del balanceador de AWS.
- **Desarrollo local:** el servidor de desarrollo del front hace de proxy de `/api` a `localhost:8000`.

### Imágenes

- **Subida:** `POST /api/v1/panel/local/logo` y `/portada`, en multipart. El límite de 2 MB se controla mientras se recibe el archivo, no al final, y recién después de validar la sesión:
  - la ruta **no declara `UploadFile` ni `Form`**: FastAPI lee y guarda el cuerpo de un formulario antes de resolver las dependencias, así que la sesión no lo cortaría a tiempo;
  - la ruta depende de la sesión del panel y lee `request.stream()` con un `MultipartParser` de `python-multipart`, acumulando en memoria con un contador; al pasar los 2 MB corta con `422 imagen_demasiado_grande`;
  - un `Content-Length` mayor al límite se rechaza antes de leer;
  - el proxy limita el cuerpo también (`client_max_body_size`), como segunda defensa.
- **Primero la suspensión, después Pillow:** `SubirImagenDelLocal` abre una unidad de solo lectura, carga el local y llama a `asegurar_modificable()` antes de procesar. Un local suspendido recibe `403 local_suspendido` sin gastar CPU en la imagen. La unidad de escritura lo vuelve a chequear al guardar, por si lo suspendieron mientras se procesaba. (Cambio sobre el código de la 1a, que hoy procesa antes de chequear.)
- **Procesamiento con Pillow, en un hilo aparte:**
  1. Abrir la imagen, lo que valida que sea un JPEG, PNG o WebP real.
  2. Tope de píxeles antes de decodificar, contra las bombas de descompresión.
  3. Corregir la orientación según el EXIF.
  4. Achicar: logo a 512×512 como máximo, portada a 1600 px de ancho.
  5. Re-codificar a WebP, lo que descarta los metadatos.
- **Puerto:** `AlmacenDeImagenes.guardar(contenido) -> NombreDeImagen` y `obtener_url_publica(nombre) -> str`. La API devuelve siempre la URL completa; el front no arma rutas.
- **Adaptador de disco:**
  - nombre UUIDv7 con extensión `.webp`, en un volumen de Docker (`imagenes`);
  - escritura atómica: archivo temporal y después renombrado;
  - servidas por `GET /api/v1/imagenes/{nombre}` con `Cache-Control: public, max-age=31536000, immutable`.
- Cada subida genera un nombre nuevo. Las imágenes reemplazadas no se borran, y un archivo huérfano por una transacción fallida es aceptable.
- El volumen entra en los backups junto con la base.
- Dependencias nuevas: `pillow`, `python-multipart`.

## Sección 4 (1a): entradas, errores y pruebas

### HTTP

Todo bajo `/api/v1`, con errores en `problem+json` como en la etapa 0.

| Ruta | Respuesta |
| --- | --- |
| `GET /tiendas/{slug}` | `200`: `slug`, `nombre`, `descripcion`, `direccion`, `whatsapp`, `color`, `modalidades`, `zona_horaria`, `horarios` (franjas en hora local), `logo_url`, `portada_url`, `abierto_ahora`, `proxima_apertura` (UTC o `null`) y `disponible: true`. Suspendido: `200 {slug, disponible: false}`. Inexistente, mal formado o reservado: `404 local_no_encontrado` |
| `GET /imagenes/{nombre}` | El archivo WebP con `Cache-Control: public, max-age=31536000, immutable`. El nombre se valida (`<uuid>.webp`) antes de tocar el disco |

La tienda: la unidad de plataforma resuelve el slug a un `local_id` y la unidad del local carga el `Local` con sus franjas; las dos son de solo lectura. `ObtenerTienda` devuelve una vista de lectura (`TiendaDisponible` con todo calculado, o `TiendaNoDisponible`) que la API solo traduce. La hora se lee del `Reloj` una vez por solicitud y los casos de uso la reciben como `ahora`.

### Consola de la 1a

| Comando | Argumentos |
| --- | --- |
| `alta-local` | `--slug --nombre --whatsapp [--modalidades delivery,retiro]` |
| `cambiar-slug` | `--slug --nuevo` |
| `cambiar-zona-horaria` | `--slug --zona` |
| `suspender-local` | `--slug` |
| `reactivar-local` | `--slug` |

`alta-admin` y `revocar-sesiones` entran en la 1b. Cada comando resuelve el local por slug y lo fija antes de escribir (en el alta, el id se genera en el dominio y se fija antes del `INSERT`), queda registrado en el log y sale con 0, con 1 ante un error de dominio (mensaje por `stderr`) o con 2 ante un uso incorrecto.

### Casos de uso de la 1a

Del owner: `DarDeAltaLocal`, `CambiarSlug`, `CambiarZonaHoraria`, `SuspenderLocal`, `ReactivarLocal`. Públicos: `ObtenerTienda`. Del admin, sin entrada HTTP hasta la 1b: `ActualizarDatosDelLocal`, `CambiarHoraDeCorte`, `ReemplazarHorario`, `CerrarManualmente`, `Reabrir`, `SubirImagenDelLocal`, `ObtenerLocalDelPanel`.

### Pruebas de la 1a

- **Dominio:** `MomentoDeLaSemana` (vuelta del domingo al lunes); `FranjaHoraria` (`contiene`, `se_superpone_con`, `corta` y sus bordes); `Horario` y el respeto de la hora de corte; la jornada con reglas fijas, con cambio pendiente de corte y de zona (Buenos Aires a Santiago), que nunca retrocede y donde un segundo cambio reemplaza al pendiente; las variantes de cierre y de estado; `esta_abierto` y `proxima_apertura` con una tabla de casos; el WhatsApp con varias formas de escribirlo y un fijo que se rechaza; el procesamiento de imágenes (formato falso, bomba de descompresión, orientación EXIF, tamaño máximo, salida WebP sin metadatos).
- **Casos de uso:** con dobles en memoria que reproducen el bloqueo optimista y un reloj fijo.
- **Integración** (PostgreSQL real): las políticas de `locales` (se lee sin local fijado, no se escribe sin local ni con el de otro, no se borra); el RLS de `franjas_horarias`; el repositorio guarda y lee el agregado completo con sus franjas; el bloqueo optimista (una suspensión durante otra edición no se pierde); la migración y `alembic check`; y una prueba de punta a punta: alta por consola, horarios cargados por caso de uso y tienda abierta por HTTP.
- **Consola:** los cinco comandos y sus errores.

### Pendientes de la etapa 0 que entran en la 1a

`SecretStr` para las URLs de conexión, logs de uvicorn en JSON, `cast` en lugar de los `# type: ignore` de los tests, un job de CI que levante Compose y `--proxy-headers` en el arranque de uvicorn.

## Sección 4 (1b): entradas, errores y pruebas

Todos los cuerpos siguen la convención del spec general (sin sobre, `snake_case`, instantes en UTC con `Z`, horas como `"HH:MM"`, enumerados como texto, `null` explícito).

### Auth

| Ruta | Request | Respuesta |
| --- | --- | --- |
| `POST /auth/nonce` | sin cuerpo | `200 {"nonce": "<sha-256 en hex>"}` y la cookie `__Host-nonce_de_login` |
| `POST /auth/google` | `{"credencial": "<id token>"}` | `200`, el mismo cuerpo que `/auth/me`, la cookie de sesión, y borra la del nonce |
| `GET /auth/me` | — | `200 {"usuario_id": "0193…", "email": "juan@laesquina.com", "rol": "admin"}` |
| `POST /auth/logout` | sin cuerpo | `204` (también sin sesión) |

`/auth/me` no trae datos del local, porque Identidad no conoce Locales: el panel pide `GET /panel/local` a continuación y de ahí saca el nombre y el slug.

### Panel

**La vista** (`GET /panel/local`, y la respuesta de toda escritura del panel), siempre con `ETag`:

```json
{
  "estado": "activo",
  "slug": "la-esquina",
  "nombre": "La Esquina",
  "descripcion": "Pizzas a la piedra",
  "direccion": null,
  "whatsapp": "5491155551234",
  "color": "#ff6600",
  "modalidades": ["delivery", "retiro"],
  "zona_horaria": "America/Argentina/Buenos_Aires",
  "hora_de_corte": "04:00",
  "cambio_pendiente": {"zona_horaria": "America/Argentina/Buenos_Aires", "hora_de_corte": "05:00", "desde_jornada": "2026-11-17"},
  "horarios": [{"dia": "viernes", "apertura": "19:00", "cierre": "01:30"}],
  "cierre_manual": {"tipo": "por_hoy", "jornada": "2026-11-15"},
  "logo_url": "https://minutas.app/api/v1/imagenes/0193….webp",
  "portada_url": null,
  "abierto_ahora": false,
  "proxima_apertura": "2026-11-16T22:00:00Z"
}
```

- `cambio_pendiente` y `cierre_manual` son `null` cuando no hay; `jornada` es `null` salvo en el cierre `por_hoy`.
- Una franja con `cierre` menor que `apertura` cruza la medianoche, como en el dominio.
- Suspendido: `200 {"estado": "suspendido", "slug": "la-esquina", "nombre": "La Esquina"}`, lo justo para el aviso.

**Escrituras:** todas exigen `If-Match` y responden `200` con la vista completa y el `ETag` nuevo, así el front redibuja con la respuesta y lo calculado (abierto ahora, cambio pendiente) sale siempre del backend. Los casos de uso del panel devuelven la vista y la versión, no el `Local` (cambio sobre el código de la 1a).

| Ruta | Request | Caso de uso |
| --- | --- | --- |
| `PUT /panel/local/datos` | `{"nombre", "descripcion", "direccion", "whatsapp", "color", "modalidades"}`, todos presentes; `descripcion` y `direccion` admiten `null`; `whatsapp` en texto libre (`"11 5555-1234"`), normalizado con `Whatsapp.desde_texto` | `ActualizarDatosDelLocal` |
| `PUT /panel/local/hora-de-corte` | `{"hora_de_corte": "05:00"}` (rige desde la próxima jornada: la respuesta lo muestra en `cambio_pendiente`) | `CambiarHoraDeCorte` |
| `PUT /panel/local/horarios` | `{"franjas": [{"dia": "lunes", "apertura": "19:00", "cierre": "23:30"}]}` (objeto, no array suelto, también en el request) | `ReemplazarHorario` |
| `PUT /panel/local/cierre-manual` | `{"tipo": "por_hoy"}` o `{"tipo": "hasta_nuevo_aviso"}` | `CerrarManualmente` |
| `DELETE /panel/local/cierre-manual` | sin cuerpo (reabre) | `Reabrir` |
| `POST /panel/local/logo`, `/portada` | multipart con un único campo, `archivo` | `SubirImagenDelLocal` |

- **Datos con `PUT` y formulario entero, no `PATCH`:** el caso de uso ya recibe los datos completos y el panel los edita en un solo formulario; un `PATCH` parcial exigiría lógica de fusión y la distinción `null`/ausente por campo, y el `If-Match` ya protege contra pisar cambios ajenos.
- **La hora de corte en su propia ruta:** es otro caso de uso, con su regla de "desde la próxima jornada"; en el mismo cuerpo que los datos, una request ejecutaría dos casos de uso.
- **El cierre manual es un recurso:** `PUT` lo pone y `DELETE` lo saca.

- Todas las rutas cuelgan del router `/api/v1/panel`, que depende de `ObtenerSesionVigente` (ver Flujos de acceso).
- **`ObtenerLocalDelPanel` devuelve una vista, no el agregado:** `PanelDisponible` (todo lo que el panel muestra, ya calculado, y la versión) o `PanelSuspendido` (solo el aviso), igual que `ObtenerTienda`. La API se limita a traducirla. (Cambio sobre el código de la 1a, que hoy devuelve el `Local`.)
- **`ETag` / `If-Match`:**
  - `GET /panel/local` responde con `ETag: "<versión>"` (fuerte; es la versión del local, no un hash del cuerpo).
  - Toda escritura del panel (las de la tabla de arriba) exige `If-Match` con esa versión. Sin la cabecera: `428 version_requerida`. Con otra versión: `409 local_modificado_en_paralelo` (el mismo error que el bloqueo dentro de la transacción, así el front tiene un solo caso: "cambiaron el local, recargá").
  - Toda escritura exitosa responde con el `ETag` nuevo.
  - Una sola versión cubre todo el local: cambiar el logo invalida un formulario de horarios abierto. Es un 409 de más en un caso raro, y se acepta.
  - En las subidas, `If-Match` se valida junto con la sesión, antes de leer el cuerpo.
- **Cookie en los tests:** el cliente de la API usa `https://testserver`, porque `httpx` no guarda una cookie `Secure` sobre HTTP.

### Consola de la 1b

| Comando | Argumentos |
| --- | --- |
| `alta-admin` | `--slug --email` |
| `revocar-sesiones` | `--email` (del usuario vinculado o pendiente; si el email está repetido entre vinculados, pide `--usuario-id`) |
| `purgar-sesiones` | sin argumentos |

Mismas reglas de salida que la consola de la 1a.

### Pruebas de la 1b

- **Unitarias:** `Sesion` (tope absoluto, días sin uso, registro de uso a lo sumo cada hora) con reloj y generador de tokens fijos; `ingresar_con` en sus tres casos; el middleware de `Origin` (ausente, `null`, otro puerto, otro esquema, permitido); el adaptador de Google rechaza un token sin `nonce`, con otro `nonce` o sin cookie.
- **Integración** (PostgreSQL real, con el mismo estándar que la 1a):
  - las políticas de `membresias`: se lee sin local fijado, no se escribe sin local ni con el de otro, no se borra;
  - el alta del admin es atómica: si falla la membresía, no queda el usuario;
  - el índice `uq_usuarios_email_pendiente`: dos pendientes con el mismo email chocan; un vinculado y un pendiente, no;
  - un admin no ve ni modifica nada de otro local, aunque mande otro id;
  - el `UPDATE` del último uso no se pisa con dos requests simultáneas;
  - `obtener` con una versión esperada distinta de la guardada lanza `LocalModificadoEnParalelo`.
- **API:** el login responde el mismo `403 usuario_no_habilitado` para un email desconocido y para uno que solo coincide con un usuario vinculado a otro `sub` (que no se pueda averiguar quién está dado de alta); un error de `google-auth` nunca da 500; una sesión vencida da 401 y borra la cookie; logout sin sesión da 204; una escritura del panel sin `If-Match` da 428 y con una versión vieja da 409 (el caso de la compu y el celular); la respuesta de una escritura trae el `ETag` nuevo; un login sin la cookie del nonce da 401, y la cookie se borra en la respuesta del login aunque falle.

## Errores

| Error | Respuesta |
| --- | --- |
| `slug_invalido`, `slug_reservado`, `whatsapp_invalido`, `zona_horaria_invalida`, `franja_ambigua`, `horarios_superpuestos`, `franja_corta_la_hora_de_corte`, `dato_del_local_invalido` | 422 (categoría `ReglaDeNegocioIncumplida`) |
| `imagen_invalida`, `imagen_demasiado_grande` | 422 |
| `slug_en_uso`, `local_modificado_en_paralelo`, `admin_ya_invitado` | 409 |
| `version_requerida` | 428 |
| `local_no_encontrado`, `imagen_no_encontrada` | 404 |
| `token_invalido`, `sesion_requerida` (además borra la cookie) | 401 |
| `servicio_de_google_no_disponible` | 503 |
| `usuario_no_habilitado`, `local_suspendido`, `origen_no_permitido` | 403 |

Las categorías `NoAutenticado` (401) y `AccesoDenegado` (403) se suman en `compartido/dominio/errores.py`, con su entrada en `ESTADOS_POR_CATEGORIA`, ya en la 1a: `LocalSuspendido` es un `AccesoDenegado`.

## Pendientes

Resueltos el 2026-11-13 (ver Decisiones tomadas): restricción de exclusión (no va), regla del WhatsApp, próxima apertura y Sección 4 de la 1a. Resueltos el 2026-11-14 (revisión del diseño de la 1b): políticas de `membresias`, unidades de trabajo de Identidad, resolución de la sesión del panel, mecanismo del límite de subida y unicidad del email de `usuarios` (único solo entre pendientes; ver Login con Google), reparto de la sesión, `sesiones` y su purga, `Origin`, adaptador de Google, vista del panel, suspensión antes de procesar imágenes, pruebas de la 1b, bloqueo entre solicitudes con `ETag`/`If-Match` obligatorio y cookie `__Host-` también en desarrollo (ver Decisiones tomadas), y `nonce` en el login (entra en la 1b: no se vuelve a tocar auth). Resuelto el 2026-11-15: Sección 4 de la 1b con los cuerpos de auth y del panel.

1. **Plan de implementación** de la 1b. Su primera tarea: que `composicion.py` deje de importar `minutas.api.rutas_publicas` (hoy la raíz de composición depende de la capa HTTP), antes de que la 1b sume routers. Otra tarea temprana: `GET /tiendas/{slug}` devuelve hoy el día de las franjas como número (`DiaDeLaSemana` es un `IntEnum`); pasa a código de texto (`"lunes"`), según la convención de cuerpos del spec general.
