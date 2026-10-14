# Servicio regiones — borrador funcional

**Puerto externo:** 5213. Escucha 8000 dentro de su contenedor, según el catálogo.
**Público:** consulta de municipios de Nuevo León (no exige JWT porque debe responder si Redis cae).

- `GET /api/v1/regions` lista municipios, búsqueda `q`, orden `order`, dirección `direction`.
- `GET /api/v1/regions/{id}` detalle de un municipio o 404.
- `/health`, `/docs`, `/openapi.json` se obtienen de `epidemia_comun`.
- XML predeterminado; JSON con `?format=json`.

Reutiliza `backend_web.queries.get_regiones_catalogo()` y `get_region_municipio()`.
Solo lectura sobre `regions` y `region_age_groups`, no escribe ni necesita bitácora.

**Pendiente:** la entrada en el compose (bloque J). Evidencia de funcionamiento en `evidencias/servicios/regiones/`.
