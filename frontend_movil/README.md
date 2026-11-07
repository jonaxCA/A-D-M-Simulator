# App móvil: cómo conectarla a los servicios

La app se entrega en el tercer parcial (D10 de `docs/decisiones.md`) y habla JSON con los
microservicios. Esta guía es lo que necesita para conectarse desde el primer día: dónde están
los servicios, cómo dejar pasar HTTP en desarrollo, con qué cuenta entrar y cómo renovar la
sesión sin cerrarla por accidente. Los contratos de cada servicio están en `docs/contratos/` y
el catálogo en `docs/arquitectura/microservicios.md`.

## El proyecto

Es un proyecto de Android Studio en esta misma carpeta: abre `frontend_movil/` con *File > Open*,
no la raíz del repositorio. Kotlin con Jetpack Compose, un solo módulo `app` y el paquete
`com.estudiante.simuladorepidemico`. Las versiones de todas las librerías están en
`gradle/libs.versions.toml`.

Gradle pide el JDK 25, que es el que trae Android Studio. Desde una consola, apunta `JAVA_HOME`
a la carpeta `jbr` de Android Studio y corre:

```bash
cd frontend_movil
./gradlew assembleDebug testDebugUnitTest
```

Dónde va cada cosa dentro de `app/src/main/java/com/estudiante/simuladorepidemico/`:

| Paquete | Qué lleva |
|---------|-----------|
| (raíz) | `MainActivity` (la única Activity), `EpidemiaApp` y `Contenedor`: las dependencias se arman a mano, sin Hilt |
| `red/` | OkHttp, Retrofit, el directorio de servicios (sección 1), el `Authenticator` que renueva (sección 4) y una interfaz por servicio en `red/api/` |
| `sesion/` | Tokens, cifrados con una llave del Keystore y guardados en DataStore, y el registro del teléfono en `dispositivos` (`Telefono.kt`, sección 6) |
| `ubicacion/` | La lectura del GPS para un caso (`Ubicador`), con Google Play services |
| `local/` | Room (`epidemia.db`): los casos capturados y los catálogos de enfermedades y municipios (sección 5). Después, las fotos por subir. El esquema de cada versión queda en `app/schemas/` |
| `trabajos/` | El `Sincronizador`, que manda los casos en lotes, y `TrabajoSincronizar`, que WorkManager corre cuando hay red. Después, subir fotos y consultar avisos |
| `ui/` | Una carpeta por pantalla con su ViewModel (`login`, `perfil`, `casos`, `fotos`, `vacunas`, `avisos`), más `tema` y `navegacion`. Ya están `login`, `inicio`, `casos` (Capturar caso y Mis casos), `perfil` y `navegacion`, que empieza en el login o en el inicio según haya sesión, regresa al login cuando se pierde y pide el permiso de red local. `ui/Formato.kt` da formato a fechas, roles y los valores de un caso |

`app/src/debug/` lleva lo que solo vale en desarrollo, como el permiso de HTTP sin cifrar
(sección 2).

Las pruebas unitarias (`app/src/test/`) corren en la PC contra un MockWebServer. Las de
`app/src/androidTest/` (el Keystore, las consultas de Room y las pantallas) necesitan un emulador:
`./gradlew connectedDebugAndroidTest`. Dale al emulador 3 GB de RAM o más (Device Manager >
editar > RAM): con 2 GB, Android 17 mata el proceso de la prueba por falta de memoria y Gradle
solo dice "Process crashed".

Antes de probar, levanta el compose en la PC (`docs/INSTALACION.md`):

```bash
python infra/genera_env.py
docker compose -f infra/docker-compose.yml --profile '*' up -d --build --wait
```

## 1. Encontrar los servicios

No hay pasarela (D13): la app le pide a `estado-servicios` la URL de cada uno y lo llama directo.

```
GET http://<host>:5262/api/v1/services
Accept: application/json
```

`<host>` es como la app ve a la PC:

| Dónde corre la app | `<host>` |
|--------------------|----------|
| Emulador de Android | `10.0.2.2` |
| Celular en la misma red Wi-Fi | La IP de la PC en esa red (`ipconfig` en Windows) |

El directorio arma cada URL con ese mismo host, así que no hay que configurar nada: el emulador
recibe `http://10.0.2.2:5221` para `casos` y el celular, la IP de la PC. Si la app entra por
otra dirección, `URL_PUBLICA` en `infra/.env` manda sobre esto.

Todos los servicios responden XML por defecto. La app pide JSON con `Accept: application/json`
(o `?format=json`) y manda sus cuerpos con `Content-Type: application/json`.

Si el celular no llega a la PC, revisa que estén en la misma red y que el firewall de Windows
deje entrar los puertos de los servicios. En una consola de administrador:

