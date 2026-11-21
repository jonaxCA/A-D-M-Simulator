# EPIDEMIA - Servicio pareto

Costo contra impacto de varias corridas completadas y su frontera de Pareto, con la
explicación de por qué cada una queda dominada o no; además, la sensibilidad exploratoria
de un parámetro y el estado de calibración de los modelos (D46). Solo lectura. Muestra opciones y costos; no recomienda un escenario.

Puerto externo: 5245; puerto interno en Docker: 8000. Contrato en
`docs/contratos/pareto/openapi.json`. Su respuesta XML valida contra
`docs/contratos/pareto/pareto.xsd`.

## Rutas

| Método | Ruta             | Qué regresa |
|--------|------------------|-------------|
| GET    | `/api/v1/pareto/sensitivity` | Sensibilidad de un factor a la vez (ver abajo) |
| GET    | `/api/v1/pareto/calibration` | Estado de calibración de cada versión de motor (ver abajo) |
| GET    | `/api/v1/pareto` | `aviso` y la comparación: por cada corrida (`filas`), su costo en personas-día (`costo`, el eje de la frontera) y en pesos (`costo_pesos`, aparte y nulo si falta un costo unitario), con el desglose por intervención, su impacto y si otra la domina (`dominado_por`). `frontera` son las corridas no dominadas; `trazabilidad_costos`, de dónde sale cada costo unitario y el factor de personas-día por dosis (D3) |

Las tres rutas piden `Authorization: Bearer` de ANALISTA, EPIDEMIOLOGO o ADMINISTRADOR, los
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

`base` llega siempre en `null`: el servicio no pide una corrida de referencia, así que
las filas no traen `impacto_evitado`, `costo_adicional` ni `costo_por_unidad_evitada`.
El motor los calcula solo cuando se le da una base (`comparar(..., base=...)`), como
hace `python -m procesamiento.motor`.

Cada fila trae `explicacion` (solo describe; no recomienda, regla 10):
- `dominado` y `dominada_por`: por cada alternativa que la domina, su `costo` e `impacto`,
  `diferencia_costo` (personas-día que cuesta menos) y `diferencia_impacto` (cuánto menos
  impacto tiene), y `criterios`, los criterios en que es estrictamente menor.
- `compromisos`: las alternativas que son menores en un solo criterio (`mejor_en`: `costo`
  o `impacto`, con su `diferencia`). Es lo que explica por qué una fila está en la frontera.
- `empatada_con`: ids con el mismo costo e impacto (no se dominan entre sí).
- `texto`: lo mismo en una o dos frases en español.

En XML, cada fila es `<fila>`; los ids de `frontera` y `dominado_por`, `<corrida>`;
el desglose, `<intervencion>`, y la trazabilidad, `<costo>`.

## Sensibilidad

`GET /api/v1/pareto/sensitivity?version=7&parameter=r0&percent=-20,20&metric=fallecimientos`

Análisis exploratorio de un factor a la vez (D46). `version`: versión de escenario
aprobada (404 si no existe, 422 si no está aprobada). `parameter`: `r0`, `incubacion_dias`,
`infeccioso_dias` o `dias_hospitalizacion`. `values` (valores absolutos) o `percent` (cambio
porcentual sobre el valor de la versión), solo uno, de 1 a 9 valores mayores que 0.
`metric`: como en `pareto`. Corre `seir-ref` en el proceso, con las semillas 1 a 5 por valor,
sin crear corridas ni escribir datos (no hay bitácora). Regresa, ordenados por valor, la
media, el mínimo y el máximo de la métrica, el cambio respecto de la base (la fila con
`es_base`, que siempre se incluye) y la `categoria` de D39, siempre `exploratoria`. Los valores
probados son supuestos del análisis. Cuerpo en `sensibilidad`; la lógica, en
`procesamiento/analitica/sensibilidad.py`.

## Calibración

`GET /api/v1/pareto/calibration?engine=seir-ref-0.1&disease=1&region=2` (todo opcional)

Lee `procesamiento/estado_validacion.json`: por versión de motor, `estado`
(`sin_calibrar`, `calibrado` o `validado`), `verificado`, `categoria` D39 con su `motivo` y
`texto`, y la evidencia. `disponible: false` y `ejecucion: no_disponible`: D24 está reabierta
y el método lo decide el bloque 0, así que no hay ruta para calibrar (un POST da 405). Hoy
todo es `sin_calibrar` y `exploratoria`.

## De dónde salen los datos

`dominio.construir_comparacion_costo_impacto()` (E8: ya no importa `backend_web`; el SQL está en `datos.py` y la traducción versión → entrada del motor, en `procesamiento/entrada_motor.py`) arma el
escenario de cada versión, lee los costos y el factor de personas-día por dosis de
`intervention_types` (migración 040) y el resultado guardado de cada corrida, y llama a
`comparar()` de `procesamiento.analitica`. Sin factor, una corrida con vacunación da 422. Lee la base directo con su rol y no
llama a `resultados`.

## Alcance y perfiles

INVESTIGADOR y AUTORIDAD_SANITARIA leen (D42). Con alcance por región (D43), `GET /pareto` da 403
si alguna corrida es de otra región y `/pareto/sensitivity` si lo es la versión; se pide a
`roles` (`GET /api/v1/scopes/me`, `SERVICIO_ROLES_URL`) con el token de la persona. Una cuenta sin
alcance es nacional. El alcance por institución no se aplica: el rol `svc_pareto` solo lee
`users (id, username, full_name)`, así que no ve la institución de quien pidió la corrida.

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

Su rol de PostgreSQL lo crea la migración 028 y corre en `infra/docker-compose.yml`.
