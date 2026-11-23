# Servicio regiones — borrador funcional

**Puerto externo:** 5213. Escucha 8000 dentro de su contenedor, según el catálogo.
**Público:** consulta de municipios de Nuevo León (no exige JWT porque debe responder si Redis cae).

- `GET /api/v1/regions` lista municipios, búsqueda `q`, orden `order`, dirección `direction`.
- `GET /api/v1/regions/state` el estado (Nuevo León) como fila única: población agregada de sus
  municipios y la fuente de su 60+ (derivado del censo o la última corrección manual). 404 si no
  está cargado.
- `GET /api/v1/regions/{id}` detalle de un municipio o 404.
- `GET /api/v1/regions/{id}/children` las regiones hijas (los municipios del estado) (D56).
- `GET /api/v1/regions/{id}/health-areas` las jurisdicciones sanitarias de un municipio (Monterrey
  está en tres, en parte).
- `GET /api/v1/health-areas` y `/health-areas/{numero}` las 8 jurisdicciones de NL con sus municipios
  y su fuente (Reglamento Interior de Servicios de Salud de NL, art. 27; 043).
- `GET /api/v1/regions/search?q=` búsqueda territorial: estado, municipios (nombre o clave) y
  jurisdicciones, sin importar acentos; hasta 20.
- `/health`, `/docs`, `/openapi.json` se obtienen de `epidemia_comun`.
- XML predeterminado; JSON con `?format=json`.

El catálogo de municipios reutiliza `backend_web.queries.get_regiones_catalogo()` y
`get_region_municipio()` (E8 pendiente); la jerarquía, las jurisdicciones y la búsqueda viven en
`datos.py`. Solo lectura sobre `regions`, `region_age_groups`, `health_areas` y
`health_area_municipalities`; no escribe ni necesita bitácora. La geometría y los mapas son de `zonas`.

Corre en `infra/docker-compose.yml`.
