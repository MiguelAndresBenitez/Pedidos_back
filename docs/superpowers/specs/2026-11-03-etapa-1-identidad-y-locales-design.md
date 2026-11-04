# Minutas — Etapa 1 (Identidad y Locales): diseño

2026-11-03 · Miguel

> Reemplaza a la minuta "Etapa 1 (Identidad y Locales): diseño en curso" (PDF). Incorpora la revisión de esa minuta y completa la Sección 3. La Sección 4 (endpoints y pruebas) sigue pendiente.
> Spec general: [`2026-10-07-backend-minutas-design.md`](2026-10-07-backend-minutas-design.md).

## Contexto

Al terminar la etapa 1, un local dado de alta por consola queda con su administrador logueado con Google y configurando la tienda. La etapa se entrega en dos partes:

| Parte | Qué incluye | Queda funcionando |
| --- | --- | --- |
| **1a — Locales** | Agregado `Local` (datos, branding, modalidades, horarios, jornada, hora de corte, cierre manual, suspensión), imágenes, consola del owner para locales, `GET /api/v1/tiendas/{slug}` | Un local dado de alta por consola, con su tienda pública respondiendo si está abierta |
| **1b — Identidad** | Usuarios, membresía (rol admin), login con Google, sesiones y logout, consola para admins y sesiones, panel del local | El admin se loguea y configura su local desde el panel |

La 1a es dominio puro y de bajo riesgo; la 1b suma lo que depende de Google, cookies y despliegue.

## Decisiones tomadas

| Tema | Decisión | Descartado y por qué |
| --- | --- | --- |
| Cierre manual | Dos acciones: "cerrar por hoy" (vale hasta que empieza la jornada siguiente) y "cerrar hasta nuevo aviso" (hasta que alguien reabra). | Solo una de las dos: o se olvidan de reabrir, o no cubre vacaciones. |
| Horarios | Varias franjas por día, pueden cruzar medianoche, sin superponerse. El panel reemplaza la semana entera de una vez. Se guardan en una tabla propia, una fila por franja. | Una franja por día (no sirve a quien corta al mediodía); franjas por modalidad (se puede sumar después); `jsonb` dentro de `locales` (la base no ve el contenido). |
| Hora de corte | Un cambio rige **desde la próxima jornada**: la jornada nunca retrocede. | Cambio inmediato: correr el corte para más tarde hace retroceder la jornada, reabre un "cerrar por hoy" y rompe la numeración de pedidos. |
| Tiempo | Los instantes (sesiones, pedidos, cierres) se guardan en UTC; las franjas y la hora de corte, en hora local, con la zona horaria del local. | Todo en UTC: "abre a las 20:00" se correría sola si el país cambia de huso u horario de verano. |
| Zona horaria | Una por local, por defecto `America/Argentina/Buenos_Aires`; solo la cambia el owner por consola. Hoy se opera solo en Argentina. | Sin campo: habría que migrar al salir del país. Editable en el panel: no hace falta hoy. |
| Logo y portada | Disco, detrás del puerto `AlmacenDeImagenes`, servidas por la API con caché permanente; S3 + CDN entra después como otro adaptador. Se re-codifican a WebP con tamaño máximo. | Guardar el original: puede traer el GPS de la foto y pesar de más. Servirlas desde el proxy: obliga a compartir disco entre servidores. |
| Instancias | Una sola instancia de la API mientras las imágenes estén en disco. Antes de escalar, se pasa a S3. | — |
| Login | Botón de Google en el panel; el backend verifica el ID token con `google-auth`. Solo entra quien el owner dio de alta. El primer login vincula la cuenta de Google (`sub`); los siguientes se buscan por `sub`. | Flujo con redirección y client secret: más código y un secreto que guardar. Identificar solo por email: el email de una cuenta de Google puede cambiar o reasignarse. |
| Sesiones | Cookie `__Host-sesion` `HttpOnly` con token opaco; vencen tras 7 días sin uso y a los 30 días sí o sí. CSRF: `SameSite=Lax` + `Origin` permitido en toda escritura. | — |
| Despliegue | Un solo dominio (`minutas.app`, provisorio) con un proxy que reparte por ruta: `/api/*` al backend, el resto al front. Front y back en servidores distintos. | Subdominios: obliga a configurar CORS y cualquier subdominio cuenta como "mismo sitio". Dominios distintos: la cookie `Lax` no viaja. |
| Slug | Lo fija y lo cambia solo el owner por consola. 3 a 40 caracteres `a-z 0-9 -`, único, sin palabras reservadas (`api`, `panel`, `admin`…). | Que lo cambie el admin: rompería el link publicado en redes sin querer. |
| Aislamiento | Toda escritura exige el local fijado en la transacción, sin excepción. La única lectura sin local fijado es la de `locales`, para resolver el slug. | `locales` sin RLS: un descuido permitiría que un local escriba datos de otro. |
| Suspensión | El local está activo o suspendido; lo cambia el owner por consola cuando ve que el abono no entró. Suspendido: la tienda figura "no disponible" sin decir por qué; el admin entra pero solo ve el aviso y no puede modificar nada. Los datos no se tocan. | Cobro automático: el cobro sigue fuera del sistema. Si se suma, solo cambia quién suspende el local. |