```powershell
New-NetFirewallRule -DisplayName "EPIDEMIA servicios" -Direction Inbound -Protocol TCP -LocalPort 5201-5262 -Profile Private -Action Allow
```

### Permiso de red local (Android 17)

Desde Android 17, una app no se conecta a direcciones de la red local (`10.x`, `192.168.x`,
`172.16-31.x`) sin el permiso `ACCESS_LOCAL_NETWORK`, y los servicios están justo ahí: en la PC,
o en `10.0.2.2` desde el emulador. Sin el permiso, la conexión no falla al momento: se queda
esperando hasta que se agota el tiempo, así que parece un problema de red.

La app lo declara en el manifiesto y lo pide al abrirse (`ui/navegacion/PermisoRedLocal.kt`)
antes de mostrar el login. El sistema lo presenta como permiso de dispositivos cercanos. Si se
niega, la pantalla ofrece abrir los Ajustes de la app. En Android 16 o anterior no se pide.

## 2. HTTP sin cifrar en desarrollo

Desde Android 9 la app no puede hacer peticiones `http://` salvo que lo permita su configuración
de seguridad de red. Los servicios corren sin TLS en la PC, así que en desarrollo hay que
permitirlo.

Eso está en el *source set* de debug (`app/src/debug/AndroidManifest.xml` y
`app/src/debug/res/xml/network_security_config.xml`), así que la versión de release sigue sin
permitir HTTP. Como la IP de la PC cambia según la red y no acepta comodines, en debug se
permite HTTP hacia cualquier dirección.

La app empieza por el directorio, que por omisión busca en `http://10.0.2.2:5262/` (el
emulador). Para un celular, agrega a tu `~/.gradle/gradle.properties`, que no está en el
repositorio:

```properties
epidemia.directorio=http://192.168.1.20:5262/
```

Cambia `192.168.1.20` por la IP de tu PC.

## 3. Cuenta de prueba e inicio de sesión

La semilla de demostración trae una cuenta CAPTURISTA, el rol de la app:

| Usuario | Contraseña | Rol |
|---------|------------|-----|
| `karla.trevino` | `Epidemia2026!` | CAPTURISTA |

Con ese rol la app registra su teléfono (`dispositivos`), registra y consulta casos (`casos`),
sube sus fotos (`evidencias`), escanea lotes de vacuna (`vacunas`) y envía y consulta sus
lotes de casos (`sincronizacion`). Es una cuenta de demostración: solo sirve en el entorno local.

El inicio de sesión lleva captcha, que la app muestra y la persona contesta:

1. `GET /api/v1/auth/captcha` (en `auth`) devuelve `captcha_id` y `pregunta` (por ejemplo `3 + 5`).
2. `POST /api/v1/auth/login` con `usuario`, `password`, `captcha_id` y `captcha_respuesta`.
3. La respuesta trae `access_token` (20 minutos, `expires_in`), `refresh_token` y la cuenta.

Cada petición protegida lleva `Authorization: Bearer <access_token>`. Guarda el refresh cifrado
(la app lo hace con una llave del Keystore, en `sesion/`), nunca en texto plano. La sesión dura 8 horas desde el
inicio de sesión y renovarla no la alarga: después hay que volver a entrar. Para salir,
`POST /api/v1/sessions/logout` (en `sesiones`) y borra lo guardado.

Para la pantalla de perfil, `GET /api/v1/users/me` (en `usuarios`) devuelve la cuenta del token:
nombre, usuario, correo, roles y último acceso. Sirve con cualquiera de los cuatro roles. La app
lo muestra en "Mi perfil", con la hora a la que vence la sesión (`sesion_expira` del login).

## 4. Renovar el access: una sola renovación a la vez

`POST /api/v1/sessions/refresh` con `{"refresh_token": "..."}` devuelve un access y un refresh
nuevos, y el refresh usado deja de servir. **Si alguien vuelve a usar un refresh ya usado, el
servidor lo toma como un robo y cierra la sesión completa** (401 `TOKEN_REVOCADO`).

En una app eso pasa sin querer: dos peticiones vencen a la vez, las dos ven 401 y las dos
renuevan con el mismo refresh; la segunda cierra la sesión. Para evitarlo:

- Renueva solo cuando la respuesta sea 401 `TOKEN_EXPIRADO`. Con `TOKEN_INVALIDO` o
  `TOKEN_REVOCADO` la sesión ya no sirve: vuelve a la pantalla de inicio de sesión.
- Una sola renovación a la vez: las peticiones que lleguen mientras otra renueva esperan y
  reintentan con el access nuevo.
- Guarda el par nuevo antes de usarlo, para que un cierre de la app a media renovación no deje
  el refresh viejo guardado.
- La llamada a `/sessions/refresh` no pasa por el mismo interceptor que renueva.

