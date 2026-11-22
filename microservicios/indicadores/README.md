# EPIDEMIA - Servicio indicadores

Indicadores del tablero y resumen de situación por enfermedad, los mismos del
dashboard del monolito. Solo lectura.

Puerto externo: 5251; puerto interno en Docker: 8000. Contrato en
`docs/contratos/indicadores/openapi.json`.

## Rutas

| Método | Ruta                             | Acceso  | Qué regresa |
|--------|----------------------------------|---------|-------------|
| GET    | `/api/v1/dashboard/indicators`   | Público | Casos activos, tasa de incidencia por 100k, zonas en riesgo y simulaciones activas, con su variación contra la semana previa; en `indicadores`, cada uno con su numerador, su denominador y su periodo, más mortalidad, letalidad y casos graves (ver abajo) |
| GET    | `/api/v1/dashboard/situation`    | Público | Casos de la última semana por enfermedad con su tendencia (`estable`, `alerta`, `critico`). `limit` de 1 a 20, por omisión 5 |

Públicas porque el tablero del monolito se ve sin iniciar sesión (`/`).
Usa `get_resumen_indicadores()` y `get_resumen_situacion()` de `consultas.py`: la copia de las
del monolito, que la web todavía lee (D36). La regla es de este servicio y las dos deben ser
iguales mientras existan (`test_copias_del_monolito.py`, E8).

## Cada indicador con su cuenta (F7)

`indicadores` (`definidos.py`, una sola consulta con `epidemia_comun.bd`) explica las mismas
cuentas de los campos de siempre, que la web sigue leyendo igual:

| `clave` | `valor` | Numerador | Denominador | `factor` |
|---|---|---|---|---|
| `casos_activos` | Casos de la semana | Casos reportados | — | — |
| `tasa_incidencia` | Por 100 000 habitantes | Casos reportados | Habitantes de Nuevo León | 100 000 |
| `tasa_mortalidad` | Por 100 000 habitantes (2 decimales) | Casos con gravedad `fallecido` | Habitantes de Nuevo León | 100 000 |
| `letalidad` | % de los casos | Casos con gravedad `fallecido` | Casos reportados | 100 |
| `casos_graves` | % de los casos | Casos con gravedad `grave` | Casos reportados | 100 |
| `zonas_en_riesgo` | Municipios | Municipios con más de 10 casos por 100 000 en la semana | Municipios de Nuevo León (referencia) | — |
| `simulaciones_activas` | Corridas | Encoladas o ejecutándose ahora | — | — |

- Los casos son los `pendiente` o `validado`, por fecha de reporte, en los municipios de Nuevo
  León. `periodo` es la semana: hoy y los 6 días previos. `previo` es la semana anterior, con
  su `valor` y su numerador, y `variacion_pct` se calcula como `casos_pct` y `tasa_pct`, así que
  coinciden. Las proporciones (`letalidad`, `casos_graves`) solo traen la semana actual.
- Con `factor`, valor = numerador / denominador × factor; sin él, valor = numerador. Lo que
  dividiría entre cero es `null`.
- No hay prevalencia (los casos no tienen fecha de recuperación), ni hospitalizaciones (no hay
  ese dato: `casos_graves` es lo más cercano), ni capacidad utilizada (no hay fuente, RF-G07).

## Caché

`cache:indicadores:indicators` y `cache:indicadores:situation:limit=<n>`, con
TTL de 60 s (`epidemia_comun.cache`). Si Redis está caído, responde directo
de PostgreSQL y la caché se vuelve a llenar sola cuando Redis regresa.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/indicadores -q
python -m microservicios.indicadores.app
curl "http://127.0.0.1:5251/api/v1/dashboard/indicators?format=json"
curl "http://127.0.0.1:5251/api/v1/dashboard/situation?limit=3"
```

Corre en `infra/docker-compose.yml`.
