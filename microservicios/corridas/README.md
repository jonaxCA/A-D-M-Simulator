# EPIDEMIA - Servicio corridas

Lanza, consulta, cancela y reintenta corridas de simulación. Lanzar crea el lote y la corrida en
PostgreSQL (`encolado`) y la mete en la cola de Redis de su motor; la ejecuta el `simulador`
de ese motor. Solo se simula una versión aprobada.

Puerto externo: 5241; puerto interno en Docker: 8000. Contrato en
`docs/contratos/corridas/openapi.json`, con un ejemplo JSON y uno XML por ruta en
`ejemplos/`. Las respuestas XML validan contra `docs/contratos/corridas/corrida.xsd`.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/runs` | ANALISTA, ADMINISTRADOR | Cuerpo `{scenario_version_id, seed?, engine?, priority?, replicas?, forzar_error?}`. Responde **202** con `id`, `batch_id`, `seed`, `engine`, `priority` y `status: encolado` |
| GET | `/api/v1/runs?limit=20` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Las corridas más recientes, con su `engine` y su `scenario_version_id` (`limit` de 1 a 100). Filtros opcionales: `scenario_id`, `scenario_version_id`, `status`, `engine`, `from` y `to` |
| GET | `/api/v1/runs/{run_id}` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Estado, `progress`, `engine`, `terminal`, `priority`, `queue_position` y la estimación (`estimated_seconds`, `estimate_samples`, `estimate_reason`) |
| GET | `/api/v1/runs/{run_id}/equivalent` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Otra corrida completada con la misma versión, semilla y huella, con su `resumen` (`null` si no hay): la demostración de reproducibilidad |
| POST | `/api/v1/runs/{run_id}/cancel` | ANALISTA, ADMINISTRADOR | Cancela una corrida que sigue `encolado` |
| POST | `/api/v1/runs/{run_id}/retry` | ANALISTA, ADMINISTRADOR | Reintenta una corrida `fallido`: la regresa a `encolado` con la misma semilla y prioridad. Responde **202** |

Los roles son los de la pantalla Simulaciones del monolito; cancelar es `simulations.delete`
en la matriz de permisos (migración 010). CAPTURISTA recibe 403 en todas.

- `seed` es un entero de 0 a 2³¹−1; si no llega, se elige al azar.
- `replicas` es el tamaño del lote que el cliente está lanzando (D8): un entero de 1 a 100. Cada POST
  crea una sola corrida y el valor no cambia nada más: se valida el tope (D8) y se rechaza el que
  pasa de 100 (migración 036 baja el tope de la base de 200 a 100). Los lotes con varias réplicas
  llegan con la app de escritorio.
- `engine` es el motor: `seir-ref` si no llega. `abm-ref` y `abm-gpu` solo se aceptan si
  `MOTORES_HABILITADOS` los nombra, porque sin un `simulador` de ese motor la corrida se
  quedaría encolada para siempre; el compose trae los de `seir-ref` y `abm-ref`. Queda en
  `simulation_batches.engine`. `engine_version` sale del registro de motores
  (`procesamiento/motores.py`) al encolar; con un motor que no está implementado (`abm-gpu`)
  queda vacía.
- Los nombres de antes de D2 (`python-ref`, `numba` y `cuda`) se siguen aceptando en `engine`,
  en el filtro `engine` de la lista y en `MOTORES_HABILITADOS`, y se traducen a `seir-ref`,
  `abm-ref` y `abm-gpu`. Así un cliente de la v1 no se rompe; las respuestas usan los nombres
  nuevos.
- `forzar_error` solo cuenta si quien lo pide es ADMINISTRADOR; para otro rol se ignora, como
  en el monolito. La corrida termina en `fallido` y sirve para probar ese camino.
- `priority` es `baja`, `normal` (por omisión) o `alta` (D44, migración 054). Cada motor tiene una
  cola por prioridad (`queue:simulaciones:<motor>`, `:alta` y `:baja`) y el `simulador` toma primero
  las altas y luego las normales y las bajas, en orden de llegada dentro de cada una. Pedir `alta`
  es solo del ADMINISTRADOR: para otro rol es 403 `PERMISO_INSUFICIENTE`.
- `estimated_seconds` es la mediana de las últimas 50 corridas completadas con el mismo motor,
  población y horizonte (en una `ejecutando`, lo que falta; en una `encolado`, suponiendo que las
  de delante duran igual). `queue_position` es el lugar entre las encoladas de su motor (1 es la
  siguiente). Sin historial, o si la corrida ya terminó, `estimated_seconds` es `null` y
  `estimate_reason` dice por qué: no se inventa una cifra.
- Reintentar usa la transición condicionada `fallido` a `encolado` (mismo `run_id`, misma semilla,
  `attempts` en 0) y audita `RUN`; no crea otra corrida ni duplica la serie. Un segundo reintento,
  o uno sobre otro estado, es 409. Un ANALISTA que reintenta una corrida de prioridad `alta` la reencola en `normal`
  (solo el ADMINISTRADOR conserva `alta`). Si Redis no responde, la corrida ya está `encolado` en la
  base: se responde 202 y el `simulador` la encola al recuperarse (D19). Una `cancelado` no se reintenta.
- Mientras la corrida no termina, `progress` sale de Redis (`job:<id>:progress`, lo escribe el
  `simulador`); después, de PostgreSQL.
- Los filtros de la lista se combinan. `from` y `to` son días `AAAA-MM-DD` de cuando se encoló
  la corrida, en hora de Monterrey (`America/Monterrey`), los dos incluidos: una corrida de las
  21:00 del 20 de octubre sale con `from=2026-10-20`, aunque en UTC ya sea el 21. `engine`
  acepta los tres motores, habilitados o no; una corrida sin lote no tiene motor y no sale con
  ese filtro.

| Caso | Respuesta |
|------|-----------|
| Cuerpo, `limit` o un filtro inválidos, `from` posterior a `to`, o lanzar con un `engine` no habilitado, o `replicas` mayor que 100 | 422 `DATOS_INVALIDOS` |
| No existe la versión o la corrida | 404 `NO_ENCONTRADO` |
| Versión no aprobada, o ya se está lanzando una corrida de la misma versión | 409 `CONFLICTO` |
| Cancelar una corrida que ya empezó o terminó, o reintentar una que no está `fallido` | 409 `CONFLICTO` |
| Pedir `priority: alta` sin ser ADMINISTRADOR | 403 `PERMISO_INSUFICIENTE` |
| Redis caído | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

1. Toma el candado `lock:corrida:<version>` (10 s) para que un doble clic no lance dos
   corridas.
2. `datos.crear_corrida()` crea el lote y la corrida y audita el `RUN` en la misma
   transacción. La base vuelve a revisar que la versión esté aprobada (`fn_version_aprobada`).
3. Mete `{"id": ..., "forzar_error": ...}` en la cola de su motor,
   `queue:simulaciones:<engine>`, que solo lee el `simulador` de ese motor. Si Redis falla en
   ese momento, la corrida se cancela (`datos.cancelar_run()`), para que no quede encolada
   sin nadie que la corra, y responde 503.

Cancelar usa la misma transición condicionada que el `simulador` (`WHERE status =
'encolado'`), así que los dos no se pisan, y queda en la bitácora como `CANCEL`.

## Alcance y perfiles

INVESTIGADOR y AUTORIDAD_SANITARIA leen la lista, una corrida y su equivalente (D42); no lanzan, cancelan ni reintentan. Con alcance por región (D43), la lista solo trae las corridas de esas regiones y una corrida o versión de otra región da 403; el alcance se pide a `roles` (`GET /api/v1/scopes/me`, `SERVICIO_ROLES_URL`) con el token de la persona, y sin respuesta de `roles` dan 503. Una cuenta sin alcance es nacional. El alcance por institución no se aplica: el rol `svc_corridas` solo lee `users (id, username, full_name)`.

## Variables

`DATABASE_URL` (rol `svc_corridas`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL`; opcionales
`JWT_ISSUER`, `JWT_AUDIENCE` y `MOTORES_HABILITADOS` (los motores además de `seir-ref` que
tienen su `simulador` desplegado, separados por comas; en el compose, `abm-ref`).

## Probarlo

```bash
python -m pytest microservicios/corridas
python -m microservicios.corridas.app
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"scenario_version_id": 11}' "http://127.0.0.1:5241/api/v1/runs?format=json"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5241/api/v1/runs/42?format=json"
```
