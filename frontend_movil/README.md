# App móvil: cómo conectarla a los servicios

La app se entrega en el tercer parcial (D10 de `docs/decisiones.md`) y habla JSON con los
microservicios. Esta guía es lo que necesita para conectarse desde el primer día: dónde están
los servicios, cómo dejar pasar HTTP en desarrollo, con qué cuenta entrar y cómo renovar la
sesión sin cerrarla por accidente. Los contratos de cada servicio están en `docs/contratos/` y
el catálogo en `docs/arquitectura/microservicios.md`.

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

## 2. HTTP sin cifrar en desarrollo

Desde Android 9 la app no puede hacer peticiones `http://` salvo que lo permita su configuración
de seguridad de red. Los servicios corren sin TLS en la PC, así que en desarrollo hay que
permitirlo, y solo para las direcciones de la PC.

Ponlo en el *source set* de debug, así la versión de release sigue sin permitir HTTP:

`app/src/debug/res/xml/network_security_config.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <!-- El emulador ve a la PC en 10.0.2.2 -->
        <domain includeSubdomains="false">10.0.2.2</domain>
        <domain includeSubdomains="false">localhost</domain>
        <!-- La IP de la PC en la red local, para probar en un celular -->
        <domain includeSubdomains="false">192.168.1.20</domain>
    </domain-config>
</network-security-config>
```

`app/src/debug/AndroidManifest.xml`

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:networkSecurityConfig="@xml/network_security_config" />
</manifest>
```

Las IP no aceptan comodines: cambia `192.168.1.20` por la IP real de la PC.

## 3. Cuenta de prueba e inicio de sesión

La semilla de demostración trae una cuenta CAPTURISTA, el rol de la app:

| Usuario | Contraseña | Rol |
|---------|------------|-----|
| `karla.trevino` | `Epidemia2026!` | CAPTURISTA |

Con ese rol la app registra su teléfono (`dispositivos`), registra y consulta casos (`casos`)
y envía y consulta sus lotes (`sincronizacion`). Es una cuenta de demostración: solo sirve en el entorno local.

El inicio de sesión lleva captcha, que la app muestra y la persona contesta:

1. `GET /api/v1/auth/captcha` (en `auth`) devuelve `captcha_id` y `pregunta` (por ejemplo `3 + 5`).
2. `POST /api/v1/auth/login` con `usuario`, `password`, `captcha_id` y `captcha_respuesta`.
3. La respuesta trae `access_token` (20 minutos, `expires_in`), `refresh_token` y la cuenta.

Cada petición protegida lleva `Authorization: Bearer <access_token>`. Guarda el refresh cifrado
(EncryptedSharedPreferences o Keystore), nunca en texto plano. La sesión dura 8 horas desde el
inicio de sesión y renovarla no la alarga: después hay que volver a entrar. Para salir,
`POST /api/v1/sessions/logout` (en `sesiones`) y borra lo guardado.

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

Con OkHttp, la forma natural es un `Authenticator` sincronizado (esquema, no código probado):

```kotlin
class Renovador(private val almacen: AlmacenSesion, private val sesiones: ApiSesiones) : Authenticator {
    private val candado = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.priorResponse != null) return null          // ya se reintentó una vez
        val usado = response.request.header("Authorization")?.removePrefix("Bearer ") ?: return null
        synchronized(candado) {
            val actual = almacen.access()
            if (actual != null && actual != usado) {               // otra petición ya renovó
                return response.request.newBuilder().header("Authorization", "Bearer $actual").build()
            }
            val par = sesiones.renovar(almacen.refresh() ?: return null)   // cliente sin este Authenticator
                ?: run { almacen.borrar(); return null }                  // 401: a iniciar sesión
            almacen.guardar(par.access, par.refresh)
            return response.request.newBuilder().header("Authorization", "Bearer ${par.access}").build()
        }
    }
}
```

`Authenticator` se llama con cualquier 401; antes de renovar, revisa que el `codigo` del cuerpo
sea `TOKEN_EXPIRADO`.

## 5. Captura sin conexión y sincronización

- Cada caso lleva un `local_uuid` generado en el celular. `casos` lo usa para no duplicar: el
  mismo `local_uuid` otra vez responde 200 con el caso existente y `duplicado: true`.
- Los casos capturados sin conexión se mandan en lotes a `POST /api/v1/sync/cases` (en
  `sincronizacion`): un `batch_id` (UUID del celular) y de 1 a 100 casos.
- Conserva el `batch_id` hasta que el lote responda 200: reenviar el mismo lote regresa el
  resultado guardado (`repetido: true`) y no crea nada dos veces. Ese resultado se guarda 7 días.
- El lote responde 200 aunque haya casos rechazados: revisa `resultados[]`, que dice por cada
  caso si se creó, era duplicado o se rechazó y por qué.
- El `device_id` de cada caso (o del lote) es el `id` que regresa `dispositivos` al registrar el
  teléfono (sección 6). Sin `device_id` el caso también se acepta, pero no queda ligado al
  teléfono y llega sin `synced_at`.

## 6. Registrar el teléfono

El servicio `dispositivos` (puerto 5223) lleva los teléfonos de cada cuenta, para poder
revocar uno perdido sin tocar la cuenta.

1. Al instalarse, la app genera un `device_uid` (por ejemplo, un UUID) y lo guarda: es el mismo
   mientras la app siga instalada. De 8 a 128 letras, números o `. _ : -`.
2. Después de cada inicio de sesión, `POST /api/v1/devices` con `{"device_uid": "...",
   "platform": "android", "model": "...", "app_version": "..."}`. La primera vez responde 201;
   las siguientes, 200, y actualiza la versión y la última conexión. La respuesta trae el `id`:
   ese es el `device_id` de los casos.
3. Si responde 409, ese `device_uid` es de otra cuenta o está revocado: genera uno nuevo y vuelve
   a registrarte.

Desde que alguien revoca el teléfono (`POST /api/v1/devices/{id}/revoke`, la misma persona o
ADMINISTRADOR), `casos` responde 409 `CONFLICTO` a sus casos, también dentro de un lote, aunque
el token siga vigente. La app debe dejar de capturar y pedir que se vuelva a iniciar sesión. Lo
que ya había sincronizado se queda. `push_token` se puede mandar al registrar, pero todavía no
hay notificaciones push.

## 7. Avisos

`GET /api/v1/notifications?unread=true` (en `notificaciones`) devuelve los avisos de la cuenta, y
`POST /api/v1/notifications/{id}/read` los marca como leídos. No hay notificaciones push: la app
consulta cada cierto tiempo.

## Lo que todavía no existe del lado del servidor

| Necesidad de la app | Estado |
|---------------------|--------|
| Fotos del caso | Falta el servicio `evidencias` (la tabla `case_attachments` ya existe) |
| QR de lotes de vacuna | Falta el servicio `vacunas` |
| Editar un caso | `casos` solo registra y consulta |
| Notificaciones push | Solo consulta; no hay envío |
