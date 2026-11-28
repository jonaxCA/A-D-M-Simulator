# EPIDEMIA - Servicio auth

Inicia sesión: revisa usuario y contraseña, pide el segundo factor a los perfiles críticos
(D40), revisa el dispositivo (D41), emite el *access* y el *refresh* y abre la sesión en Redis. Renovar, cerrar y revocar sesiones es tarea de `sesiones`.

Puerto externo: 5201; puerto interno en Docker: 8000. Contrato en
`docs/contratos/auth/openapi.json`.

## Rutas

| Método | Ruta                   | Acceso  | Qué hace                                                    |
|--------|------------------------|---------|-------------------------------------------------------------|
| GET    | `/api/v1/auth/captcha` | Público | Regresa `captcha_id` y una suma (`"5 + 7"`) que vence en 300 s |
| POST   | `/api/v1/auth/login`   | Público | Recibe `usuario`, `password`, `captcha_id`, `captcha_respuesta` y `dispositivo_id` (con `dispositivo_etiqueta`, opcional) |
| POST   | `/api/v1/auth/mfa/verify`  | Público (con token de MFA) | Cambia el token de MFA y un código TOTP o de respaldo por la sesión |
| POST   | `/api/v1/auth/mfa/enroll`  | Público (con token de MFA) | Genera el secreto TOTP y su URI `otpauth://` |
| POST   | `/api/v1/auth/mfa/confirm` | Público (con token de MFA) | Activa el MFA con el primer código, regresa 8 códigos de respaldo y abre la sesión |
| DELETE | `/api/v1/auth/mfa/{user_id}` | ADMINISTRADOR | Restablece el MFA de una cuenta; audita `DELETE` en `user_mfa` |

Las cinco primeras son públicas: son la puerta de entrada, todavía no hay token que pedir. Las de
MFA piden el token temporal que regresa `/login`.

### Captcha

Sin SMTP no hay segundo factor por correo; en su lugar, cada intento de login necesita un
captcha nuevo. Va antes que la contraseña, así que para probar una contraseña hay que resolver
uno. Se guarda en Redis (`captcha:<id>`, TTL 300 s) y se borra al usarse, acierte o no. Junto
con el bloqueo de cinco intentos de `auth/datos.py`, frena a quien adivina contraseñas.

### Login

- Usa `attempt_login()` de `auth/datos.py`: bcrypt, bloqueo de 15 minutos tras cinco fallos,
  `failed_attempts` y `last_login_at`. Escribe solo esas columnas de `users`.
- Cuenta inexistente, inactiva, bloqueada o contraseña equivocada: el mismo 401
  `CREDENCIALES_INVALIDAS` con el mensaje del monolito.
- Bitácora: `LOGIN` y `LOGIN_FAILED`, igual que el monolito.
- Al acertar, pide a `sesiones` abrir la sesión (`POST /api/v1/sessions/internal/open`, 8 h) y firma el *access* (HS256, 20 min)
  con `iss`, `aud`, `sub`, `roles`, `sid`, `jti`, `iat`, `nbf` y `exp`: los que revisa
  `@requiere_token` de la biblioteca.
- Respuesta: `access_token`, `refresh_token`, `token_type`, `expires_in` (segundos),
  `sesion_expira` (época Unix) y `usuario` (`id`, `username`, `full_name`, `roles`).

### MFA (D40)

- **Perfiles críticos:** `ADMINISTRADOR`, `EPIDEMIOLOGO` y `AUTORIDAD_SANITARIA`, cambiables con `MFA_PERFILES` (lista
  separada por comas; sin definir o vacía, el MFA está apagado (valor por omisión) hasta que los clientes tengan los dos pasos; se activa con `MFA_PERFILES=ADMINISTRADOR,EPIDEMIOLOGO,AUTORIDAD_SANITARIA`). Los demás perfiles inician sesión como antes.
- **Dos pasos:** con contraseña correcta y un perfil crítico, `/login` no regresa tokens sino
  `mfa_requerido`, `mfa_enrolado`, `mfa_token` y `mfa_expira`. El token es opaco (no un JWT),
  vive 5 min en Redis (`mfa:<huella>`) y se borra al usarlo o al quinto código fallido.
  Si `mfa_enrolado` es falso: `/mfa/enroll` y `/mfa/confirm`; si no: `/mfa/verify`.
