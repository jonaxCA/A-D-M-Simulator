# EPIDEMIA - Servicio parametros

Puerto externo previsto: 5212; puerto interno en Docker: 8000.

Sus reglas viven aquí (D37, E8): `reglas.py` valida los parámetros con los límites del motor
(`procesamiento.entrada_motor`) y `datos.py` los guarda con su versión. Ya no importa `backend_web`
ni usa `epidemia_comun/validaciones.py`. Sus rutas quedan bajo `/api/v1` y tienen contrato en
`docs/contratos/parametros/openapi.json` y `parametros.xsd`.

**Incertidumbre (D58).** Cada parámetro lleva `valor`, `fuente` o `supuesto` y, opcional, su
`intervalo`: `min` y `max`, que contienen el valor y caben en los límites del parámetro, y `tipo`
(`IC95`, `RIC` o `rango`, por omisión). `GET .../parameters/status` lo muestra. El motor no lo usa.

**Versiones (D58).** `PUT .../parameters` (EPIDEMIOLOGO, ADMINISTRADOR) acepta `motivo` y guarda la
versión siguiente, completa, en la misma transacción; la respuesta trae `version`.
`GET .../parameters/versions` da el historial (público) y `GET .../parameters/versions/{version}`, una
versión con sus parámetros. La versión 1 son los de antes del historial (042).

## Ejecución en desarrollo

Instalar los requerimientos de `procesamiento` y `microservicios/comun`,
configurar `JWT_SECRET_KEY`, `REDIS_URL` y `DATABASE_URL`, y levantar
`python -m microservicios.parametros.app` desde la raíz con `PYTHONPATH`
incluyendo `microservicios/comun`.

Comprobar `/health`, `/docs` y peticiones GET en ambos formatos
(XML por defecto y JSON con `?format=json`). Las rutas PUT/POST exigen un
JWT del servicio de identidad, con sesión activa en Redis.

Corre en `infra/docker-compose.yml`.
