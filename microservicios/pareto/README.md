# EPIDEMIA - Servicio pareto

Costo contra impacto de varias corridas completadas y su frontera de Pareto. Solo
lectura. Muestra opciones y costos; no recomienda un escenario.

Puerto externo: 5245; puerto interno en Docker: 8000. Contrato en
`docs/contratos/pareto/openapi.json`. Su respuesta XML valida contra
`docs/contratos/pareto/pareto.xsd`.

## Ruta

| Método | Ruta             | Qué regresa |
|--------|------------------|-------------|
| GET    | `/api/v1/pareto` | `aviso` y la comparación: por cada corrida (`filas`), su costo con el desglose por intervención, su impacto, si otra la domina (`dominado_por`) y, contra la `base`, el impacto evitado y el costo por unidad evitada. `frontera` son las corridas no dominadas; `trazabilidad_costos`, de dónde sale cada costo unitario |

Pide `Authorization: Bearer` de ANALISTA, EPIDEMIOLOGO o ADMINISTRADOR, los
mismos roles que la pantalla Comparación del monolito, donde vive este cálculo.
CAPTURISTA recibe 403.

- `runs`: los ids de 2 a 50 corridas, separados por comas (`runs=12,15`), en el
  orden pedido y sin repetidas.
- `metric` (opcional): eje de impacto. `fallecimientos` (por omisión),
  `hospitalizaciones`, `casos_acumulados`, `pico_casos_activos` o
  `pico_hospitalizados`.

Todo lo que impide comparar es 422 `DATOS_INVALIDOS`, con los motivos del monolito
en `detail`: `runs` o `metric` inválidos, una corrida que no existe o no ha
terminado, sin resultado guardado, o cuya versión ya no se puede simular.

`base` es la corrida de referencia que elige el motor; si ninguna es "sin
intervención", es `null`.

En XML, cada fila es `<fila>`; los ids de `frontera` y `dominado_por`, `<corrida>`;
el desglose, `<intervencion>`, y la trazabilidad, `<costo>`.

## De dónde salen los datos

Reusa `simulaciones.construir_comparacion_costo_impacto()` del monolito: arma el
escenario de cada versión, lee los costos de `intervention_types` y el resultado
guardado de cada corrida, y llama a `comparar()` del motor. Lee la base directo y no
llama a `resultados`, que todavía no existe (ver la nota en
`docs/arquitectura/microservicios.md`).

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `REDIS_URL`; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
python -m pytest microservicios/pareto
python -m microservicios.pareto.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5245/api/v1/pareto?runs=12,15&format=json"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5245/api/v1/pareto?runs=12,15&metric=hospitalizaciones"
```

Como en `comparacion`, la base de la demostración no tiene resultados guardados:
para probarlo con datos, ejecuta antes algunas corridas.

Pendiente: su rol de PostgreSQL (migración 027) y la entrada en el compose (bloque J).
