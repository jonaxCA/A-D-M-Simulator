# EPIDEMIA - Servicio resultados

Curvas e indicadores de una corrida completada, tal como los guardó el `simulador`: el
resumen, la huella y la trazabilidad en `simulation_runs` (migración 038) y la serie diaria en
MongoDB (`series_corridas`, D28). Solo lectura. Cada respuesta lleva el aviso de que los resultados no son una predicción
(`AVISO_SIMULACION`).

Puerto externo: 5243; puerto interno en Docker: 8000. Contrato en
`docs/contratos/resultados/openapi.json`. El XML de `/results` valida contra
`docs/contratos/resultados/resultado.xsd`.

## Rutas

| Método | Ruta | Qué regresa |
|--------|------|-------------|
| GET | `/api/v1/runs/{run_id}/results` | `aviso`, `simplificaciones` del modelo, `corrida` (escenario, versión, semilla, población, horizonte), `engine_version`, `scenario_checksum`, `resumen`, `serie`, `trazabilidad` de los parámetros y `escala` (D6: cuántos habitantes de la región representa cada agente, y los conteos del resumen llevados a habitantes) |
| GET | `/api/v1/runs/{run_id}/curves` | `aviso`, `run_id` y `serie`: un punto por día |
| GET | `/api/v1/runs/{run_id}/indicators` | `aviso`, `run_id` y `resumen`, con el desglose por grupo de edad |
| GET | `/api/v1/runs/{run_id}/band?campo=casos_activos` | `aviso`, `categoria`, `scenario_version_id`, `motor`, `campo`, `replicas` y `banda`: por día, `corridas`, `p5`, `p50` (mediana) y `p95` entre las réplicas completadas de la versión con el mismo motor (D8) |

Las cuatro piden ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR, INVESTIGADOR o AUTORIDAD_SANITARIA (D42; los dos últimos solo leen). CAPTURISTA recibe 403. Con alcance por región (D43) una corrida de otra región da 403: se revisa en cada petición, fuera de la caché (que es de todos), con lo que `roles` responde a `GET /api/v1/scopes/me` (`SERVICIO_ROLES_URL`). Sin alcance la cuenta es nacional; el alcance por institución no se aplica (el rol `svc_resultados` no lee `users.institution_id`). La serie la lee `serie.py`; la escribe `simulador/serie.py`, y el formato es el contrato `docs/contratos/series_corridas/`.

| Caso | Respuesta |
|------|-----------|
| Id inválido | 422 `DATOS_INVALIDOS` |
| No existe la corrida o no tiene resultado guardado | 404 `NO_ENCONTRADO` |
| La corrida está completada, pero su serie no está en MongoDB (el simulador la reintenta) | 404 `NO_ENCONTRADO` en `/results` y `/curves` |
| MongoDB no responde | 503 `SERVICIO_NO_DISPONIBLE` en `/results`, `/curves` y `/band`; `/indicators` sigue, porque solo lee PostgreSQL |
| `campo` de `/band` que no es un compartimento ni un total diario de la serie | 422 `DATOS_INVALIDOS` |
| La versión no tiene series en MongoDB, o no se reconoce el motor | 404 `NO_ENCONTRADO` en `/band` |
| La corrida no está completada | 409 `CONFLICTO`, con su estado en `detail` |

`/band` usa `series_corridas.banda()`, que agrupa por día los documentos de la versión y el motor de la corrida, limitados a las corridas completadas según PostgreSQL (D38) **y que tienen su serie en MongoDB** (`series_corridas.con_serie()`): `replicas` cuenta solo las corridas que entran en la banda, no todas las completadas de la versión. Con una sola réplica la banda es la propia curva y `replicas` vale 1: el cliente decide si avisa. `categoria` es la de D39.

En XML, cada día de la serie (y de la banda) es un `<punto>`, cada grupo de edad un `<grupo_edad>` y cada
parámetro de la trazabilidad un `<parametro>`.

## Caché

El resultado de una corrida completada ya no cambia: se guarda 300 s. Lo de PostgreSQL va en
`cache:resultados:run=<id>`, que comparten las tres rutas, y la serie en
`cache:resultados:serie=<id>`, que comparten `/results` y `/curves`. La banda va en `cache:resultados:banda=<versión>&<motor>&<campo>&n=<réplicas con serie>&m=<última>`: al completarse otra réplica la llave cambia. Lo que no está completado
no entra a la caché, ni una serie que todavía no llega a MongoDB. Si Redis se cae, las rutas responden 503 porque el token no se puede
verificar.

## Variables

`DATABASE_URL` (rol `svc_resultados`, migración 029), `JWT_SECRET_KEY`, `REDIS_URL`,
`MONGO_URL`; opcionales `JWT_ISSUER`, `JWT_AUDIENCE` y `MONGO_TIMEOUT_MS`.

## Probarlo

```bash
python -m pytest microservicios/resultados
python -m microservicios.resultados.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5243/api/v1/runs/42/indicators?format=json"
```
