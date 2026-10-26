# EPIDEMIA - Servicio comparacion

Compara corridas completadas lado a lado: los indicadores de cada una y su serie
diaria, para la tabla comparativa y las curvas superpuestas. Solo lectura. Muestra
opciones; no recomienda un escenario.

Puerto externo: 5244; puerto interno en Docker: 8000. Contrato en
`docs/contratos/comparacion/openapi.json`.

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

En XML, cada día de la serie es un `<punto>`.

La consulta es la del monolito, `queries.get_corridas_para_comparar()`. La
comparación de costo contra impacto y la frontera de Pareto son del servicio
`pareto`; la lista de corridas para elegir es de `corridas`.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `REDIS_URL`; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/comparacion
python -m microservicios.comparacion.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5244/api/v1/comparisons?runs=12,15&format=json"
```

La base de la demostración tiene corridas completadas pero sin resultados guardados,
así que ahí la comparación responde 404. Para probarla con datos, ejecuta antes
algunas corridas.

Pendiente: su rol de PostgreSQL (migración) y la entrada en el compose (bloque J).