- **TOTP:** RFC 6238 con la biblioteca estándar (HMAC-SHA1, 30 s, 6 dígitos, ±1 paso). Un código
  de un paso ya aceptado no sirve otra vez (`user_mfa.last_counter`). Un código de respaldo
  (12 hex, con o sin guiones) sirve una vez; en la base solo está su SHA-256.
- **Secreto:** `user_mfa.secret` está en claro (el servidor debe conocerlo). Solo `svc_auth` lo lee.
- **Respaldo:** 10 caracteres base32 (50 bits), con o sin guion; la base guarda PBKDF2-SHA256 (100 000 vueltas) con la cuenta como sal.
- **Alta del enrolamiento:** `/mfa/enroll` exige `codigo_alta`, de un solo uso y 15 min, que emite un ADMINISTRADOR con
  `POST /api/v1/auth/mfa/{user_id}/enrollment-code` (llave `mfa:alta:<id>`, audita `UPDATE` en `user_mfa`). Un secreto pendiente
  no se sobrescribe durante 15 min (409; un ADMINISTRADOR lo restablece). El primer administrador no tiene quién le emita el código:
  arranca `auth` con `MFA_ENROLAMIENTO_LIBRE=1`, enrola y quita la variable.
- **Tope por cuenta:** 5 códigos probados por cuenta en 15 min (`mfa:fallos:<id>`, contador atómico), aparte del de cada token; al
  agotarse, `/login` y `/mfa/verify` responden 429 `MFA_BLOQUEADO`. Pasar el MFA lo borra.
- **Fallos:** cada código incorrecto audita `LOGIN_FAILED` sobre `user_mfa`.

### Dispositivo y sesiones (D41)

- `dispositivo_id` (8 a 128 caracteres) es obligatorio para los perfiles críticos (solo con el MFA activo) y opcional para
  los demás, salvo con `DISPOSITIVO_OBLIGATORIO=1`. `auth` llama a `sesiones`
  (`SERVICIO_SESIONES_URL`) antes del segundo factor: un dispositivo pendiente o revocado da 403
  `DISPOSITIVO_NO_AUTORIZADO`; con `sesiones` caído, 503.
- Tope de sesiones por cuenta: lo aplica `sesiones` (`MAX_SESIONES_POR_USUARIO` en ese servicio, 3 por
  omisión, supuesto). Al pasarlo cierra la más antigua; `LOGIN` anota cuántas se cerraron.

| Caso                                        | HTTP | `codigo`                 |
|---------------------------------------------|------|--------------------------|
| Falta un campo, o captcha incorrecto/vencido | 422  | `DATOS_INVALIDOS`        |
| Credenciales no válidas                     | 401  | `CREDENCIALES_INVALIDAS` |
| Código de MFA incorrecto                    | 401  | `MFA_CODIGO_INVALIDO`    |
| Token de MFA desconocido, vencido o agotado | 401  | `MFA_TOKEN_INVALIDO`     |
| Dispositivo pendiente o revocado            | 403  | `DISPOSITIVO_NO_AUTORIZADO` |
| `verify` sin MFA, o `enroll`/`confirm` con MFA activo | 409 | `CONFLICTO`    |
| Content-Type distinto de JSON o XML         | 415  | `DATOS_INVALIDOS`        |
| Redis caído                                 | 503  | `SERVICIO_NO_DISPONIBLE` |

## Variables

`SERVICIO_SESIONES_URL`, `MFA_PERFILES`, `MAX_SESIONES_POR_USUARIO` y `DISPOSITIVO_OBLIGATORIO`
(ver arriba). Además `DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`, las mismas que los demás servicios
(`.env.shared` o `microservicios/auth/.env`). `JWT_SECRET_KEY` tiene que ser el mismo en todos
los servicios: es el que verifica los tokens que firma `auth`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/auth -q
python -m microservicios.auth.app

curl "http://127.0.0.1:5201/api/v1/auth/captcha?format=json"
curl -X POST "http://127.0.0.1:5201/api/v1/auth/login?format=json" \
     -H "Content-Type: application/json" \
     -d '{"usuario": "<usuario>", "password": "<contraseña>", "captcha_id": "<id>", "captcha_respuesta": "<suma>"}'
```

El `access_token` va como `Authorization: Bearer <token>` en las rutas protegidas de los demás
servicios.

Corre en `infra/docker-compose.yml`.
