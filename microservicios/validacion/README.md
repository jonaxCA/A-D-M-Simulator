# EPIDEMIA - Servicio validacion

Puerto del catálogo: **5234** (8000 dentro del contenedor). Contrato:
`docs/contratos/validacion/openapi.json` (idéntico al de `/openapi.json`) y ejemplos JSON/XML en
`docs/contratos/validacion/ejemplos/`.

## Qué hace

Revisa un escenario contra las reglas del monolito (`backend_web.queries.valida_escenario`,
`valida_intervencion`) y el motor (`procesamiento.motor`) **sin guardar nada**. Por eso no
escribe en la bitácora. Lee `diseases`, `regions`, `region_age_groups`, `intervention_types`,
`scenarios` y `scenario_versions`.

## Rutas

| Ruta | Qué hace |
|---|---|
| `POST /api/v1/validate` | Valida el escenario del cuerpo (JSON o XML). |
| `GET /api/v1/versions/{id}/validation` | Valida la versión guardada `{id}` (`revisa_version`). |
| `GET /health`, `/docs`, `/openapi.json` | Comunes a todos los servicios. |

Roles de las dos rutas: `ANALISTA`, `EPIDEMIOLOGO`, `ADMINISTRADOR`. Se llama con el token de
la persona (los servicios que consumen este reenvían el suyo con `llamar()`); no acepta tokens
de servicio.

### Respuesta y códigos

`{valido, errores[], avisos[]}` (la ruta de versión añade `version_id`, `scenario_id`,
`version_number`, `status`). **Un escenario inválido responde 200 con `valido=false`**: la
petición se atendió bien y el dictamen es el contenido. Los códigos de error significan otra
cosa: 400 JSON/XML ilegible o `?format` desconocido, 401/403 token o rol, 404 versión
inexistente, 413 cuerpo mayor de 1 MiB, 415 `Content-Type` no soportado, 422 cuerpo mal formado
(no es objeto, un campo simple trae objeto/lista, `interventions` no es lista de objetos) o
`version_id` no entero, 503 Redis/base caída.

Los mensajes de `errores` y `avisos` están en español y son los de `backend_web` y el motor.

### Cuerpo de `POST /api/v1/validate`

Mismos campos que el formulario de alta del monolito. Enteros como número o como texto (XML).

| Campo | Tipo | Notas |
|---|---|---|
| `name` | texto | obligatorio, máx. 160 |
| `description`, `notes` | texto | opcionales |
| `disease_id` | entero | enfermedad activa y simulable |
| `region_id` | entero | estado o municipio de Nuevo León |
| `population_size` | entero | obligatorio si no se estratifica; ignorado si se estratifica |
| `estratificar` | booleano | `true` = población por edad del censo de la región |
| `age_unknown_policy` | `excluir`/`prorratear` | si la región tiene gente sin edad |
| `population_by_age` | objeto grupo->personas | opcional; equivale a `estratificar`; debe coincidir con el censo |
| `initial_infected` | entero | obligatorio |
| `horizon_days` | entero | obligatorio |
| `interventions` | lista | opcional: `{code, start_day, end_day?, coverage?, compliance?, params?}` |

En XML, `interventions` lleva un hijo `<item>` (o `<intervention>`) por intervención. Los campos
desconocidos se ignoran y quedan como aviso.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (y las habituales de `epidemia_comun`).
No llama a otros servicios.

## Cómo probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD .venv/bin/python -m pytest microservicios/validacion -q
curl -X POST "http://localhost:5234/api/v1/validate?format=json" -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d @docs/contratos/validacion/ejemplos/validar_escenario.peticion.json
```
