# EPIDEMIA - Servicio corridas

Lanza, consulta y cancela corridas de simulación. Lanzar crea el lote y la corrida en
PostgreSQL (`encolado`) y la mete en la cola de Redis de su motor; la ejecuta el `simulador`
de ese motor. Solo se simula una versión aprobada.

Puerto externo: 5241; puerto interno en Docker: 8000. Contrato en
`docs/contratos/corridas/openapi.json`, con un ejemplo JSON y uno XML por ruta en
`ejemplos/`.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/runs` | ANALISTA, ADMINISTRADOR | Cuerpo `{scenario_version_id, seed?, engine?, forzar_error?}`. Responde **202** con `id`, `batch_id`, `seed`, `engine` y `status: encolado` |
| GET | `/api/v1/runs?limit=20` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Las corridas más recientes, con su `engine` (`limit` de 1 a 100) |
| GET | `/api/v1/runs/{run_id}` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Estado, `progress`, `engine` y `terminal` |
| POST | `/api/v1/runs/{run_id}/cancel` | ANALISTA, ADMINISTRADOR | Cancela una corrida que sigue `encolado` |

Los roles son los de la pantalla Simulaciones del monolito; cancelar es `simulations.delete`
en la matriz de permisos (migración 010). CAPTURISTA recibe 403 en todas.

- `seed` es un entero de 0 a 2³¹−1; si no llega, se elige al azar.
- `engine` es el motor: `python-ref` si no llega. `numba` y `cuda` solo se aceptan si
  `MOTORES_HABILITADOS` los nombra, porque sin un `simulador` de ese motor la corrida se
  quedaría encolada para siempre; hoy solo existe el de `python-ref`. Queda en
  `simulation_batches.engine`. `engine_version` sale de `python-ref` al encolar; con otro motor
  queda vacía, porque este servicio no la conoce.
- `forzar_error` solo cuenta si quien lo pide es ADMINISTRADOR; para otro rol se ignora, como
  en el monolito. La corrida termina en `fallido` y sirve para probar ese camino.
- Mientras la corrida no termina, `progress` sale de Redis (`job:<id>:progress`, lo escribe el
  `simulador`); después, de PostgreSQL.

| Caso | Respuesta |
|------|-----------|
| Cuerpo o `limit` inválidos, o un `engine` no habilitado | 422 `DATOS_INVALIDOS` |
| No existe la versión o la corrida | 404 `NO_ENCONTRADO` |
| Versión no aprobada, o ya se está lanzando una corrida de la misma versión | 409 `CONFLICTO` |
| Cancelar una corrida que ya empezó o terminó | 409 `CONFLICTO` |
| Redis caído | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

1. Toma el candado `lock:corrida:<version>` (10 s) para que un doble clic no lance dos
   corridas.
2. `queries.crear_corrida()` crea el lote y la corrida y audita el `RUN` en la misma
   transacción. La base vuelve a revisar que la versión esté aprobada (`fn_version_aprobada`).
3. Mete `{"id": ..., "forzar_error": ...}` en la cola de su motor,
   `queue:simulaciones:<engine>`, que solo lee el `simulador` de ese motor. Si Redis falla en
   ese momento, la corrida se cancela (`queries.cancelar_run()`), para que no quede encolada
   sin nadie que la corra, y responde 503.

Cancelar usa la misma transición condicionada que el `simulador` (`WHERE status =
'encolado'`), así que los dos no se pisan, y queda en la bitácora como `CANCEL`.

## Variables

`DATABASE_URL` (rol `svc_corridas`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL`; opcionales
`JWT_ISSUER`, `JWT_AUDIENCE` y `MOTORES_HABILITADOS` (los motores además de `python-ref` que
tienen su `simulador` desplegado, separados por comas; por ejemplo `cuda`).

## Probarlo

```bash
python -m pytest microservicios/corridas
python -m microservicios.corridas.app
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"scenario_version_id": 11}' "http://127.0.0.1:5241/api/v1/runs?format=json"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5241/api/v1/runs/42?format=json"
```