## Sección 1: módulos y responsabilidades

El backend suma dos módulos independientes, Identidad y Locales, que la API web y la consola del owner usan por igual.

- **Identidad** no importa nada de Locales: cuando da de alta un admin, consulta que el local exista a través de un puerto.
- **El reloj es un puerto**, así horarios, jornadas y vencimientos se prueban con una hora fija.
- **Dos unidades de trabajo:**
  - **Del local** (fija `app.local_id`): el agregado `Local` completo (fila de `locales` y sus franjas), y después la carta y los pedidos.
  - **De plataforma** (sin local fijado): usuarios, sesiones y la resolución del slug.
- **La consola del owner tiene seis comandos:** alta de local, alta de admin, cambio de slug, revocar sesiones, suspender local y reactivar local. Todo comando que toca un local fija ese local; en el alta, el id se genera en el dominio y se fija antes del `INSERT`. Cada comando queda registrado en el log.

## Sección 2: el dominio de Locales

Todo el comportamiento del local vive en el agregado `Local`, que recibe la hora actual como dato.

### Datos del local

| Campo | Regla |
| --- | --- |
| Nombre | 1 a 80 caracteres |
| Descripción | Hasta 500 caracteres, opcional |
| Dirección | Opcional |
| WhatsApp | Formato internacional, solo dígitos (ej. `5493511234567`) |
| Color | `#RRGGBB` |
| Modalidades | Delivery, retiro o ambas; nunca ninguna |
| Zona horaria | Por defecto `America/Argentina/Buenos_Aires`; solo por consola |
| Hora de corte | Por defecto 06:00 |
| Logo y portada | Opcionales; se guarda el nombre del archivo |
| Estado | Activo o suspendido; solo lo cambia el owner por consola |

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

### Jornada y hora de corte

La jornada es el "día de trabajo" del local y termina en la hora de corte, no a la medianoche:

> jornada = fecha de (ahora en la hora del local − hora de corte)

Con corte a las 06:00, el sábado a las 02:00 sigue siendo la jornada del viernes; el sábado a las 06:00 empieza la del sábado. La misma regla numera los pedidos en la etapa 3.

**La hora de corte tiene dos variantes**, con el mismo método `jornada_de(ahora, zona_horaria)`:

- **`CorteFijo(hora)`:** calcula la jornada con la fórmula de arriba.
- **`CorteConCambioPendiente(vigente, pendiente, desde_jornada)`:** `desde_jornada` es la jornada en la que empieza a regir el corte nuevo, siempre la jornada actual + 1.
  - Antes del corte vigente que da inicio a `desde_jornada`, calcula con el vigente.
  - Desde ese momento, calcula con el pendiente, sin bajar nunca de `desde_jornada`.

Cambiar el corte desde un `CorteFijo` crea un `CorteConCambioPendiente`. Las reglas:

