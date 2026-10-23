# EPIDEMIA - Servicio escenarios

Puerto externo: 5231; puerto interno en Docker: 8000. Contrato:
`docs/contratos/escenarios/openapi.json` (ejemplos JSON y XML por ruta en `ejemplos/`).

## Qué hace

Alta de escenarios, versiones nuevas, historial y duplicado. Reutiliza las reglas de
`backend_web/queries.py` (`valida_escenario`, `crea_escenario`, `valida_version`,
`crea_version`, `duplica_escenario`, `get_escenarios`, `get_escenario_detalle`,
`get_versiones`), que escriben y registran la bitácora en la misma transacción con el
`Contexto` del token.

- **Alta**: escenario y versión 1 (borrador, vigente) en una sola transacción, después de
  pasar por las reglas del monolito y por el servicio `validacion`.
- **Versión siguiente**: nunca sobrescribe; copia las intervenciones de la vigente.
- **Duplicado**: escenario nuevo de quien duplica, con una versión copiada.

Escribe `scenarios` y `scenario_versions` (alta y contenido). Lee `diseases`, `regions`,
`region_age_groups`, `users`, `scenario_interventions` e `intervention_types`.

## Rutas (`/api/v1`)

| Método y ruta | Qué hace | Roles |
|---|---|---|
| `GET /scenarios?q=` | Lista con la versión vigente | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR |
| `GET /scenarios/{id}?version=` | Detalle de una versión (vigente por defecto) e intervenciones | los mismos |
| `GET /scenarios/{id}/versions` | Historial | los mismos |
| `POST /scenarios` (201) | Alta | los mismos |
| `POST /scenarios/{id}/versions` (201) | Versión siguiente | los mismos; solo quien creó el escenario o ADMINISTRADOR (403 si no) |
| `POST /scenarios/{id}/duplicate` (201) | Duplica (`name`, `version` opcional) | los mismos; no exige ser dueño |

Los cuerpos se aceptan en JSON o XML (`Content-Type`). XML por defecto en la respuesta; JSON
con `?format=json` o `Accept: application/json`. Campos del alta: `name`, `description`,
`disease_id`, `region_id`, `population_size`, `horizon_days`, `initial_infected`,
`stratify` (booleano), `age_unknown_policy`, `notes`. Versión: los mismos menos nombre,
enfermedad y región, y `notes` es obligatorio.

Errores RFC 7807: 401 (sin token o vencido), 403 (rol o no es dueño), 404, 409 (nombre
repetido por autor, versión concurrente), 422 (reglas de negocio, con los mensajes del
monolito), 503 (Redis o `validacion` caídos).

## Llamada a `validacion`

`POST /api/v1/validate` en JSON con el escenario (`name`, `disease_id`, `region_id`,
`population_size`, `horizon_days`, `initial_infected`, `estratificar`, ...; los nombres son los de
`validacion`), reenviando el token
de la persona. Se rechaza (422) si responde `errores` no vacío o `valido: false`; un fallo 5xx
o servicio caído da 503 `SERVICIO_NO_DISPONIBLE`. URL por `SERVICIO_VALIDACION_URL`.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`, `SERVICIO_VALIDACION_URL`,
`VERSION_SERVICIO` y `CONSOLE_ORIGIN` (opcional).

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/escenarios -q
```

Las pruebas simulan la base, Redis y `validacion`. A mano: `/health`, `/docs`, y con un token
de `auth`: `curl -H "Authorization: Bearer $T" "http://localhost:5231/api/v1/scenarios?format=json"`.
