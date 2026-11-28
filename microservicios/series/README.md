# EPIDEMIA - Servicio series

Curva epidémica y series por edad, sexo y totales, con los filtros de la
pantalla de Monitoreo del monolito, y una serie con rango libre, agregación por día, semana
epidemiológica o mes, grupos, paginación y salida para Highcharts (F7). Solo lectura.

Puerto externo: 5252; puerto interno en Docker: 8000. Contrato en
`docs/contratos/series/openapi.json`.

## Rutas

Todas piden `Authorization: Bearer` de cualquier rol con sesión activa, igual
que Monitoreo en el monolito.

| Método | Ruta                            | Qué regresa |
|--------|---------------------------------|-------------|
| GET    | `/api/v1/series/cases`          | Casos por día e incidencia acumulada por 100k |
| GET    | `/api/v1/series/cases/by-age`   | Los seis grupos de edad en orden, aunque alguno venga en cero |
| GET    | `/api/v1/series/cases/by-sex`   | Casos y porcentaje por sexo |
| GET    | `/api/v1/series/cases/totals`   | Casos e incidencia del periodo contra el periodo previo |
| GET    | `/api/v1/series/cases/aggregate` | Casos por periodo, con rango libre, agregación, grupos y paginación (ver abajo) |
| GET    | `/api/v1/series/cases/highcharts` | La misma serie, sin paginar, como `{xAxis, yAxis, series}` de Highcharts |

Filtros comunes (`epidemia_comun.ambito`):

- `disease_id`: enfermedad; 404 si no existe.
- `region_id`: municipio de Nuevo León; 404 si no existe. Sin él, todo el estado.
- `days`: 7, 30 o 90, por omisión 30. Otro valor es 422.

Cada respuesta repite los filtros aplicados en `filtros`.

## Serie agregada y Highcharts (F7)

`agregadas.py`, con su propia consulta (`epidemia_comun.bd`, sin `backend_web`). Además de
`disease_id` y `region_id`:

| Parámetro | Valores | Por omisión |
|---|---|---|
| `from`, `to` | Fechas `AAAA-MM-DD`; hasta 731 días | Los 90 días que terminan hoy (fecha de la base) |
| `days` | 7, 30 o 90, en lugar de `from` y `to` (los dos juntos es 422) | — |
| `interval` | `dia`, `semana` o `mes` | `dia` |
| `group_by` | `sexo`, `edad`, `enfermedad` o `municipio` | sin grupos |
| `page`, `size` | Solo en `aggregate`; `size` de 1 a 366 | 1 y 52 |

- **Periodos sin huecos:** cada día, semana o mes del rango sale aunque tenga 0 casos.
  `completo` es falso en el primero o el último si el rango los corta.
- **Semana epidemiológica:** de domingo a sábado; la semana 1 es la primera con al menos cuatro
  días del año, como en el SINAVE. Va en `semana_epi` (`2026-47`).
- **Grupos:** `grupos` da el orden (por casos; la edad, siempre sus seis grupos) y cada periodo
  trae `por_grupo` en ese orden. Sexo y edad sin dato son «No especificado».
- **Paginación:** por periodos. `total` es cuántos hay, `paginas` cuántas páginas y
  `total_casos` la suma de todo el rango, no solo de la página.
- **Highcharts:** una serie por grupo (o «Casos») con puntos `{x, y}`, donde x es el inicio del
  periodo en milisegundos UTC: `Highcharts.chart(contenedor, respuesta)` la dibuja tal cual.
- Las dos rutas comparten la caché (`cache:series:aggregate:<filtros>`, 60 s); la página se
  corta después.

## Caché

`cache:series:<ruta>:d=<enfermedad>:r=<municipio>:dias=<n>`, TTL de 60 s. Con
Redis caído, la verificación del token responde 503: es una ruta protegida y
nunca deja pasar.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `REDIS_URL`; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/series -q
python -m microservicios.series.app
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:5252/api/v1/series/cases?days=7&format=json"
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:5252/api/v1/series/cases/aggregate?from=2026-01-01&to=2026-06-30&interval=semana&group_by=sexo&format=json"
```

Corre en `infra/docker-compose.yml`.
