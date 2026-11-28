# EPIDEMIA - Servicio aprobacion

Puerto del catálogo: **5233** (8000 dentro del contenedor). Contrato:
`docs/contratos/aprobacion/openapi.json` (idéntico al de `/openapi.json`) y ejemplos JSON/XML en
`docs/contratos/aprobacion/ejemplos/`. Las respuestas XML validan contra
`docs/contratos/aprobacion/aprobacion.xsd`.

## Qué hace

Envío a revisión, aprobación con firma, rechazo y devolución para cambios de la versión vigente
de un escenario (D55). Sus reglas viven en `datos.py` (E8: ya no importa `backend_web` y su imagen
parte de `epidemia/base-vigilancia`). Escribe **solo** las columnas de estado, revisión y firma de
`scenario_versions` (`status`, `submitted_at`, `disease_params`, `reviewed_by`, `reviewed_at`,
`review_comment`, `approval_sha256`) y la bitácora (`UPDATE`) con el cursor de la misma
transacción y el `Contexto` del token. Lee `scenarios`, `scenario_interventions` y, para la
firma, `simulation_runs` (`scenario_version_id`, `scenario_checksum`, `status`).

- **Devolver** regresa la misma versión a `borrador` con el comentario: su autor la corrige y la
  reenvía. **Rechazar** la cierra.
- **Firmar**: al aprobar, `validacion` da la huella de la entrada del motor y se guarda en
  `approval_sha256`. Es la misma que guarda cada corrida en `scenario_checksum`. Sin ella no se
  aprueba (503).

## Rutas y roles

| Ruta | Roles | Resultado |
|---|---|---|
| `POST /api/v1/scenarios/{id}/submit` | `ANALISTA`, `EPIDEMIOLOGO`, `ADMINISTRADOR`; además dueño del escenario o `ADMINISTRADOR` (si no, 403) | Pide el dictamen a `validacion`; congela `disease_params` y pasa `borrador` -> `en_revision`. 409 si el escenario está archivado |
| `POST /api/v1/scenarios/{id}/review` | `EPIDEMIOLOGO`, `ADMINISTRADOR` | Cuerpo `{decision: aprobar\|rechazar\|devolver, comentario}`; deja `aprobado` (con `approval_sha256`), `rechazado` o `borrador` |
| `GET /api/v1/reviews/pending` | `EPIDEMIOLOGO`, `ADMINISTRADOR` | Bandeja `{total, pendientes[]}`: versiones vigentes en revisión, la más antigua primero |
| `GET /api/v1/versions/{id}/signature` | `ANALISTA`, `EPIDEMIOLOGO`, `ADMINISTRADOR` | La firma, quién y cuándo, la huella actual (`integra`) y las corridas que coinciden con lo firmado |

### Errores

- 401/403: token o rol. 404: escenario o versión inexistente. 422: `decision` inválida,
  `rechazar` o `devolver` sin `comentario`, comentario de más de 1,000 caracteres, o la versión no
  pasa `validacion`.
- 409 `CONFLICTO`: la versión no está en el estado esperado, **quien revisa creó la versión**
  («No puedes revisar una versión que tú creaste...») o alguien cambió el estado a la vez (los
  `UPDATE` llevan `WHERE status = ...`).
- 503 `SERVICIO_NO_DISPONIBLE`: `validacion` caído o sin huella (el envío y la aprobación no
  escriben nada) o Redis caído.

Se llama a `notificaciones` (`POST /api/v1/notifications`) con un **token de servicio**
(`token_servicio`), porque esa ruta es interna:

- Al enviar a revisión: tipo `SCENARIO_SUBMITTED`, a los EPIDEMIOLOGO (`role`), RF-D15.
- Al aprobar: `SCENARIO_APPROVED`, para quien creó la versión.
- Al rechazar: `SCENARIO_REJECTED`, para quien creó la versión, con el comentario en `body` (RF-D16).
- Al devolver: `SCENARIO_RETURNED`, para quien creó la versión, con el comentario en `body` (D55).

Si falla, **el cambio de estado se mantiene** y solo se anota una advertencia en el log.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`, `SERVICIO_VALIDACION_URL` (p. ej.
`http://validacion:8000`) y `SERVICIO_NOTIFICACIONES_URL`.

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/aprobacion -q
```
Las pruebas simulan `datos.py`, Redis y `llamar()`; `test_aprobacion_bd.py` prueba `datos.py`
contra la base de pruebas, con la 064 (congelado, devolución, firma y los CHECK).
