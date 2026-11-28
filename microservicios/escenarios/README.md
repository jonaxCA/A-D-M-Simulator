# EPIDEMIA - Servicio escenarios

Puerto externo: 5231; puerto interno en Docker: 8000. Contrato:
`docs/contratos/escenarios/openapi.json` (ejemplos JSON y XML por ruta en `ejemplos/`).

## Qué hace

Alta de escenarios, versiones nuevas, historial con responsables, duplicado, proyectos de
investigación y archivado (D54). Todo vive en `datos.py` (E8): el alta, la versión siguiente y el
duplicado escriben y registran la bitácora en la misma transacción con el `Contexto` del token.
Revisar el escenario es de `validacion` (D37): antes de guardar un alta (`POST /api/v1/validate`) o
una versión nueva (`POST /api/v1/validate/version`) le pide el dictamen, y guarda el formulario
normalizado que regresa. Su imagen parte de `epidemia/base-vigilancia`, sin `backend_web` ni el
motor.

- **Alta**: escenario y versión 1 (borrador, vigente) en una sola transacción, después de
  pasar por el servicio `validacion`. Si `validacion` no responde, 503 y no se guarda nada.
- **Versión siguiente**: nunca sobrescribe; copia las intervenciones de la vigente.
- **Duplicado**: escenario nuevo de quien duplica, con una versión copiada. Se queda en el
  proyecto del original si sigue activo.
- **Proyectos** (`research_projects`): agrupan escenarios de una enfermedad y una región, con su
  objetivo, su periodo y sus motores. Un escenario solo entra a uno activo de su misma enfermedad
  y región (la base también lo revisa). No se borran: se archivan.
- **Archivar**: un escenario archivado es de solo lectura (sin versiones, cambios de
  intervenciones, envíos ni corridas) y deja de ser público; no se archiva con la versión vigente
  en revisión. Restaurarlo lo vuelve a `borrador`.
- **Candados de versión**: no se crea una versión de un escenario archivado ni mientras la vigente
  está en revisión (409).
- **Alcance (D43)**: las listas solo traen las regiones de la cuenta; lo de fuera es 403. Leen
  también INVESTIGADOR y AUTORIDAD_SANITARIA (D42).

Escribe `scenarios` (alta; `status`, `is_public` y `project_id`), `scenario_versions` (alta y
contenido), `scenario_interventions` (al versionar o duplicar) y `research_projects`. Lee
`diseases`, `regions`, `region_age_groups`, `users` e `intervention_types`.

## Rutas (`/api/v1`)

| Método y ruta | Qué hace | Roles |
|---|---|---|
| `GET /scenarios?q=&project_id=&archived=` | Lista con la versión vigente y el proyecto; sin archivados salvo `archived=true` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR, INVESTIGADOR, AUTORIDAD_SANITARIA |
| `GET /scenarios/versions?status=` | Versiones de todos los escenarios, aprobadas primero, con quién las creó y revisó (nombre completo); para la pantalla de simulaciones de la web (D36) | los mismos |
| `GET /scenarios/{id}?version=` | Detalle de una versión (vigente por defecto), intervenciones y proyecto | los mismos |
| `GET /scenarios/{id}/versions` | Historial con responsables: autor, envío, revisor, comentario, `devuelta` y firma | los mismos |
| `POST /scenarios` (201) | Alta (`project_id` opcional) | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR |
| `POST /scenarios/{id}/versions` (201) | Versión siguiente | los mismos; solo quien creó el escenario o ADMINISTRADOR (403 si no) |
| `POST /scenarios/{id}/duplicate` (201) | Duplica (`name`, `version` opcional) | los mismos; no exige ser dueño |
| `PUT /scenarios/{id}/project` | Mete, cambia o saca (`null`) el escenario de un proyecto | los mismos; dueño o ADMINISTRADOR |
| `POST /scenarios/{id}/archive`, `/restore` | Archiva o restaura (RF-D12) | los mismos; dueño o ADMINISTRADOR |
| `GET /projects?status=&q=` | Proyectos (activos por defecto; `archivado` o `todos`) | los cinco lectores |
| `GET /projects/{id}` | Proyecto con sus escenarios | los cinco lectores |
| `POST /projects` (201), `PATCH /projects/{id}` | Alta y cambio (`name`, `objective`, `disease_id`, `region_id`, `period_start`, `period_end`, `motores`) | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR; cambiar, solo su dueño o ADMINISTRADOR |
| `POST /projects/{id}/archive`, `/restore` | Archiva o restaura el proyecto | los mismos; dueño o ADMINISTRADOR |

Los cuerpos se aceptan en JSON o XML (`Content-Type`). XML por defecto en la respuesta; JSON
con `?format=json` o `Accept: application/json`. Campos del alta: `name`, `description`,
`disease_id`, `region_id`, `population_size`, `horizon_days`, `initial_infected`,
`stratify` (booleano), `age_unknown_policy`, `notes`. Versión: los mismos menos nombre,
enfermedad y región, y `notes` es obligatorio.

Errores RFC 7807: 401 (sin token o vencido), 403 (rol, no es dueño o fuera del alcance de la
cuenta), 404, 409 (nombre repetido por autor, versión concurrente, archivado o con la vigente en
revisión), 422 (reglas de negocio, con los mensajes del monolito; un proyecto de otra enfermedad
o región), 503 (Redis, `roles` o `validacion` caídos).

## Llamada a `validacion`

`POST /api/v1/validate` en JSON con el escenario (`name`, `disease_id`, `region_id`,
`population_size`, `horizon_days`, `initial_infected`, `estratificar`, ...; los nombres son los de
`validacion`), reenviando el token
de la persona. Se rechaza (422) si responde `errores` no vacío o `valido: false`; un fallo 5xx
o servicio caído da 503 `SERVICIO_NO_DISPONIBLE`. URL por `SERVICIO_VALIDACION_URL`.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL`, `SERVICIO_VALIDACION_URL`,
`SERVICIO_ROLES_URL` (alcance de D43), `VERSION_SERVICIO` y `CONSOLE_ORIGIN` (opcional).

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/escenarios -q
```

Las pruebas simulan la base, Redis, `roles` y `validacion`; `test_escenarios_bd.py` prueba
`datos.py` contra la base de pruebas, con la 064. A mano: `/health`, `/docs`, y con un token
de `auth`: `curl -H "Authorization: Bearer $T" "http://localhost:5231/api/v1/scenarios?format=json"`.
