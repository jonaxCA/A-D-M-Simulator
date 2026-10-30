# EPIDEMIA - Servicio intervenciones

Puerto externo: 5232; puerto interno en Docker: 8000. Contrato:
`docs/contratos/intervenciones/openapi.json` (ejemplos JSON y XML por ruta en `ejemplos/`). Las
respuestas XML validan contra `docs/contratos/intervenciones/intervencion.xsd`.

## Qué hace

Agrega, quita y reordena las intervenciones de una versión, y fija el costo de una
intervención. Reutiliza `valida_intervencion`, `params_desde_schema` (con un adaptador del
cuerpo JSON/XML a los campos `p_<CODE>_<clave>`), `agrega_intervencion`, `quita_intervencion`,
`mueve_intervencion` y `valida_costo_intervencion` de `backend_web/queries.py`. Los parámetros se
validan contra el `param_schema` del tipo; los que el tipo no declara se rechazan.

Escribe `scenario_interventions` y, solo en la ruta de costo, las columnas de costo de
`intervention_types` (`unit_cost`, `cost_source`, `cost_is_assumption`). Lee `scenario_versions`,
`scenarios` (dueño) e `intervention_types`.

## Rutas (`/api/v1`)

| Método y ruta | Qué hace | Roles |
|---|---|---|
| `GET /versions/{id}/interventions` | Lista en orden de aplicación | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR |
| `POST /versions/{id}/interventions` (201) | Agrega al final | los mismos |
| `DELETE /versions/{id}/interventions/{iid}` | Quita y cierra el hueco | los mismos |
| `POST /versions/{id}/interventions/{iid}/move` | `{"direction": "subir"\|"bajar"}` | los mismos |
| `PUT /versions/{id}/interventions/{iid}/cost` | `unit_cost`, `cost_source`, `cost_is_assumption` | EPIDEMIOLOGO, ADMINISTRADOR |

Reglas (las del monolito): agregar, quitar y mover solo si la versión es la vigente y está en
borrador (si no, 409 `CONFLICTO`), y solo quien creó el escenario o un ADMINISTRADOR (403).
Dos intervenciones del mismo tipo que se traslapan dan 409. Mover usa `subir`/`bajar` (los del
monolito); `up`/`down` se aceptan como alias. Mover en un extremo no es error (`movida: false`).

El costo vive en el tipo, como en el monolito: cambiarlo afecta a todas las intervenciones de
ese tipo. No exige que la versión sea borrador. Se audita en la misma transacción
(`intervention_types`).

Cuerpos en JSON o XML; respuesta XML por defecto, JSON con `?format=json` o
`Accept: application/json`. Errores RFC 7807: 401, 403, 404, 409, 422, 503.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`, `VERSION_SERVICIO`, `CONSOLE_ORIGIN` (opcional).
No llama a otros servicios.

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/intervenciones -q
```

Las pruebas simulan la base y Redis. A mano: `/health`, `/docs`, y con un token de `auth`:
`curl -H "Authorization: Bearer $T" "http://localhost:5232/api/v1/versions/1/interventions?format=json"`.
