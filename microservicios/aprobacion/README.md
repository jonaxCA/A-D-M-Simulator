# EPIDEMIA - Servicio aprobacion

Puerto del catálogo: **5233** (8000 dentro del contenedor). Contrato:
`docs/contratos/aprobacion/openapi.json` (idéntico al de `/openapi.json`) y ejemplos JSON/XML en
`docs/contratos/aprobacion/ejemplos/`.

## Qué hace

Envío a revisión, aprobación y rechazo de la versión vigente de un escenario. Reutiliza
`backend_web.queries.envia_a_revision` y `resuelve_revision`, que escriben **solo** las columnas
de estado y revisión de `scenario_versions` (`status`, `submitted_at`, `disease_params`,
`reviewed_by`, `reviewed_at`, `review_comment`) y la bitácora (`UPDATE`) con el cursor de la
misma transacción y el `Contexto` del token. Lee `scenarios` y `scenario_interventions`.

## Rutas y roles

| Ruta | Roles | Resultado |
|---|---|---|
| `POST /api/v1/scenarios/{id}/submit` | `ANALISTA`, `EPIDEMIOLOGO`, `ADMINISTRADOR`; además dueño del escenario o `ADMINISTRADOR` (si no, 403) | Pide el dictamen a `validacion`; congela `disease_params` y pasa `borrador` -> `en_revision` |
| `POST /api/v1/scenarios/{id}/review` | solo `EPIDEMIOLOGO` | Cuerpo `{decision: aprobar\|rechazar, comentario}`; deja `aprobado`/`rechazado` |
| `GET /api/v1/reviews/pending` | `EPIDEMIOLOGO`, `ADMINISTRADOR` | Bandeja `{total, pendientes[]}`, la más antigua primero |

### Errores

- 401/403: token o rol. 404: escenario inexistente. 422: `decision` inválida, `rechazar` sin
  `comentario`, comentario de más de 1,000 caracteres, o la versión no pasa `validacion`.
- 409 `CONFLICTO`: la versión no está en el estado esperado, **quien revisa creó la versión**
  («No puedes revisar una versión que tú creaste...») o alguien cambió el estado a la vez (los
  `UPDATE` llevan `WHERE status = ...`).
- 503 `SERVICIO_NO_DISPONIBLE`: `validacion` caído (el envío no escribe nada) o Redis caído.

Al aprobar se llama a `notificaciones` (`POST /api/v1/notifications`, tipo `SCENARIO_APPROVED`,
para quien creó la versión) con un **token de servicio** (`token_servicio`), porque esa ruta es
interna. Si falla, **la aprobación se mantiene** y solo se anota una advertencia en el log.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`, `SERVICIO_VALIDACION_URL` (p. ej.
`http://validacion:8000`) y `SERVICIO_NOTIFICACIONES_URL`.

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/aprobacion -q
```
Las pruebas simulan la base (respetando los `UPDATE` condicionales), Redis y `llamar()`.
