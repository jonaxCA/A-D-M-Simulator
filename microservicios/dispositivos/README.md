# EPIDEMIA - Servicio dispositivos

Registra, consulta y revoca los dispositivos de las apps (tabla `devices`): el teléfono con que
la app móvil captura casos, o la PC de la app de escritorio. Revocar un dispositivo es para un
teléfono perdido o robado: desde ese momento `casos` rechaza los casos que lo traen como
`device_id`, aunque el token de la persona siga vigente.

Puerto externo: 5223; puerto interno en Docker: 8000. Contrato en
`docs/contratos/dispositivos/openapi.json`, con un ejemplo JSON y uno XML por ruta en
`ejemplos/`.

## Rutas

| Método | Ruta | Qué hace |
|--------|------|----------|
| POST | `/api/v1/devices` | Cuerpo `{device_uid, platform?, model?, app_version?, push_token?}`. Registra el dispositivo a nombre de quien inició sesión (**201**), o, si ya era suyo, actualiza `model`, `app_version`, `push_token` y `last_seen_at` (**200**) |
| GET | `/api/v1/devices?user_id=&limit=50` | Los de quien pregunta; ADMINISTRADOR, los de todos o los de `user_id` (`limit` de 1 a 200) |
| GET | `/api/v1/devices/{device_id}` | Uno propio; ADMINISTRADOR, cualquiera |
| POST | `/api/v1/devices/{device_id}/revoke` | Lo revoca para siempre. Uno propio; ADMINISTRADOR, cualquiera |

Las cuatro rutas son para los cuatro roles: cada quien maneja sus dispositivos y ADMINISTRADOR,
los de todos. El dispositivo de otra persona no existe para quien pregunta (404).

- `device_uid` lo genera la app al instalarse (por ejemplo, un UUID): de 8 a 128 letras,
  números o `. _ : -`. Es único, así que no se puede registrar en dos cuentas.
- `platform` es `android` (por omisión), `ios` o `desktop`, y solo cuenta al registrarlo.
- La app llama `POST /api/v1/devices` cada vez que inicia sesión: así se entera de su `id` (el
  `device_id` que manda con cada caso) y deja al día su versión y `last_seen_at`.
- `push_token` se guarda, pero ninguna respuesta lo regresa ni entra a la bitácora: solo
  `has_push_token`.
- Un dispositivo revocado no se puede volver a registrar con el mismo `device_uid`: la app
  tiene que generar uno nuevo. Los casos que ya había sincronizado se quedan.

| Caso | Respuesta |
|------|-----------|
| Cuerpo, `user_id`, `limit` o id inválidos | 422 `DATOS_INVALIDOS` |
| Pedir con `user_id` los dispositivos de otra cuenta sin ser ADMINISTRADOR | 403 `PERMISO_INSUFICIENTE` |
| No existe o es de otra persona | 404 `NO_ENCONTRADO` |
| `device_uid` de otra cuenta o revocado; revocar uno ya revocado | 409 `CONFLICTO` |
| Redis caído | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

Las reglas están en `backend_web/dispositivos.py`, con sus pruebas contra la base
(`backend_web/tests/test_dispositivos.py`):

1. Registrar bloquea la fila de ese `device_uid` (`FOR UPDATE`) para que dos peticiones del
   mismo teléfono no se pisen, y audita `CREATE` o `UPDATE` en la misma transacción.
2. Revocar usa la transición condicionada (`WHERE NOT is_revoked`) y audita `UPDATE`.
3. `casos` revisa el `device_id` de cada caso con `estado_para_captura()`: si no existe o es de
   otra cuenta responde 422, y si está revocado, 409. `sincronizacion` manda cada caso a
   `casos`, así que esos casos salen rechazados en el resultado del lote.

## Variables

`DATABASE_URL` (rol `svc_dispositivos`, migración 031), `JWT_SECRET_KEY`, `REDIS_URL`; opcionales
`JWT_ISSUER` y `JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/dispositivos
python -m unittest backend_web.tests.test_dispositivos
python -m microservicios.dispositivos.app
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"device_uid": "3f2a9c1e-77b0-4d2e-a1f5-0c9b8e6d4a21", "model": "Pixel 7"}' \
     "http://127.0.0.1:5223/api/v1/devices?format=json"
curl -X POST -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5223/api/v1/devices/3/revoke?format=json"
```
