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
| GET    | `/api/v1/comparisons` | `aviso` y `corridas`: por cada una, su escenario y versión, fallecimientos, pico de casos activos, día del pico, tasa de ataque y `serie` (un punto por día) |

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

En XML, cada día de la serie es un `<punto>`.

Por cada corrida pide `GET /api/v1/runs/{id}/results` a `resultados` (hasta 8 a la vez, 5 s de
espera), con el token y el `X-Correlation-ID` de la petición; así aprovecha su caché de
300 s. El indicador sale del `resumen` y la serie, de `serie`. La
comparación de costo contra impacto y la frontera de Pareto son del servicio
`pareto`; la lista de corridas para elegir es de `corridas`.

## Variables

`SERVICIO_RESULTADOS_URL` (en el compose, `http://resultados:8000`), `JWT_SECRET_KEY`,
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
