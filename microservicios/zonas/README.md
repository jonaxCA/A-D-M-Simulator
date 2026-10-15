# EPIDEMIA - Servicio zonas

Detalle por zona (tabla de Monitoreo) y datos del mapa por municipio de Nuevo
León. Solo lectura.

Puerto externo: 5253; puerto interno en Docker: 8000. Contrato en
`docs/contratos/zonas/openapi.json`.

## Rutas

Las dos piden `Authorization: Bearer` de cualquier rol con sesión activa,
igual que Monitoreo y Mapa en el monolito.

| Método | Ruta                 | Qué regresa |
|--------|----------------------|-------------|
| GET    | `/api/v1/zones`      | Una fila por municipio: casos, incidencia, variación a 7 días, graves y semáforo (`estado`). Con paginación y `mayor_cambio` |
| GET    | `/api/v1/zones/map`  | Municipios con incidencia, nivel del semáforo (`nivel`) y tendencia de 14 días, más la serie acumulada día por día para la línea de tiempo |

Filtros de `/api/v1/zones`: `disease_id`, `region_id`, `days` (7, 30 o 90),
`q` (nombre del municipio), `order` (`casos` o `incidencia`, por omisión
`incidencia`), `page` y `size` (máximo 100).

Filtros de `/api/v1/zones/map`: `disease_id` y `days` (7, 30 o 60, los del mapa).

### `mayor_cambio` (LIMP-20)

Se calcula sobre **todas** las zonas del ámbito, en el orden fijo de la
consulta, nunca sobre la página, la búsqueda ni el orden elegido. Con un empate
gana la primera. Regresa datos, no texto:

- `{"estado": "con_aumento", "zona": {"id", "zona", "variacion"}}`
- `{"estado": "sin_aumento", "zona": null}`: ninguna zona aumentó.
- `{"estado": "sin_casos", "zona": null}`: no hay casos en el periodo.

### Serie del mapa

`get_mapa_serie_temporal()` indexa la serie por clave INEGI (`"19039"`), que
no sirve como etiqueta XML. El servicio la regresa como lista en
`serie.municipios`, cada elemento con su `region_code`.

## Caché

`cache:zonas:zones:...`, `cache:zonas:zones-all:...` y `cache:zonas:map:...`,
TTL de 60 s. Sin caché, el mapa hace más de 50 consultas (una por municipio para
la tendencia), así que la caché importa aquí.

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY`, `REDIS_URL`; opcionales `JWT_ISSUER` y
`JWT_AUDIENCE`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/zonas -q
python -m microservicios.zonas.app
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5253/api/v1/zones?size=5&format=json"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5253/api/v1/zones/map?days=7"
```

Pendiente: la entrada en el compose (bloque J). Evidencia de funcionamiento en `evidencias/servicios/zonas/`.