La app lo hace en `red/Renovador.kt`, un `Authenticator` de OkHttp sincronizado, y
`RenovadorTest` lo prueba con cinco peticiones que vencen a la vez. Dos detalles más:

- La renovación es una llamada síncrona (`Call.execute()`), no `suspend`. Si se encolara en el
  despachador de OkHttp mientras las peticiones vencidas lo ocupan, se quedaría esperando.
- Si el 401 llegó con un access que ya no es el guardado (otra petición renovó, o se volvió a
  iniciar sesión), reintenta con el guardado sin renovar ni borrar nada.

## 5. Captura sin conexión y sincronización

- Cada caso lleva un `local_uuid` generado en el celular. `casos` lo usa para no duplicar: el
  mismo `local_uuid` otra vez responde 200 con el caso existente y `duplicado: true`.
- Los casos capturados sin conexión se mandan en lotes a `POST /api/v1/sync/cases` (en
  `sincronizacion`): un `batch_id` (UUID del celular) y de 1 a 100 casos.
- Conserva el `batch_id` hasta que el lote responda 200: reenviar el mismo lote regresa el
  resultado guardado (`repetido: true`) y no crea nada dos veces. Ese resultado se guarda 7 días.
- El lote responde 200 aunque haya casos rechazados: revisa `resultados[]`, que dice por cada
  caso si se creó, era duplicado o se rechazó y por qué. En un rechazado, `codigo` dice qué
  hacer: `DATOS_INVALIDOS`, el caso hay que corregirlo; `CONFLICTO`, el teléfono está revocado
  (sale en todos los casos del lote) y los casos no tienen nada malo: no los marques como
  rechazados, pide volver a iniciar sesión (sección 6) y mándalos en un lote nuevo.
- Un lote que ya respondió 200 no se reenvía: los casos que se corrijan o se vuelvan a mandar
  van en un lote nuevo, con otro `batch_id`. Con el mismo, el servidor regresa el resultado
  guardado aunque el contenido cambie.
- El `device_id` de cada caso (o del lote) es el `id` que regresa `dispositivos` al registrar el
  teléfono (sección 6). Sin `device_id` el caso también se acepta, pero no queda ligado al
  teléfono y llega sin `synced_at`.
- Para el formulario sin conexión, los catálogos son públicos:
  `GET /api/v1/diseases?status=activa&size=100` (en `enfermedades`, paginado) y
  `GET /api/v1/regions` (en `regiones`, los 51 municipios). Son los mismos que acepta `casos`.

### Cómo lo hace la app

- **Capturar caso** guarda el caso en `epidemia.db` (Room, `local/`) con su `local_uuid` y la
  cuenta de la sesión, con las mismas reglas que `casos`: fechas hasta hoy, el inicio de
  síntomas antes del reporte y la edad de 0 a 120. Los catálogos se bajan al llegar al inicio
  con conexión; si el teléfono nunca los tuvo, la captura ofrece descargarlos.
- La ubicación es opcional y de cada caso. "Agregar mi ubicación" pide el permiso en ese momento
  (sirve el preciso o el aproximado) y lee el GPS, que funciona sin red; la pantalla muestra
  las coordenadas y su precisión. Van con seis decimales, como las guarda `cases`
  (`NUMERIC(9,6)`), y al guardar se limpian: el siguiente caso toma la suya
  (`ubicacion/Ubicador.kt`, con Google Play services).
- `TrabajoSincronizar` (WorkManager, `trabajos/`) manda lo pendiente en cuanto hay red, aunque
  la app esté cerrada: después de guardar un caso, al llegar al inicio y con "Enviar ahora" en
  Mis casos. Si falla, WorkManager lo reintenta cada vez más espaciado, con el mismo lote.
- Cada caso es de la cuenta que lo capturó y solo se manda con una sesión suya. El `device_id`
  va en el lote: el de la sesión al momento de enviar. Si el teléfono no quedó registrado al
  iniciar sesión, se registra antes de enviar.
- Un caso enviado se queda en el teléfono como comprobante (enfermedad, municipio, fecha y
  `case_id`); la edad, el sexo, el resultado, la severidad y la ubicación se borran. Un
  rechazado por datos se queda con su motivo hasta que se descarte. Con el teléfono revocado,
  los casos vuelven a pendientes y la app cierra la sesión.
- Cerrar sesión no borra lo pendiente: Mi perfil avisa cuántos casos faltan, y se envían cuando
  esa cuenta vuelva a entrar. Otra cuenta en el mismo teléfono no los ve.
- `epidemia.db` no entra en los respaldos ni pasa a otro teléfono (`res/xml/`): lleva datos de
  salud.

## 6. Registrar el teléfono

El servicio `dispositivos` (puerto 5223) lleva los teléfonos de cada cuenta, para poder
revocar uno perdido sin tocar la cuenta.

