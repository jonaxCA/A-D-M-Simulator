# App móvil: cómo conectarla a los servicios

La app se entrega en el tercer parcial (D10 de `docs/decisiones/decisiones.md`) y habla JSON con los
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

En Windows usa ese JDK (JetBrains Runtime). Si Gradle no lo encuentra, descarga un JDK 25 de
Adoptium, y con ese fallan las pruebas que usan DataStore (`AlmacenSesionTest`, `RenovadorTest`,
`AvisosTest`…) con `Unable to rename … .preferences_pb.tmp`: en las pruebas JVM, DataStore cambia
el archivo con `File.renameTo`, que en Windows, con ese JDK, no reemplaza uno existente (con el de
Android Studio sí pasan). Gradle reutiliza un
daemon que ya esté corriendo con otro JDK, así que después de cambiar `JAVA_HOME` corre
`./gradlew --stop`.

Dónde va cada cosa dentro de `app/src/main/java/com/estudiante/simuladorepidemico/`:

| Paquete | Qué lleva |
|---------|-----------|
| (raíz) | `MainActivity` (la única Activity), `EpidemiaApp` y `Contenedor`: las dependencias se arman a mano, sin Hilt |
| `red/` | OkHttp, Retrofit, el directorio de servicios (sección 1), el `Authenticator` que renueva (sección 4) y una interfaz por servicio en `red/api/` |
| `sesion/` | Tokens, cifrados con una llave del Keystore y guardados en DataStore, y el registro del teléfono en `dispositivos` (`Telefono.kt`, sección 6) |
| `ubicacion/` | La lectura del GPS para un caso (`Ubicador`), con Google Play services |
| `avisos/` | Los avisos de `notificaciones` (`Avisos`) y la notificación del teléfono (`Notificador`) |
| `local/` | Room (`epidemia.db`): los casos capturados, sus fotos por subir, los catálogos de enfermedades y municipios y los formularios por enfermedad (secciones 5, 7 y 10), y los archivos de las fotos (`Fotos.kt`). Los datos de salud de cada caso van cifrados (`DatosDeSalud`, sección 10). El esquema de cada versión queda en `app/schemas/` |
| `trabajos/` | El `Sincronizador`, que manda los casos en lotes y sube sus fotos, y `TrabajoSincronizar`, que WorkManager corre cuando hay red; `TrabajoAvisos`, que consulta los avisos cada 15 minutos |
| `ui/` | Una carpeta por pantalla con su ViewModel (`login`, `perfil`, `casos`, `fotos`, `vacunas`, `avisos`), más `tema` y `navegacion`. Ya están `login`, `inicio`, `casos` (Capturar caso y Mis casos, con sus fotos), `vacunas` (lectura del QR, registro del lote y aplicación de dosis), `avisos`, `perfil` y `navegacion`, que empieza en el login o en el inicio según haya sesión, regresa al login cuando se pierde, pide el permiso de red local y pone arriba de todas las pantallas la franja que dice si hay conexión (`IndicadorConexion.kt`, RF-I20). `casos` también tiene el seguimiento de un caso (`PantallaSeguimiento`) y `consulta`, los casos por zona (sección 10). `ui/Formato.kt` da formato a fechas, roles, avisos y los valores de un caso, y `ui/Campos.kt` tiene los campos que comparten los formularios |

`app/src/debug/` lleva lo que solo vale en desarrollo, como el permiso de HTTP sin cifrar
(sección 2). La raíz de Let's Encrypt que trae la app está en `app/src/main/res/raw/` (también
sección 2).

El ícono es un pin de ubicación (un caso en campo) con una partícula de virus, sobre verde azulado.
Lo genera `herramientas/icono.py` desde una sola geometría: los vectoriales del ícono adaptativo
(`drawable/ic_launcher_*.xml`, con su capa monocroma para los íconos temáticos de Android 13) y los
WebP de Android 7 (`mipmap-*dpi/`). Para cambiarlo, se edita el script y se corre
`python herramientas/icono.py app/src/main/res` (necesita Pillow).

