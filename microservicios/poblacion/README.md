# EPIDEMIA - Servicio poblacion

Puerto externo previsto: 5214; puerto interno en Docker: 8000.

Sus reglas viven en `datos.py` (E8: ya no importa `backend_web` y su imagen parte de
`epidemia/base-vigilancia`): consulta y corrección de la población total y de las bandas de edad de
cada municipio, con el control optimista, el recálculo del estado y la bitácora de antes. Sus rutas
quedan bajo `/api/v1` y tienen contrato en `docs/contratos/poblacion/openapi.json`.

**Versiones y periodos (D56).** Cada corrección guarda la versión siguiente de la población del
municipio y, si cambió, la del estado (`population_versions`), en la misma transacción; la versión 1,
con las cifras de antes, se guarda en el primer ajuste. La respuesta trae `version`.

- `GET /api/v1/regions/{id}/population/versions` las versiones del estado o de un municipio (sin
  ajustes, la vigente como versión 1, Censo 2020).
- `GET /api/v1/regions/{id}/population/periods` la población en cada censo o conteo de INEGI, de
  1990 a 2020 (`census_population`, 043).

## Ejecución en desarrollo

Instalar los requerimientos de `microservicios/comun`,
configurar `JWT_SECRET_KEY`, `REDIS_URL` y `DATABASE_URL`, y levantar
`python -m microservicios.poblacion.app` desde la raíz con `PYTHONPATH`
incluyendo `microservicios/comun`.

Comprobar `/health`, `/docs` y peticiones GET en ambos formatos
(XML por defecto y JSON con `?format=json`). Las rutas PUT/POST exigen un
JWT del servicio de identidad, con sesión activa en Redis.

Corre en `infra/docker-compose.yml`.
