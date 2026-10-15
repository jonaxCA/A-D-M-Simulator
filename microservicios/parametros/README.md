# EPIDEMIA - Servicio parametros

Puerto externo previsto: 5212; puerto interno en Docker: 8000.

El servicio reutiliza las consultas y reglas existentes de `backend_web`.
Sus rutas quedan bajo `/api/v1` y tienen contrato en
`docs/contratos/parametros/openapi.json`.

## Ejecución en desarrollo

Instalar los requerimientos de `backend_web` y `microservicios/comun`,
configurar `JWT_SECRET_KEY`, `REDIS_URL` y `DATABASE_URL`, y levantar
`python -m microservicios.parametros.app` desde la raíz con `PYTHONPATH`
incluyendo `microservicios/comun`.

Comprobar `/health`, `/docs` y peticiones GET en ambos formatos
(XML por defecto y JSON con `?format=json`). Las rutas PUT/POST exigen un
JWT del servicio de identidad, con sesión activa en Redis.

Pendiente: la incorporación al compose (bloque J). Evidencia de funcionamiento en `evidencias/servicios/parametros/`.
