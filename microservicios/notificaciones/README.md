# EPIDEMIA - Servicio notificaciones

Avisos para las apps: corrida terminada o fallida, versión aprobada. Cada persona lee y marca
como leídos solo los suyos. Los crean otros servicios por una ruta interna.

Puerto externo: 5261; puerto interno en Docker: 8000. Contrato en
`docs/contratos/notificaciones/openapi.json`.

## Rutas

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| GET | `/api/v1/notifications?unread=true&limit=50` | Cualquier rol con sesión | Las suyas, de la más reciente a la más vieja, con `total` y `no_leidas` |
| POST | `/api/v1/notifications/{notificacion_id}/read` | Cualquier rol con sesión | Marca una suya como leída; si ya lo estaba, no cambia nada |
| POST | `/api/v1/notifications` | **Solo token de servicio** | Crea un aviso. Responde 201 con su `id` |

- Las de otra persona no existen para quien consulta: marcarlas da 404.
- `unread` es `true` o `false`; `limit` va de 1 a 200.

### Crear (ruta interna)

Cuerpo `{user_id, type, title, body?, payload?}`, sin otros campos:

- `type` es uno de `RUN_FINISHED`, `RUN_FAILED`, `THRESHOLD_EXCEEDED`, `ASSIGNMENT`,
  `SCENARIO_PUBLISHED`, `SCENARIO_APPROVED` y `SYSTEM` (CHECK de la tabla, migraciones 003 y
  029).
- `title` lleva como máximo 160 caracteres.
- `payload` es un objeto con los ids para llegar al recurso.

Solo acepta un token de servicio (audiencia `epidemia-interno`, de
`epidemia_comun.seguridad.token_servicio`). El token de una persona, aunque sea de un
ADMINISTRADOR, recibe 401. Lo usan:

- `simulador`: `RUN_FINISHED` y `RUN_FAILED`, para quien pidió la corrida.
- `aprobacion`: `SCENARIO_APPROVED`, para quien armó la versión.

| Caso | Respuesta |
|------|-----------|
| Campos desconocidos, tipo fuera de la lista o `title` vacío | 422 `DATOS_INVALIDOS` |
| No existe el destinatario | 404 `NO_ENCONTRADO` |

## Bitácora

Crear queda como `CREATE` y marcar como leída como `UPDATE`, los dos en la misma transacción.
Al crear no hay persona detrás: `user_id` queda vacío y `user_agent` dice qué servicio lo pidió
(`servicio simulador`). La lógica está en `backend_web/notificaciones.py`.

## Variables

`DATABASE_URL` (rol `svc_notificaciones`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL`;
opcionales `JWT_ISSUER`, `JWT_AUDIENCE` y `JWT_AUDIENCE_INTERNA`.

## Probarlo

```bash
python -m pytest microservicios/notificaciones
python -m microservicios.notificaciones.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5261/api/v1/notifications?unread=true&format=json"
```
