# EPIDEMIA - Servicio validacion

Puerto del catálogo: **5234** (8000 dentro del contenedor). Contrato:
`docs/contratos/validacion/openapi.json` (idéntico al de `/openapi.json`) y ejemplos JSON/XML en
`docs/contratos/validacion/ejemplos/`.

## Qué hace

Revisa un escenario contra sus reglas (`reglas.py`: `valida_escenario`, `valida_version` y
`revisa_version`, E8) y el motor (`procesamiento.motor`) **sin guardar nada**. Por eso no escribe en
la bitácora. Las reglas de cada intervención son de `intervenciones`: se las pide por HTTP
(`POST /api/v1/interventions/validate`, con el token de la persona) solo si el escenario trae
intervenciones (D37). Lee `diseases`, `regions`, `region_age_groups`, `scenarios`,
`scenario_versions` y `scenario_interventions`; `datos.escenario_detalle` es copia de solo lectura
del de `escenarios`, y `test_copias_de_lectura.py` revisa que sigan iguales. Su imagen parte de
`epidemia/base-simulacion`.

## Rutas

| Ruta | Qué hace |
|---|---|
| `POST /api/v1/validate` | Valida el escenario del cuerpo (JSON o XML) y regresa el formulario normalizado en `datos`. |
| `POST /api/v1/validate/version` | Valida una versión nueva de un escenario que ya existe (`scenario_id` y los campos de la versión), con su región y sus parámetros; escenarios la pide antes de crearla. |
| `GET /api/v1/versions/{id}/validation` | Valida la versión guardada `{id}` (`revisa_version`) y da su `huella` (D55). |
| `GET /health`, `/docs`, `/openapi.json` | Comunes a todos los servicios. |

Roles de las tres rutas: `ANALISTA`, `EPIDEMIOLOGO`, `ADMINISTRADOR`. Se llama con el token de
la persona (los servicios que consumen este reenvían el suyo con `llamar()`); no acepta tokens
de servicio.

### Respuesta y códigos

`{valido, errores[], avisos[], datos}` (la ruta de versión guardada cambia `datos` por `version_id`, `scenario_id`,
`version_number`, `status` y `huella`: la SHA-256 de la entrada canónica del motor, la misma que
guardará cada corrida en `scenario_checksum`; `aprobacion` firma con ella la versión que aprueba).
`huella.py` lee las filas con una copia de `simulador/datos.version_para_motor`, y una prueba revisa
que sigan iguales. **Un escenario inválido responde 200 con `valido=false`**: la
petición se atendió bien y el dictamen es el contenido. Los códigos de error significan otra
cosa: 400 JSON/XML ilegible o `?format` desconocido, 401/403 token o rol, 404 versión
inexistente, 413 cuerpo mayor de 1 MiB, 415 `Content-Type` no soportado, 422 cuerpo mal formado
(no es objeto, un campo simple trae objeto/lista, `interventions` no es lista de objetos) o
`version_id` no entero, 503 Redis/base caída.

Los mensajes de `errores` y `avisos` están en español: los de las reglas, los de `intervenciones` y los del motor. Si `intervenciones` no responde, la validación de un escenario con intervenciones es 503.

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
