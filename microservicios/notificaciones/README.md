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

Cuerpo `{user_id | role, type, title, body?, payload?}`, sin otros campos. `role`
(`EPIDEMIOLOGO`, `ADMINISTRADOR` o `CAPTURISTA`) va en lugar de `user_id` y crea un aviso por cada persona activa con ese rol;
responde 201 con `{role, type, total}`. Mandar los dos es 422.


- `type` es uno de `RUN_FINISHED`, `RUN_FAILED`, `THRESHOLD_EXCEEDED`, `ASSIGNMENT`,
  `SCENARIO_PUBLISHED`, `SCENARIO_APPROVED`, `SCENARIO_SUBMITTED`, `SCENARIO_REJECTED`,
  `NEW_CASES`, `SYSTEM`, `CASE_REJECTED`, `CAMPAIGN` y `DATA_INCOMPLETE` (CHECK de la tabla,
  migraciones 003, 029, 037, 057 y 060).
- `title` lleva como máximo 160 caracteres.
- `payload` es un objeto con los ids para llegar al recurso.

Solo acepta un token de servicio (audiencia `epidemia-interno`, de
`epidemia_comun.seguridad.token_servicio`). El token de una persona, aunque sea de un
ADMINISTRADOR, recibe 401. Lo usan:

- `simulador`: `RUN_FINISHED` y `RUN_FAILED`, para quien pidió la corrida.
- `aprobacion`: `SCENARIO_SUBMITTED` (a los EPIDEMIOLOGO), `SCENARIO_APPROVED` y
  `SCENARIO_REJECTED` (a quien armó la versión).
- `sincronizacion`: `NEW_CASES`, a los EPIDEMIOLOGO, una vez por lote.
- `casos`: `CASE_REJECTED`, a quien capturó el caso, cuando un EPIDEMIOLOGO lo descarta o lo
  marca como duplicado (D47).
- `casos`, también `DATA_INCOMPLETE`, a quien capturó casos a los que les faltan datos (uno por
  captura o por lote, D49).
- `vacunas`: `CAMPAIGN`, a los CAPTURISTA, al crear o cancelar una campaña (D49).
- `estado-servicios`: `SYSTEM`, a los ADMINISTRADOR, cuando un servicio cae, se degrada o se
  recupera (alertas técnicas, F7; ver su README).

| Caso | Respuesta |
|------|-----------|
| Campos desconocidos, tipo fuera de la lista o `title` vacío | 422 `DATOS_INVALIDOS` |
| No existe el destinatario | 404 `NO_ENCONTRADO` |

## Bitácora

Crear queda como `CREATE` y marcar como leída como `UPDATE`, los dos en la misma transacción.
Al crear no hay persona detrás: `user_id` queda vacío y `user_agent` dice qué servicio lo pidió
(`servicio simulador`). La lógica está en `backend_web/notificaciones.py`.

## Variables

`DATABASE_URL` (rol `svc_notificaciones`, migraciones 029 y 037; esta le da lectura de `users`, `user_roles` y `roles` para los avisos a un rol), `JWT_SECRET_KEY`, `REDIS_URL`;
opcionales `JWT_ISSUER`, `JWT_AUDIENCE` y `JWT_AUDIENCE_INTERNA`.

## Probarlo

```bash
python -m pytest microservicios/notificaciones
python -m microservicios.notificaciones.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5261/api/v1/notifications?unread=true&format=json"
```

## Preferencias (D49)

`GET /api/v1/notifications/preferences` da los tipos de aviso que le llegan a quien consulta según su
perfil, con `enabled` y `fijo`; `PUT` con `{tipo: true o false}` los apaga o los prende
(`notification_preferences`, migración 060; sin fila, prendido). Por perfil:

| Perfil | Tipos |
|---|---|
| CAPTURISTA | `CASE_REJECTED`, `CAMPAIGN`, `DATA_INCOMPLETE` |
| EPIDEMIOLOGO | `SCENARIO_SUBMITTED`, `NEW_CASES` |
| ANALISTA | `RUN_FINISHED`, `RUN_FAILED`, `SCENARIO_APPROVED`, `SCENARIO_REJECTED` |
| ADMINISTRADOR | los de ANALISTA y `SYSTEM`, que no se apaga |

Un aviso apagado no se crea: a una persona, `POST /notifications` responde 200 con `id` null y
`omitida` true; a un rol, se salta a quien lo apagó. Quien avisa no lo toma como error. Un tipo que
no le llega, `SYSTEM` o un valor que no es booleano es 422.