- La jornada de transición puede durar más o menos de 24 h.
- Un segundo cambio el mismo día reemplaza al pendiente; no se acumulan.
- No hace falta ningún proceso: cuando el cambio ya rige, la próxima modificación del local lo convierte en `CorteFijo(pendiente)`.
- Mientras haya un pendiente, las franjas se validan contra los dos cortes. El `Local` valida las franjas tanto al reemplazarlas como al cambiar el corte.
- El panel muestra desde cuándo rige el corte nuevo.

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
- Un cambio de zona horaria tampoco lo afecta: los instantes están en UTC y las franjas en hora local.

### Suspensión

El estado tiene dos variantes:

| Clase | `permite_abrir()` | `asegurar_modificable()` |
| --- | --- | --- |
| `Activo` | `True` | No hace nada |
| `Suspendido` | `False` | Lanza `LocalSuspendido` (403) |

Todo comando del panel sobre el `Local` empieza llamando a `self._estado.asegurar_modificable()`; así la regla de suspensión vive en un solo lugar y sin `if`. Los comandos de la consola (suspender, reactivar, cambiar slug) no la llaman.

- Un local suspendido está cerrado siempre, sin importar horarios ni cierre manual.
- La tienda pública responde solo que no está disponible y rechaza pedidos, sin mostrar el motivo.
- El admin puede iniciar sesión y ver el aviso; cualquier cambio en el panel se rechaza.
- Suspender y reactivar no borra ni modifica ningún dato del local.

### Cómo se decide "abierto ahora"

El `Local` no pregunta nada: cada parte contesta la suya y el resultado es la conjunción de las tres respuestas.

```python
class Local:
    def esta_abierto(self, ahora: datetime) -> bool:
        jornada = self._hora_de_corte.jornada_de(ahora, self._zona_horaria)
        momento = MomentoDeLaSemana.desde_instante(ahora, self._zona_horaria)
        return (
            self._estado.permite_abrir()
            and self._cierre_manual.permite_abrir(jornada)
            and self._horario.contiene(momento)
        )
```

1. El estado: un local suspendido no abre.
2. El cierre manual: no abre si hay un cierre vigente para esta jornada.
3. El horario: abre si alguna franja contiene el momento actual, pasado a la zona del local.

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
| `zona_horaria` | `text` | |
| `hora_de_corte` | `time` | Vigente |
| `hora_de_corte_pendiente`, `hora_de_corte_desde_jornada` | `time`, `date` | Nulos juntos o no nulos juntos |
| `cierre_manual` | `text NULL` | `por_jornada` o `hasta_nuevo_aviso` |
| `cierre_manual_jornada` | `date NULL` | No nulo solo si el cierre es `por_jornada` |
| `logo`, `portada` | `text NULL` | Nombre de la imagen |
| `estado` | `text` | `activo` o `suspendido` |
| `creado_en`, `actualizado_en` | `timestamptz` | UTC |

**`franjas_horarias`** (RLS completo): `id`, `local_id`, `dia` (0 a 6), `apertura`, `cierre` (`time`). Reemplazar el horario borra y vuelve a insertar las franjas del local en la misma transacción que actualiza `locales`.

**`usuarios`** (plataforma, sin RLS): `id`, `email` UNIQUE (en minúsculas), `google_sub` UNIQUE NULL, `creado_en`.

**`membresias`**: `usuario_id`, `local_id`, `rol` (hoy solo `admin`). Las políticas quedan pendientes (ver abajo).

**`sesiones`** (plataforma, sin RLS): `id`, `usuario_id`, `hash_del_token` (SHA-256), `creada_en`, `ultimo_uso_en`, `expira_en`, `ip`, `user_agent`.

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
- **Panel:** el `local_id` sale de la membresía del usuario de la sesión, nunca de un parámetro del cliente.
- **Consola:** fija el local sobre el que opera.

### Login con Google

