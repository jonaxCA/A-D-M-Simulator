# EPIDEMIA - Servicio sesiones

Renueva, cierra y revoca las sesiones que abre `auth`. Solo usa Redis (módulo `sesiones` de la
biblioteca común): no escribe ni lee tablas de PostgreSQL, salvo la bitácora del logout.

Puerto externo: 5202; puerto interno en Docker: 8000. Contrato en
`docs/contratos/sesiones/openapi.json`.

## Rutas

| Método | Ruta                            | Acceso                 | Qué hace |
|--------|---------------------------------|------------------------|----------|
| POST   | `/api/v1/sessions/refresh`      | Público (con refresh)  | Recibe `refresh_token`; regresa un access nuevo y rota el refresh |
| POST   | `/api/v1/sessions/logout`       | Cualquier sesión       | Revoca el access y cierra la sesión; audita `LOGOUT` |
| GET    | `/api/v1/sessions/current`      | Cualquier sesión       | `usuario`, `roles`, `creada`, `expira` y `access_expira` (época Unix) |
| DELETE | `/api/v1/sessions/user/{id}`    | Solo token de servicio | Cierra todas las sesiones de una cuenta; regresa cuántas cerró |

- **Refresh:** cada uno sirve una vez. Si llega uno ya usado, solo puede venir de una copia, así
  que se cierra la sesión completa (401 `TOKEN_REVOCADO`). Renovar no alarga la sesión: vence
  8 h después del login.
- **Logout:** el access deja de valer aunque no haya vencido, y el refresh ya no renueva.
- **Ruta interna:** la llaman `usuarios` y `roles` al desactivar una cuenta o quitarle un rol
  (`@solo_servicios`, audiencia `epidemia-interno`). Un token de persona recibe 401. No audita:
  lo audita el servicio que hace el cambio en la cuenta.

| Caso                                    | HTTP | `codigo`                 |
|-----------------------------------------|------|--------------------------|
| Falta `refresh_token` o id no válido    | 422  | `DATOS_INVALIDOS`        |
| Refresh desconocido o sesión vencida    | 401  | `TOKEN_INVALIDO`         |
| Refresh reutilizado o sesión cerrada    | 401  | `TOKEN_REVOCADO`         |
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

Pendiente: Dockerfile y entrada en el compose (bloque J); emitir el token de servicio que usa la
ruta interna (bloque L).