Las pruebas unitarias (`app/src/test/`) corren en la PC contra un MockWebServer. Las de
`app/src/androidTest/` (el Keystore, las consultas de Room y las pantallas) necesitan un emulador:
`./gradlew connectedDebugAndroidTest`. Dale al emulador 3 GB de RAM o más (Device Manager >
editar > RAM): con 2 GB, Android 17 mata el proceso de la prueba por falta de memoria y Gradle
solo dice "Process crashed".

Antes de probar, levanta el compose en la PC (`docs/INSTALACION.md`):

```bash
python infra/genera_env.py
docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait
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

La configuración de release (`app/src/main/res/xml/network_security_config.xml`) solo permite
HTTPS. El *source set* de debug la reemplaza con la suya
(`app/src/debug/res/xml/network_security_config.xml`), que además permite HTTP. Como la IP de
la PC cambia según la red y no acepta comodines, en debug se permite HTTP hacia cualquier
dirección.

Las dos configuraciones confían en las raíces del sistema y en ISRG Root X1, la raíz de Let's
Encrypt, que la app trae en `app/src/main/res/raw/isrg_root_x1.crt` (D26). Android la incluye de
fábrica solo desde la 7.1.1 (API 25), y la app acepta desde la 7.0 (`minSdk 24`): sin ella, un
teléfono con Android 7.0 rechazaría el certificado del servidor. `RaicesTlsTest` revisa la huella
de la raíz y que las dos configuraciones la conserven. Si cambias la de debug, deja sus
`trust-anchors`.

La app empieza por el directorio, que por omisión busca en `http://10.0.2.2:5262/` (el
emulador). Para un celular, agrega a tu `~/.gradle/gradle.properties`, que no está en el
repositorio:

```properties
epidemia.directorio=http://192.168.1.20:5262/
```

Cambia `192.168.1.20` por la IP de tu PC.

Para el APK de la demostración en la nube, el directorio es el del dominio, que ya responde por
HTTPS con su certificado de Let's Encrypt:

```bash
./gradlew assembleDebug -Pepidemia.directorio=https://epidemos.app/estado-servicios/
```

El APK queda en `app/build/outputs/apk/debug/app-debug.apk`. No se sube al repositorio.

## 3. Cuenta de prueba e inicio de sesión

La semilla de demostración trae una cuenta CAPTURISTA, el rol de la app:

| Usuario | Contraseña | Rol |
|---------|------------|-----|
| `karla.trevino` | `Epidemia2026!` | CAPTURISTA |

Con ese rol la app registra su teléfono (`dispositivos`), registra y consulta casos (`casos`),
sube sus fotos (`evidencias`), escanea lotes de vacuna (`vacunas`) y envía y consulta sus
lotes de casos (`sincronizacion`). Es una cuenta de demostración: solo sirve en el entorno local.

Los otros perfiles también entran, con su propio menú (D56, `ui/inicio/Menu.kt`): el EPIDEMIOLOGO y
la AUTORIDAD_SANITARIA ven «Casos» (los del servidor, con el seguimiento solo para leer),
«Campañas», los lotes de vacuna para consultarlos, la consulta por zona y los avisos; el
ADMINISTRADOR, lo mismo y además registra lotes; ANALISTA e INVESTIGADOR, la consulta por zona.
Ninguno ve «Capturar caso» ni «Mis casos» (RF-I19). La app guarda los roles que regresa el login con
la sesión, para saberlos sin red; una sesión abierta antes de guardarlos los pregunta a
`/users/me`, y mientras tanto queda el menú del CAPTURISTA. Ocultar un botón no es el candado:
`casos`, `sincronizacion` y `vacunas` rechazan a quien no debe, y `casos` y `zonas` recortan lo
que se ve al alcance por región de la cuenta (D43).

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
- `GET /api/v1/cases/{case_id}/attachments` lista las de un caso, con su tipo y su huella.
- `GET /api/v1/attachments/{id}/url` da una URL firmada del bucket (D30) que vence en 15 minutos;
  `GET /api/v1/attachments/{id}/content` regresa el archivo por el servicio, siempre con token.
