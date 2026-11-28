# EPIDEMIA - Servicio comparacion

Compara corridas completadas lado a lado: los indicadores de cada una y su serie
diaria, para la tabla comparativa y las curvas superpuestas. Solo lectura. Muestra
opciones; no recomienda un escenario. Los resultados se los pide al servicio `resultados`.

Puerto externo: 5244; puerto interno en Docker: 8000. Contrato en
`docs/contratos/comparacion/openapi.json`. Su respuesta XML valida contra
`docs/contratos/comparacion/comparacion.xsd`.

## Ruta

| Método | Ruta                  | Qué regresa |
|--------|-----------------------|-------------|
| GET    | `/api/v1/comparisons` | `aviso` y `corridas`: por cada una, su escenario y versión, fallecimientos, pico de casos activos, día del pico, tasa de ataque y `serie` (un punto por día); más `base_id`, `diferencias`, `incertidumbre` y, si se pide, `contrafactual` |

Pide `Authorization: Bearer` de ANALISTA, EPIDEMIOLOGO o ADMINISTRADOR, los
mismos roles que la pantalla Comparación del monolito. CAPTURISTA recibe 403.

`runs`: los ids de 2 a 50 corridas, separados por comas (`runs=12,15`). Se
regresan en el orden pedido y sin repetidas.

| Caso | Respuesta |
|------|-----------|
| Falta `runs`, un id no es entero positivo, menos de dos distintas o más de 50 | 422 `DATOS_INVALIDOS` |
| Alguna no existe, no ha terminado o no tiene resultado guardado | 404 `NO_ENCONTRADO`, con sus ids en `detail` |
| `resultados` no responde, responde 5xx o algo ilegible | 503 `SERVICIO_NO_DISPONIBLE` |
| `resultados` rechaza la identidad | 401 o 403, el mismo código |

`base` (opcional): la corrida de referencia de las diferencias; una de `runs`, por omisión la primera.
`sin_intervencion` (opcional): una de `runs`; activa el contrafactual. Una que no esté en `runs`
es 422 `DATOS_INVALIDOS`.

- **`diferencias`:** cada corrida contra la base, en tasa de ataque, pico de casos activos, día del
  pico, fallecimientos y, si `pareto` los entrega, costo en personas-día y en pesos (D3). `absoluta`
  es la corrida menos la base; `relativa`, esa resta entre la base (nula si la base es cero). Si
  `pareto` no responde o se niega (falta un costo o su fuente, regla 8), `costos_disponibles` es
  `false`, `costos_motivo` dice por qué y las demás métricas siguen.
- **`incertidumbre`:** por cada versión y motor (`engine_version` de la corrida) con réplicas (2 o más), pide la banda p5 a p95 de los casos
  activos a `resultados` (`/band`); trae `banda`, el `pico` (día de mayor mediana) y `replicas`.
  `sin_replicas` lista las corridas sin banda (una sola réplica, o sin serie) y `bandas_encimadas`
  los pares cuyos intervalos p5 a p95 en el pico se cruzan (D8); dos corridas de la misma versión y motor comparten banda y no se comparan entre sí, pero sí con otro motor (seir-ref contra abm-ref). No oculta nada: con réplicas, la
  diferencia entre dos corridas sueltas no es la diferencia entre escenarios.
- **`contrafactual`:** solo con `sin_intervencion`. Compara cada corrida con la indicada, usando
  únicamente las corridas que pasaste; `exploratorio` es `true` y `mismo_escenario` avisa si no
  comparten escenario. No estima lo que habría pasado en la realidad ni recomienda un escenario.

En XML, cada día de la serie es un `<punto>`.

Por cada corrida pide `GET /api/v1/runs/{id}/results` a `resultados`, y una vez por versión su `.../band`; los costos, con un solo `GET /api/v1/pareto?runs=` a `pareto` (con la misma identidad). Los resultados (hasta 8 a la vez, 5 s de
espera), con el token y el `X-Correlation-ID` de la petición; así aprovecha su caché de
300 s. El indicador sale del `resumen` y la serie, de `serie`. La
comparación de costo contra impacto y la frontera de Pareto son del servicio
`pareto`; la lista de corridas para elegir es de `corridas`.

## Perfiles y alcance

INVESTIGADOR y AUTORIDAD_SANITARIA leen (D42). Comparacion no tiene datos propios: reenvía el token de la persona a `resultados` y `pareto`, que aplican el alcance por región (D43), y su 403 sube tal cual. Nunca importó `backend_web`.

## Variables

`SERVICIO_RESULTADOS_URL` (en el compose, `http://resultados:8000`), `SERVICIO_PARETO_URL` (`http://pareto:8000`; sin ella no hay costos), `JWT_SECRET_KEY`,
`REDIS_URL`; `DATABASE_URL` ya no se consulta, pero el arranque la sigue pidiendo; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/comparacion
python -m microservicios.comparacion.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5244/api/v1/comparisons?runs=12,15&format=json"
```

Necesita `resultados` levantado (perfil `simulacion`) y corridas completadas con resultado.

Su rol de PostgreSQL lo crea la migración 028 y corre en `infra/docker-compose.yml`.
