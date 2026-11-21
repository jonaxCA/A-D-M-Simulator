# EPIDEMIA - Servicio sesiones

Abre (a petición de `auth`), renueva, cierra y revoca las sesiones (Redis, `almacen.py`) y lleva los dispositivos desde los que cada cuenta puede iniciar sesión (D41). Escribe
`session_devices` y la bitácora.

Puerto externo: 5202; puerto interno en Docker: 8000. Contrato en
`docs/contratos/sesiones/openapi.json`.

## Rutas

| Método | Ruta                            | Acceso                 | Qué hace |
|--------|---------------------------------|------------------------|----------|
| POST   | `/api/v1/sessions/refresh`      | Público (con refresh)  | Recibe `refresh_token`; regresa un access nuevo y rota el refresh |
| POST   | `/api/v1/sessions/logout`       | Cualquier sesión       | Revoca el access y cierra la sesión; audita `LOGOUT` |
| GET    | `/api/v1/sessions/current`      | Cualquier sesión       | `usuario`, `roles`, `creada`, `expira` y `access_expira` (época Unix) |
| DELETE | `/api/v1/sessions/user/{id}`    | Solo token de servicio | Cierra todas las sesiones de una cuenta; regresa cuántas cerró |
| POST   | `/api/v1/sessions/internal/open` | Solo token de servicio | La llama `auth` con credenciales ya validadas: abre la sesión (8 h), aplica el tope y regresa `sid`, `refresh`, `expira` y `cerradas` |
| POST   | `/api/v1/sessions/devices/check` | Solo token de servicio | La llama `auth` al iniciar sesión: registra el dispositivo y regresa su ficha (`status`) |
| GET    | `/api/v1/sessions/devices`      | Cualquier sesión       | Los dispositivos de quien pregunta; con `?user_id=`, los de otra cuenta (solo ADMINISTRADOR) |
| POST   | `/api/v1/sessions/devices/{id}/authorize` | Dueño o ADMINISTRADOR | Autoriza un dispositivo pendiente; un revocado solo lo reautoriza ADMINISTRADOR |
| POST   | `/api/v1/sessions/devices/{id}/revoke` | Dueño o ADMINISTRADOR | Revoca un dispositivo y cierra las sesiones abiertas desde él |

- **Refresh:** cada uno sirve una vez. Si llega uno ya usado, solo puede venir de una copia, así
  que se cierra la sesión completa (401 `TOKEN_REVOCADO`). Renovar no alarga la sesión: vence
  8 h después del login.
- **Logout:** el access deja de valer aunque no haya vencido, y el refresh ya no renueva.
- **Ruta interna:** la llaman `usuarios` y `roles` al desactivar una cuenta o quitarle un rol
  (`@solo_servicios`, audiencia `epidemia-interno`). Un token de persona recibe 401. No audita:
  lo audita el servicio que hace el cambio en la cuenta.

- **Dispositivos (D41):** de cada `dispositivo_id` solo se guarda su SHA-256. El primero de una
  cuenta nace `autorizado`; los demás, `pendiente`, y `auth` responde 403
  `DISPOSITIVO_NO_AUTORIZADO` hasta que la persona (desde una sesión abierta) o un ADMINISTRADOR
  lo autoriza. La sesión guarda la huella de su dispositivo para poder cerrarla al revocarlo.
  El dispositivo de un tercero no existe: 404. Quien no es ADMINISTRADOR solo autoriza o revoca desde una sesión abierta en un dispositivo autorizado (403 `DISPOSITIVO_NO_AUTORIZADO`). `/internal/open` y `/devices/check` solo aceptan el token de servicio de `auth`. Máximo 10 dispositivos pendientes por cuenta (429); `MAX_SESIONES_POR_USUARIO` inválido (no entero o menor a 1) usa 3 y avisa en el log. Autorizar y revocar auditan `UPDATE` en
  `session_devices`.
- **Tope de sesiones:** lo aplica `almacen.abrir(..., maximo=N)` cuando `auth` abre
  una sesión (`MAX_SESIONES_POR_USUARIO` en este servicio, 3 por omisión, supuesto): cierra la más antigua.

| Caso                                    | HTTP | `codigo`                 |
|-----------------------------------------|------|--------------------------|
| Falta `refresh_token` o id no válido    | 422  | `DATOS_INVALIDOS`        |
| Refresh desconocido o sesión vencida    | 401  | `TOKEN_INVALIDO`         |
| Refresh reutilizado o sesión cerrada    | 401  | `TOKEN_REVOCADO`         |
| Dispositivo de otra cuenta, o inexistente | 404 | `NO_ENCONTRADO`          |
| Dispositivo ya en ese estado            | 409  | `CONFLICTO`              |
| Reautorizar un revocado sin ser ADMINISTRADOR | 403 | `PERMISO_INSUFICIENTE` |
| Redis caído                             | 503  | `SERVICIO_NO_DISPONIBLE` |

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`, las mismas que `auth`. `JWT_SECRET_KEY` y
`REDIS_URL` tienen que ser los mismos que los de `auth`: este servicio firma el access renovado
y lee la sesión que `auth` abrió.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/sesiones -q
python -m microservicios.sesiones.app

# Con el access y el refresh que regresa POST /api/v1/auth/login:
curl -H "Authorization: Bearer <access>" "http://127.0.0.1:5202/api/v1/sessions/current?format=json"
curl -X POST "http://127.0.0.1:5202/api/v1/sessions/refresh?format=json" \
     -H "Content-Type: application/json" -d '{"refresh_token": "<refresh>"}'
curl -X POST -H "Authorization: Bearer <access>" "http://127.0.0.1:5202/api/v1/sessions/logout?format=json"
```

Corre en `infra/docker-compose.yml`. Pendiente: emitir el token de servicio que usa la ruta
interna (bloque L).
