# EPIDEMIA - Servicio sincronizacion

Puerto externo 5222; puerto interno en Docker, 8000. Recibe lotes de casos capturados sin
conexión (app móvil) y los manda **uno por uno** a `casos` (`POST /api/v1/cases`, en JSON,
con el token de quien sincroniza). No escribe tablas de casos.

## Rutas (`/api/v1`)

| Ruta | Roles | Qué hace |
|---|---|---|
| `POST /sync/cases` | CAPTURISTA, ADMINISTRADOR | Procesa el lote y regresa el resultado de cada caso. |
| `GET /sync/batches/{id}` | CAPTURISTA, ADMINISTRADOR | Resultado guardado de un lote (404 si no existe, venció o es de otra persona; el ADMINISTRADOR ve todos). |

## Cuerpo

```json
{"batch_id": "<uuid del cliente>", "device_id": 3,
 "cases": [{"local_uuid": "<uuid>", "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"}]}
```

`lote_id` es alias de `batch_id`. Entre 1 y 100 casos; cada uno necesita `local_uuid` (si
falta, todo el lote es 422). `device_id` del lote se aplica a los casos que no traigan el suyo.
En XML: `<lote><batch_id/><device_id/><cases><item>...</item></cases></lote>`; la respuesta
tiene raíz `resultado_lote`. XSD: `docs/contratos/sincronizacion/lote.xsd`.

## Respuesta

`batch_id`, `device_id`, `recibido_en`, `total`, `creados`, `duplicados`, `rechazados`,
`repetido` y `resultados[]` con `indice`, `local_uuid`, `resultado`, `case_id`, `errores[]`.

- `creado`: casos respondió 201. `duplicado`: 200 (ese `local_uuid` ya existía).
- `rechazado`: casos respondió 400/409/415/422; `errores` trae su mensaje.
- El lote responde 200 aunque haya rechazos; el cliente revisa cada caso.

## Idempotencia, candado y fallas

- Resultado en Redis `sync:lote:<batch_id>`, TTL **7 días** (`SYNC_LOTE_TTL_SECONDS`).
  Reenviar el mismo `batch_id` regresa lo guardado con `repetido: true`, sin llamar a casos
  (aunque el contenido cambie). Otra persona con ese `batch_id` recibe 409.
- Candado `sync:lote:<batch_id>:candado` (300 s) con `candados.candado`: si otra petición
  procesa el mismo lote, 409 `CONFLICTO`.
- Si casos no responde o contesta 5xx: **todo el lote es 503** `SERVICIO_NO_DISPONIBLE`, sin
  reintentos y sin guardar resultado. El cliente reenvía el lote; los casos ya creados salen
  como `duplicado` gracias a `local_uuid`. Un 401/403 de casos se propaga.
- Redis caído: 503.
- Bitácora: un `SYNC` (entidad `sync_batches`, id = `batch_id`) por lote procesado, con
  conteos, en su propia transacción. Si falla, se registra en el log y el lote no se pierde.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (rol `svc_sincronizacion`: solo INSERT en
`audit_log`), `SERVICIO_CASOS_URL` (en Docker, `http://casos:8000`), `SYNC_LOTE_TTL_SECONDS`
(opcional).

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD python -m pytest microservicios/sincronizacion -q
python -m microservicios.sincronizacion.app    # http://127.0.0.1:5222/docs
```

Las pruebas simulan casos, la base y Redis. Ejemplos: `docs/contratos/sincronizacion/ejemplos/`.
