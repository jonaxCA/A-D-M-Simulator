# EPIDEMIA - Servicio auth

Inicia sesión: revisa usuario y contraseña, emite el *access* y el *refresh* y abre la sesión
en Redis. Renovar, cerrar y revocar sesiones es tarea de `sesiones`.

Puerto externo: 5201; puerto interno en Docker: 8000. Contrato en
`docs/contratos/auth/openapi.json`, con ejemplos en `docs/contratos/auth/ejemplos/`.

## Rutas

| Método | Ruta                   | Acceso  | Qué hace                                                    |
|--------|------------------------|---------|-------------------------------------------------------------|
| GET    | `/api/v1/auth/captcha` | Público | Regresa `captcha_id` y una suma (`"5 + 7"`) que vence en 300 s |
| POST   | `/api/v1/auth/login`   | Público | Recibe `usuario`, `password`, `captcha_id` y `captcha_respuesta` |

Las dos son públicas: son la puerta de entrada, todavía no hay token que pedir.

### Captcha

Sin SMTP no hay segundo factor por correo; en su lugar, cada intento de login necesita un
captcha nuevo. Va antes que la contraseña, así que para probar una contraseña hay que resolver
uno. Se guarda en Redis (`captcha:<id>`, TTL 300 s) y se borra al usarse, acierte o no. Junto
con el bloqueo de cinco intentos de `backend_web.auth`, frena a quien adivina contraseñas.

### Login

- Usa `backend_web.auth.attempt_login()`: bcrypt, bloqueo de 15 minutos tras cinco fallos,
  `failed_attempts` y `last_login_at`. Escribe solo esas columnas de `users`.
- Cuenta inexistente, inactiva, bloqueada o contraseña equivocada: el mismo 401
  `CREDENCIALES_INVALIDAS` con el mensaje del monolito.
- Bitácora: `LOGIN` y `LOGIN_FAILED`, igual que el monolito.
- Al acertar, abre la sesión con `sesiones.abrir()` (8 h) y firma el *access* (HS256, 20 min)
  con `iss`, `aud`, `sub`, `roles`, `sid`, `jti`, `iat`, `nbf` y `exp`: los que revisa
  `@requiere_token` de la biblioteca.
- Respuesta: `access_token`, `refresh_token`, `token_type`, `expires_in` (segundos),
  `sesion_expira` (época Unix) y `usuario` (`id`, `username`, `full_name`, `roles`).

| Caso                                        | HTTP | `codigo`                 |
|---------------------------------------------|------|--------------------------|
| Falta un campo, o captcha incorrecto/vencido | 422  | `DATOS_INVALIDOS`        |
| Credenciales no válidas                     | 401  | `CREDENCIALES_INVALIDAS` |
| Content-Type distinto de JSON o XML         | 415  | `DATOS_INVALIDOS`        |
| Redis caído                                 | 503  | `SERVICIO_NO_DISPONIBLE` |

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`, las mismas que los demás servicios
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

Pendiente: Dockerfile y entrada en el compose (bloque J) y evidencia contra la base real.