- Reduce las fotos antes de subirlas (por ejemplo, a 1600 px por lado): una foto de cámara de
  varios MB tarda en subir con datos móviles.

### Cómo lo hace la app

- En Capturar caso, "Tomar foto" abre la app de cámara del teléfono y "De la galería", el
  selector de fotos del sistema. La cámara escribe en un archivo de la app con un permiso de una
  sola vez (`FileProvider`, `res/xml/rutas_fotos.xml`). Como el manifiesto declara `CAMERA` (para
  los QR de la sección 8), Android exige ese permiso también para abrir la app de cámara: se pide
  antes de la primera foto. La galería no pide nada. Hasta cinco fotos por caso.
- Cada foto se reduce a 1600 px por lado, se endereza según su EXIF y se guarda como JPEG nuevo,
  sin EXIF: así no viaja la ubicación GPS que algunas cámaras guardan en el archivo. La foto
  completa de la cámara se borra en cuanto se reduce.
- Los archivos viven en `filesDir/fotos`, fuera de los respaldos. Las fotos entran a
  `epidemia.db` con el caso, en la misma transacción; salir del formulario sin guardar las borra.
- El `Sincronizador` las sube después de mandar los lotes, solo las de casos que ya tienen
  `case_id`. Una subida que falla por red se reintenta; una que evidencias rechaza (403, 404, 413
  o 422) queda con su motivo. Subida o rechazada, el archivo se borra del teléfono. Mis casos dice
  cuántas van subidas, por subir o rechazadas; descartar un caso rechazado borra sus fotos.
- En el seguimiento de un caso, **Fotos** lista las que tiene en `evidencias`. "Ver" pide la URL
  firmada justo antes de bajarla (no se guarda) y baja el archivo directo del bucket con el
  cliente **sin token**: el de la sesión no sale hacia Google. Lo que llega se compara con la
  huella SHA-256 de la lista y, si no coincide, no se muestra. Hasta 20 MB; se decodifica
  reducida a 2048 px por lado y no se escribe en el teléfono. Los PDF no se abren en la app.
  Si `evidencias` no responde, el caso se sigue viendo (`SeguimientoViewModelTest`).

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

### Cómo lo hace la app

- "Lotes de vacuna", en el inicio, abre la cámara trasera (CameraX) y ML Kit lee QR, Data Matrix,
  Code 128, Code 39 y EAN-13 con el modelo dentro de la app (`ui/vacunas/Escaner.kt`). El permiso
  de cámara se pide al entrar; sin él, o si la cámara no lee la etiqueta, el código se escribe a
  mano. Antes de buscarlo, la app revisa que sea como lo pide `vacunas`: de 1 a 60 caracteres
  visibles, sin espacios.
- Si el lote existe, muestra la enfermedad, el fabricante, el municipio, cuántas dosis quedan y
  la caducidad, y deja aplicar de 1 hasta las que quedan (máximo 1,000 por vez). Un lote caducado
  o sin dosis no ofrece aplicar. Si no existe, pide los datos de la caja y lo registra; si
  alguien lo registró distinto mientras tanto (409), muestra el suyo.
- Aplicar dosis no se reintenta: si la respuesta no llega, no se sabe si el servidor ya las
  descontó, así que la app lo dice y vuelve a consultar el lote. Por lo mismo, el cliente HTTP de
  la app no reintenta solo (`retryOnConnectionFailure(false)` en `red/ClienteHttp.kt`): OkHttp
  volvía a mandar el POST cuando la respuesta se cortaba en una conexión reusada.
- Sin red, la pantalla lo dice: consultar lotes y aplicar dosis necesita conexión.

## 9. Avisos

