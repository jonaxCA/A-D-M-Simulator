# EPIDEMIA - Servicio escenarios-xml

Puerto externo: 5235; interno en Docker: 8000. Exporta e importa un escenario completo
(versión, población por edad, intervenciones) como un documento XML validado contra
`docs/contratos/escenarios-xml/escenario.xsd`. **No escribe ninguna tabla**: lee
`scenarios`, `scenario_versions` y `scenario_interventions` (más los códigos de
`diseases`, `regions` e `intervention_types`) y, al importar, crea todo llamando a otros
servicios.

## Rutas

| Ruta | Roles | Qué hace |
|---|---|---|
| `GET /api/v1/scenarios/{id}/export[?version=N]` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Documento XML del escenario (versión vigente o la N). Registra `EXPORT` en la bitácora. |
| `POST /api/v1/scenarios/import` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR | Cuerpo `application/xml`. Crea un escenario nuevo (versión 1, borrador). Responde 201. |
| `GET /api/v1/schemas/scenario.xsd` | pública | El XSD. |

Más `/health`, `/docs` y `/openapi.json` de la biblioteca común.

## Formatos

El export es un **documento**: siempre XML. `?format=json` responde 400 y `Accept` se
ignora. La respuesta de importación y los errores (RFC 7807) sí siguen la regla general:
XML por defecto, JSON con `?format=json` o `Accept: application/json`.

## Importar, paso a paso

1. XML mal formado o con DTD/entidades: 400. Content-Type distinto de XML: 415.
2. Validación contra el XSD: 422 `DATOS_INVALIDOS` con `errores` (lista de `ruta` y `mensaje`).
3. Reglas entre campos (suma de la población por edad, política de edad desconocida,
   `fin_dia >= inicio_dia`, días dentro del horizonte) y códigos de catálogo existentes: 422.
4. `validacion` (`POST /api/v1/validate`, JSON). Si devuelve errores: 422 y no se crea nada.
5. `escenarios` (`POST /api/v1/scenarios`, **en XML**, como pide el catálogo) y, por cada
   intervención en orden, `intervenciones` (`POST /api/v1/versions/{vid}/interventions`, en
   JSON: sus parámetros pueden ser listas, y una lista que viaja en XML llega como
   `<item>` anidados, que `intervenciones` no acepta como valor simple).

Las formas de los cuerpos están en `mapeo.py` (`cuerpo_validacion`, `cuerpo_escenarios`,
`cuerpo_intervencion`) y las revisa `microservicios/comun/tests/test_consistencia_servicios.py`
con los servicios reales. Notas: `validacion` recibe un cuerpo plano con los campos del
formulario del monolito (`estratificar`, `population_by_age`, `interventions[]`); `escenarios`
no recibe el reparto por edad sino `stratify` y toma el del censo de la región (si el XML trae
otro, `validacion` lo rechaza); `escenarios` no devuelve el id de la versión, así que se pide
`GET /api/v1/scenarios/{id}` (`version.id`); `intervenciones` no guarda la región destino de
una intervención, y el importador lo avisa en `avisos`.

El token de la persona se reenvía a los tres servicios. Un servicio caído o con 5xx es
503 `SERVICIO_NO_DISPONIBLE`; 409 y 4xx de los otros servicios se traducen a 409/422.

**Falla a medias.** No hay compensación automática (no se borra nada, no se reintenta). Si
falla una intervención, el escenario queda en borrador con las anteriores, y el `detail` del
error dice el id del escenario, la versión, cuántas se crearon y cuál falló. La persona
agrega las faltantes con `POST /api/v1/versions/{vid}/interventions` o descarta el escenario.

## Archivos

- `rutas.py`: las tres rutas y las llamadas a otros servicios.
- `mapeo.py`: **único** lugar que conoce los campos que esperan `escenarios`, `intervenciones`
  y `validacion` (`cuerpo_escenarios`, `cuerpo_intervencion`, `cuerpo_validacion`,
  `ids_de_respuesta`, `fallas_de`), y la conversión documento XML a dict y de vuelta.
- `lectura.py`: los SELECT y la resolución de códigos a ids.

## Variables

`JWT_SECRET_KEY`, `REDIS_URL`, `DATABASE_URL` (como los demás servicios) y las URL de los
servicios que llama: `SERVICIO_VALIDACION_URL`, `SERVICIO_ESCENARIOS_URL`,
`SERVICIO_INTERVENCIONES_URL`. Requiere `xmlschema` (está en `microservicios/comun/requirements.txt`).

## Probar

```
PYTHONPATH=$PWD/microservicios/comun:$PWD python -m pytest microservicios/escenarios_xml -q
```

Con el servicio arriba: `curl -H "Authorization: Bearer $T" localhost:5235/api/v1/scenarios/1/export`.
