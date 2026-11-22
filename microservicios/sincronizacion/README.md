# EPIDEMIA - Servicio sincronizacion

Puerto externo 5222; puerto interno en Docker, 8000. Recibe lotes de casos capturados sin
conexión (app móvil) y los manda **en una sola llamada** a `casos` (`POST /api/v1/cases/batch`,
en JSON, con el token de quien sincroniza). No escribe tablas de casos. Antes era una llamada por
caso: con carga, un lote de 5 tardaba segundos (prueba de carga en la nube, F4). Si `casos` no
tiene esa ruta (404 o 405), los manda uno por uno con `POST /api/v1/cases`, como antes.
El lote también trae las correcciones hechas sin conexión (`updates`, D47): cada una va a
`PATCH /api/v1/cases/{id}` con la versión que tenía el teléfono y nunca sobrescribe lo que cambió
otra persona.

## Rutas (`/api/v1`)

| Ruta | Roles | Qué hace |
|---|---|---|
| `POST /sync/cases` | CAPTURISTA (D1: el ADMINISTRADOR no captura) | Procesa el lote y regresa el resultado de cada caso. |
| `GET /sync/batches/{id}` | CAPTURISTA, ADMINISTRADOR | Resultado guardado de un lote (404 si no existe, venció o es de otra persona; el ADMINISTRADOR ve todos). |

## Cuerpo

```json
{"batch_id": "<uuid del cliente>", "device_id": 3,
 "cases": [{"local_uuid": "<uuid>", "disease_id": 1, "region_id": 10, "report_date": "2026-10-01"}]}
```

`lote_id` es alias de `batch_id`. Entre 1 y 100 casos; cada uno necesita `local_uuid` (si
falta, todo el lote es 422). `device_id` del lote se aplica a los casos que no traigan el suyo.
Lo revisa `casos` en cada caso: con un dispositivo ajeno o revocado, esos casos salen
`rechazado` en `resultados[]`, con el motivo.
En XML: `<lote><batch_id/><device_id/><cases><item>...</item></cases></lote>`; la respuesta
tiene raíz `resultado_lote`. XSD: `docs/contratos/sincronizacion/lote.xsd`.

### Correcciones sin conexión (D47)

```json
{"batch_id": "<uuid>", "device_id": 3,
 "updates": [{"case_id": 41, "version": 1, "changes": {"age": 35}, "reason": "Edad mal capturada"}]}
```

Un lote trae `cases`, `updates` o las dos cosas, hasta 100 entre ambas. Cada corrección lleva el
`case_id`, la `version` que tenía el teléfono, los campos que cambiaron (`changes`, los mismos que
acepta `PATCH /cases/{id}`) y el motivo. Van después de los casos nuevos, una llamada por
corrección, con `If-Match` y el `device_id` del lote.

## Respuesta

`batch_id`, `device_id`, `recibido_en`, `total`, `creados`, `duplicados`, `rechazados`,
`repetido` y `resultados[]` con `indice`, `local_uuid`, `resultado`, `case_id`, `codigo`,
`errores[]`.

- `creado`: casos respondió 201. `duplicado`: 200 (ese `local_uuid` ya existía). En los dos,
  `codigo` es `null`.
- `rechazado`: casos respondió 400/409/413/415/422; `errores` trae su mensaje y `codigo`, el de
  casos. `CONFLICTO` es un dispositivo revocado y sale en todos los casos del lote: la app deja
  de sincronizar con ese teléfono en lugar de marcar los casos como mal capturados.
  `DATOS_INVALIDOS` es un caso que hay que corregir. Los lotes guardados antes de que existiera
  `codigo` no lo traen.
- El lote responde 200 aunque haya rechazos; el cliente revisa cada caso.

Si el lote trajo correcciones, además: `actualizados`, `conflictos`, `actualizaciones_rechazadas`
y `actualizaciones[]` con `indice`, `case_id`, `resultado`, `version`, `codigo`, `errores[]` y
`caso`:

- `actualizado`: se aplicó; `version` es la nueva (la misma si no cambió nada).
- `conflicto`: alguien cambió el caso desde esa versión (412 de casos). `caso` es el caso como está
  en el servidor y `version` la suya; nada se sobrescribe. La app lo muestra para que la persona
  decida y, si quiere, vuelve a mandar su corrección con la versión nueva.
- `rechazado`: casos respondió 403, 404, 409 o 422 (por ejemplo, el caso ya no está pendiente y
  el CAPTURISTA no puede corregirlo); `codigo` y `errores` traen el motivo.
- Un lote que falló a medias se reenvía completo: una corrección que ya había entrado choca con su
  propia versión, pero como el caso ya tiene lo que se pidió, sale `actualizado`, no `conflicto`.

## Idempotencia, candado y fallas

- Resultado en Redis `sync:lote:<batch_id>`, TTL **7 días** (`SYNC_LOTE_TTL_SECONDS`).
  Reenviar el mismo `batch_id` regresa lo guardado con `repetido: true`, sin llamar a casos
  (aunque el contenido cambie). Otra persona con ese `batch_id` recibe 409.
- Candado `sync:lote:<batch_id>:candado` (300 s) con `candados.candado`: si otra petición
  procesa el mismo lote, 409 `CONFLICTO`.
- **Aviso (D32, RF-C19):** si el lote se procesa por primera vez y `creados` es mayor que 0,
  se llama a `notificaciones` (`POST /api/v1/notifications` con `role: EPIDEMIOLOGO`, tipo
  `NEW_CASES`, `payload` con `batch_id`, `creados` y `total`) con un token de servicio. Es uno por
  lote, no por caso. Un reintento regresa lo guardado y no llega a esa llamada. Es best-effort:
  si falla, el lote se mantiene y solo se anota en el log.
- **Limitaciones conocidas:** (1) si un lote tarda más que el candado (300 s; 100 casos con
  5 s de timeout por llamada pueden pasarse), una segunda petición lo procesa otra vez y el
  aviso `NEW_CASES` puede duplicarse; con el lote en una sola llamada a casos ya es mucho más raro. (2) Si `casos` crea las filas y falla guardar el
  resultado del lote en Redis, el reintento ve todo como duplicado y ya no avisa. Ambos son
  casos extremos y se aceptan.
- Si casos no responde o contesta 5xx: **todo el lote es 503** `SERVICIO_NO_DISPONIBLE`, sin
  reintentos y sin guardar resultado. El cliente reenvía el lote; los casos ya creados salen
  como `duplicado` gracias a `local_uuid`. Un 401/403 de casos se propaga, y un 429 (el límite
  de casos por cuenta, que cuenta cada caso del lote) llega con su `Retry-After`.
- Redis caído: 503.
- Bitácora: un `SYNC` (entidad `sync_batches`, id = `batch_id`) por lote procesado, con
  conteos, en su propia transacción. Si falla, se registra en el log y el lote no se pierde.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (rol `svc_sincronizacion`: solo INSERT en
`audit_log`), `SERVICIO_CASOS_URL` (en Docker, `http://casos:8000`), `SERVICIO_NOTIFICACIONES_URL`, `SYNC_LOTE_TTL_SECONDS`
(opcional).

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD python -m pytest microservicios/sincronizacion -q
python -m microservicios.sincronizacion.app    # http://127.0.0.1:5222/docs
```

Las pruebas simulan casos, la base y Redis. Ejemplos: `docs/contratos/sincronizacion/ejemplos/`.
