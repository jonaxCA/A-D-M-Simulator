# EPIDEMIA - Servicio zonas

Detalle por zona (tabla de Monitoreo), datos del mapa por municipio de Nuevo
León, puntos agregados para un mapa de calor, casos por jurisdicción sanitaria y la geometría
oficial de los municipios, con la ubicación de un punto (F7). Solo lectura.

Puerto externo: 5253; puerto interno en Docker: 8000. Contrato en
`docs/contratos/zonas/openapi.json`.

## Rutas

Las dos piden `Authorization: Bearer` de cualquier rol con sesión activa,
igual que Monitoreo y Mapa en el monolito.

| Método | Ruta                 | Qué regresa |
|--------|----------------------|-------------|
| GET    | `/api/v1/zones`      | Una fila por municipio: casos, incidencia, variación a 7 días, graves y semáforo (`estado`). Con paginación y `mayor_cambio`. Con alcance por región (D43), solo sus municipios; uno ajeno en `region_id` es 403 |
| GET    | `/api/v1/zones/map`  | Municipios con incidencia, nivel del semáforo (`nivel`) y tendencia de 14 días, más la serie acumulada día por día para la línea de tiempo |
| GET    | `/api/v1/zones/heatmap` | Los casos con coordenadas, agregados en celdas, para un mapa de calor (ver abajo) |
| GET    | `/api/v1/zones/jurisdictions` | Las cifras de `/zones` sumadas por jurisdicción sanitaria (ver abajo) |
| GET    | `/api/v1/zones/geometry` | Los 51 municipios como GeoJSON, tal cual, con su ETag (ver abajo) |
| GET    | `/api/v1/zones/locate` | En qué municipio y jurisdicción cae un punto (`lat`, `lon`) |

Filtros de `/api/v1/zones`: `disease_id`, `region_id`, `days` (7, 30 o 90),
`q` (nombre del municipio), `order` (`casos` o `incidencia`, por omisión
`incidencia`), `page` y `size` (máximo 100).

Filtros de `/api/v1/zones/map`: `disease_id` y `days` (7, 30 o 60, los del mapa).

Filtros de `/api/v1/zones/heatmap`: `disease_id`, `region_id`, `days` (7, 30, 60 o 90) y
`cell` (0.01, 0.02 o 0.05 grados; por omisión 0.01).

### Mapa de calor (F7)

`calor.py`, con su propia consulta (`epidemia_comun.bd`, sin `backend_web`). Cada caso trae la
latitud y la longitud de donde se capturó; publicarlas tal cual ubicaría a una persona, así que:

- Salen agregadas en una cuadrícula de `cell` grados: 0.01 son unos 1.1 km en Nuevo León, y
  no hay celda más fina.
- Una celda con menos de 3 casos no se publica; se cuenta en `casos_suprimidos` y
  `celdas_suprimidas`.
- Cada punto trae el centro de su celda (`lat`, `lon`), `casos` y `peso` (de 0 a 1, contra la
  celda con más), para la intensidad de Leaflet.heat o el color de Highcharts.
- `total_casos` = `casos_en_puntos` + `casos_suprimidos` + `casos_sin_coordenadas`.

### Por jurisdicción sanitaria (F7)

`jurisdicciones.py`; filtros `disease_id` y `days` (7, 30 o 90). Cada grupo trae `poblacion`,
`casos`, `graves`, `incidencia`, `variacion` a 7 días y `estado` (el semáforo de `/zones`),
con sus `municipios` y los `numeros` de jurisdicción.

- Qué municipios tiene cada jurisdicción sale de `datos/geo/nl_jurisdicciones_sanitarias.json`.
  Lo genera `datos/scripts/build_jurisdicciones.py` desde el artículo 27 del Reglamento
  Interior de Servicios de Salud de Nuevo León (P.O. 12/10/2004, última reforma 4/03/2009). La
  imagen lo copia (`Dockerfile` y la excepción en `.dockerignore`).
- **Pendiente de confirmar** con la Secretaría de Salud que esa división siga vigente.
- **Monterrey** se reparte entre las jurisdicciones 1 (poniente), 2 (norte y oriente) y 3
  (sur). Con casos por municipio no se puede partir, así que va primero como su propio grupo
  (`compartido-19039`), y la 2 y la 3 llevan solo sus otros municipios. Por eso salen 8 grupos:
  Monterrey y las jurisdicciones 2 a 8.

### Geometría oficial y ubicar un punto (F7)

`geometria.py`. La geometría es `datos/geo/nl_municipios.geojson`: la capa municipal del Marco
Geoestadístico 2024 de INEGI, reproyectada a lon/lat y simplificada a 0.0012 grados (unos 130 m)
por `datos/scripts/build_municipios_inegi.py`, el mismo script que hace la del mapa de la web (una
prueba revisa que sean iguales). El miembro `fuente` del GeoJSON cita a INEGI.

- **`/zones/geometry`:** el archivo tal cual (`application/geo+json`, unos 250 KB), con `ETag` y
  `Cache-Control` de un día; con `If-None-Match` igual, 304 sin cuerpo. Es lo que el escritorio
  necesita para dibujar los municipios en lugar de marcadores (A4).
- **`/zones/locate?lat=&lon=`:** el municipio (con su `region_id`, para llenar un caso) y su
  jurisdicción sanitaria. Sin PostGIS: cada municipio guarda su recuadro, que descarta casi todos,
  y luego la prueba de punto en polígono, con huecos (unos 0.13 ms por punto; coincide con shapely
  en 8 407 puntos al azar). Como la geometría está simplificada, un punto en la rendija entre dos
  fronteras (o a menos de 0.0015 grados del borde del estado) se asigna al municipio más cercano y
  sale con `aproximado` en true. Fuera de Nuevo León, `municipio` y `jurisdiccion` son null.
- La imagen copia el GeoJSON (`Dockerfile` y la excepción en `.dockerignore`).

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

Corre en `infra/docker-compose.yml`.