1. El panel obtiene un ID token con el botón de Google y lo envía a `POST /api/v1/auth/google`.
2. **El puerto `VerificadorDeIdentidad`** devuelve una `IdentidadVerificada(sub, email)` o lanza `TokenInvalido`. El adaptador usa `google-auth`:
   - verifica firma, audiencia (`MINUTAS_GOOGLE_CLIENT_ID`), emisor, vencimiento y `email_verified`;
   - corre en un hilo aparte para no bloquear el loop, con caché de las claves de Google y tolerancia de unos segundos de desfase de reloj.
3. **El usuario se resuelve en el dominio,** con dos variantes que responden a `asegurar_identidad(identidad)`: `UsuarioSinVincular`, que acepta si el email coincide y pasa a `UsuarioVinculado` guardando el `sub`, y `UsuarioVinculado`, que compara por `sub`:

| Situación | Resultado |
| --- | --- |
| Primer login: hay un usuario con ese email y sin `sub` | Se guarda el `sub`: la cuenta queda vinculada |
| Login siguiente: se encuentra por `sub` | Entra; si el email cambió en Google, se actualiza |
| El email coincide con un usuario que tiene otro `sub` | `usuario_no_habilitado` (403) |
| No hay coincidencia | `usuario_no_habilitado` (403) |

4. Se crea la sesión y se devuelve la cookie.

Un local suspendido no impide el login: la suspensión se chequea al escribir. La sesión es del usuario, no del local, así que si algún día un usuario tiene más de un local, alcanza con sumar un "elegir local".

### Sesión y cookie

```
Set-Cookie: __Host-sesion=<token>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000
```

- **El token:** `secrets.token_urlsafe(32)`, 256 bits. En la base se guarda solo su SHA-256.
- **Vencimiento:** 7 días sin uso y 30 días como tope absoluto, configurables por variables de entorno. El `Max-Age` de la cookie es el tope; los 7 días sin uso los controla el servidor.
- **El último uso** se actualiza como mucho una vez por hora.
- **Logout:** borra la fila y devuelve la cookie con `Max-Age=0`. La consola puede revocar todas las sesiones de un usuario.
- **CSRF:** un middleware exige que toda request `POST`, `PUT`, `PATCH` o `DELETE` traiga una cabecera `Origin` que esté en `MINUTAS_ORIGENES_PERMITIDOS`; si no, responde `403 origen_no_permitido`. Ningún `GET` modifica datos.

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

- **Subida:** `POST /api/v1/panel/local/logo` y `/portada`, en multipart. El límite de 2 MB se controla mientras se recibe el archivo, no al final.
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

## Errores

| Error | Respuesta |
| --- | --- |
| Slug inválido, horarios superpuestos, franja ambigua o que corta la hora de corte, zona horaria o WhatsApp inválidos | 422 `regla_de_negocio_incumplida` (cada uno con su código) |
| `imagen_invalida`, `imagen_demasiado_grande` | 422 |
| Slug en uso | 409 |
| Local no encontrado | 404 |
| `token_invalido`, `sesion_requerida` | 401 |
| `usuario_no_habilitado`, `local_suspendido`, `origen_no_permitido` | 403 |

**Cambio pendiente en el código (decidido, sin implementar):** sumar las categorías `NoAutenticado` (401) y `AccesoDenegado` (403) en `compartido/dominio/errores.py`, con su entrada en `ESTADOS_POR_CATEGORIA`.

## Pendientes

1. **Políticas de `membresias`:** en el login hay que leerla antes de saber el local. Propuesta a confirmar: el mismo esquema que `locales` (lectura abierta, escritura con el local fijado).
2. **Restricción de exclusión en `franjas_horarias`** (rango de minutos de la semana con `EXCLUDE USING gist`), como red extra en la base. Opcional; la regla vive en el dominio.
3. **La regla exacta del WhatsApp:** largo y prefijo `549` para celulares argentinos.
4. **"Abre a las 20:00":** que `GET /tiendas/{slug}` devuelva la próxima apertura.
5. **`nonce` en el login con Google:** fuera del MVP, queda como mejora.
6. **Sección 4:** los endpoints de la etapa con sus cuerpos de request y response, y el plan de pruebas.
7. **Plan de implementación** de 1a y 1b.