`GET /api/v1/notifications?unread=true` (en `notificaciones`) devuelve los avisos de la cuenta, y
`POST /api/v1/notifications/{id}/read` los marca como leídos. No hay notificaciones push: la app
consulta cada cierto tiempo.

### Cómo lo hace la app

- "Avisos", en el inicio, dice cuántos hay sin leer y abre la lista de los últimos 50 de la
  cuenta, del más nuevo al más viejo. Tocar uno sin leer lo marca como leído; "Marcar leídos" los
  marca uno por uno, porque `notificaciones` no tiene una ruta para todos.
- Sin push, `TrabajoAvisos` (WorkManager) consulta cada 15 minutos con red, lo menos que permite
  WorkManager, y si llegaron avisos nuevos muestra una notificación del teléfono. Al tocarla, la
  app abre los avisos. En la pantalla bloqueada no se ve el contenido, solo "Tienes avisos nuevos".
- Para no avisar dos veces de lo mismo, la app guarda por cuenta el id más alto que ya se vio, en
  la pantalla o en una notificación (`avisos/Avisos.kt`). Otra cuenta en el mismo teléfono lleva
  el suyo.
- El permiso de notificaciones (Android 13+) se pide desde la pantalla de avisos, no al abrir la
  app. Sin él, o con las notificaciones apagadas en Ajustes, los avisos solo se ven en esa pantalla.

## 10. Formularios, seguimiento, consulta y datos cifrados

Lo que pidió la retroalimentación para la app (B4 del checklist del tercer parcial):

- **Formularios por enfermedad (D48).** Con los catálogos se baja `GET /api/v1/forms/current` (en
  `casos`) y se guarda en `epidemia.db`. Al elegir la enfermedad, la captura agrega sus campos
  (texto, entero, decimal, fecha, booleano, opción u opciones) y los valida igual que `casos`:
  obligatorios, tipo y rango. El lote manda `form_id` y `form_answers` con cada caso.
- **Control de calidad.** La captura dice qué datos faltan (los mismos que `casos` marca como
  incompletos, D49) sin impedir guardar, y avisa si en el teléfono ya hay un caso con la misma
  enfermedad, municipio, fecha, edad y sexo: se guarda solo si la persona confirma que es otro.
- **Ubicación a mano.** Si el GPS no conviene, "Escribir las coordenadas" acepta latitud y longitud.
- **Seguimiento (D47).** Un caso recibido abre su estado en el servidor y su historial
  (`GET /api/v1/cases/{id}` y `.../history`). Mientras está pendiente, quien lo capturó lo corrige
  con `PATCH /api/v1/cases/{id}` y `If-Match` con la versión que leyó. Si alguien más lo cambió,
  responde 412: la app lo dice y muestra cómo quedó, sin pisarlo. Corregir necesita conexión (no
  usa los `updates` del lote). Solo el servidor dice si se validó, se descartó o se marcó duplicado.
- **Datos faltantes (D49).** El inicio y Mis casos cuentan y listan `GET /api/v1/cases/incomplete`;
  cada uno abre su seguimiento para completarlo.
- **Consulta por zona.** Casos, incidencia por 100 mil y nivel por municipio, para una enfermedad
  (o todas) y 7, 30 o 90 días (`GET /api/v1/zones`, con el alcance que dé el servidor).
- **Perfil.** Muestra la institución y la región asignada de la cuenta (E7) y el estado de conexión.
- **Datos de salud cifrados.** La edad, el sexo, el inicio de síntomas, el resultado, la gravedad,
  la ubicación y las respuestas de un caso se guardan en una sola columna (`datos`), cifrada con la
  llave del Keystore (`CifradorKeystore`, la misma de los tokens). La enfermedad, el municipio y la
  fecha quedan en claro para listar los casos. Los casos guardados antes de la versión 3 de la base
  conservan esas columnas en claro hasta que se envían.

## Lo que todavía no existe del lado del servidor

| Necesidad de la app | Estado |
|---------------------|--------|
| Notificaciones push | Solo consulta; no hay envío |