1. La app genera un `device_uid` (un UUID) y lo guarda: es el mismo mientras la app siga
   instalada. De 8 a 128 letras, números o `. _ : -`. Un `device_uid` no puede ser de dos
   cuentas, así que la app guarda uno por cuenta: en un teléfono compartido, cada quien tiene su
   registro, en lugar de uno nuevo cada vez que cambia quien entra.
2. Después de cada inicio de sesión, `POST /api/v1/devices` con `{"device_uid": "...",
   "platform": "android", "model": "...", "app_version": "..."}`. La primera vez responde 201;
   las siguientes, 200, y actualiza la versión y la última conexión. La respuesta trae el `id`:
   ese es el `device_id` de los casos.
3. Si responde 409, ese `device_uid` es de otra cuenta o está revocado: genera uno nuevo y vuelve
   a registrarte.

La app lo hace en `sesion/Telefono.kt`, antes de pasar del login al inicio. Con la sesión guarda
el `id` del teléfono y el de la cuenta (`usuario.id` del login), y los dos se borran al cerrarla o
al perderla. La cuenta se necesita sin red: los casos capturados sin conexión son de quien los
capturó y solo se mandan con una sesión suya, porque `reported_by` sale del token.

Si `dispositivos` no responde, la sesión se abre igual, sin `id`, y "Mi perfil" ofrece registrar
el teléfono. En ese reintento la sesión ya estaba abierta, así que un 409 no se resuelve con otro
`device_uid`: quiere decir que revocaron el teléfono, y la app cierra la sesión. Solo quien vuelva
a entrar con su contraseña lo registra de nuevo. "Mi perfil" también muestra el número de
dispositivo, que es el que ADMINISTRADOR revoca si el teléfono se pierde.

Desde que alguien revoca el teléfono (`POST /api/v1/devices/{id}/revoke`, la misma persona o
ADMINISTRADOR), `casos` responde 409 `CONFLICTO` a sus casos, también dentro de un lote, aunque
el token siga vigente. La app debe dejar de capturar y pedir que se vuelva a iniciar sesión. Lo
que ya había sincronizado se queda. `push_token` se puede mandar al registrar, pero todavía no
hay notificaciones push.

## 7. Fotos de los casos

El servicio `evidencias` (puerto 5224) guarda fotos (JPEG, PNG o WebP) y PDF de hasta 20 MB.

- Se suben a `POST /api/v1/cases/{case_id}/attachments` con el archivo **tal cual en el cuerpo**,
  no como formulario: con OkHttp, `file.asRequestBody("image/jpeg".toMediaType())`. Responde 201
  con su `id`, tamaño y huella SHA-256.
- Solo a los casos que reportó la misma cuenta. Un caso capturado sin conexión no tiene `id`
  hasta que se sincroniza: guarda sus fotos y súbelas con el `case_id` que regresa el lote.
- Subir otra vez la misma foto al mismo caso responde 200 con la que ya estaba: reintentar una
  subida que se cortó no la duplica.
- `GET /api/v1/attachments/{id}/content` regresa el archivo, siempre con token.
- Reduce las fotos antes de subirlas (por ejemplo, a 1600 px por lado): una foto de cámara de
  varios MB tarda en subir con datos móviles.

## 8. Lotes de vacuna (QR)

El servicio `vacunas` (puerto 5225) lleva los lotes que la app lee por QR o código de barras
(ML Kit) y las dosis que se les aplican.

1. Escanea el código y búscalo: `GET /api/v1/vaccine-lots?lot_code=<código>`.
2. Si `total` es 0, pide los datos y regístralo con `POST /api/v1/vaccine-lots`
   (`lot_code`, `disease_id`, `doses_total` y, si los hay, `manufacturer`, `region_id` y
   `expires_on`). Un reintento con los mismos datos responde 200; con otros, 409: alguien ya lo
   registró distinto, así que consúltalo.
3. Al vacunar, `POST /api/v1/vaccine-lots/{id}/doses` con `{"doses": 1}`. Si no quedan dosis
   o el lote caducó, responde 409 y no descuenta nada: muestra el `detail`.

Aplicar dosis necesita conexión: el servidor es quien garantiza que nunca se apliquen más dosis
de las que trae el lote.

## 9. Avisos

`GET /api/v1/notifications?unread=true` (en `notificaciones`) devuelve los avisos de la cuenta, y
`POST /api/v1/notifications/{id}/read` los marca como leídos. No hay notificaciones push: la app
consulta cada cierto tiempo.

## Lo que todavía no existe del lado del servidor

| Necesidad de la app | Estado |
|---------------------|--------|
| Editar un caso | `casos` solo registra y consulta |
| Notificaciones push | Solo consulta; no hay envío |
