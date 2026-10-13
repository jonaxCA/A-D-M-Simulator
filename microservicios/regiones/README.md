# Servicio regiones — borrador funcional

**Puerto externo:** 5213. Escucha 8000 dentro del futuro contenedor, según el catálogo.
**Público:** consulta de municipios de Nuevo León (no exige JWT porque debe responder si Redis cae).

- `GET /api/v1/regions` lista municipios, búsqueda `q`, orden `order`, dirección `direction`.
- `GET /api/v1/regions/{id}` detalle de un municipio o 404.
- `/health`, `/docs`, `/openapi.json` se obtienen de `epidemia_comun`.
- XML predeterminado; JSON con `?format=json`.

Reutiliza `backend_web.queries.get_regiones_catalogo()` y `get_region_municipio()`.
Solo lectura sobre `regions` y `region_age_groups`, no escribe ni necesita bitácora.

**Pendiente antes de marcar terminado:** prueba HTTP real contra PostgreSQL, healthcheck de Docker,
revisión del contrato en Swagger y pruebas del contenedor. No se ha hecho despliegue.
