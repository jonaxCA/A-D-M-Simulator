# EPIDEMIA - Servicio enfermedades

Puerto externo previsto: 5211; puerto interno en Docker: 8000.

Sus reglas viven aquí (E8, D37): `datos.py` (la lista con su actividad en Nuevo León, la ficha, la
clasificación y las definiciones de caso, D58) y `reglas.py` (el código y el nombre del alta). La
lista dice si cada enfermedad se puede simular con `procesamiento.entrada_motor`, así que su imagen
parte de `epidemia/base-simulacion`, sin `backend_web`. Sus rutas quedan bajo
`/api/v1` y tienen contrato en `docs/contratos/enfermedades/openapi.json` y `enfermedad.xsd`.

**Clasificación.** La ficha (`GET /diseases/{id}`) trae `transmission` (respiratoria o vectorial),
`icd10` y `classification_source`. `PUT /diseases/{id}` las cambia juntas y con su fuente.

**Definiciones de caso (D58).** Cada enfermedad tiene versiones de su definición operacional de caso:
una lista de `criterios` (`clasificacion` y `texto`) con su `fuente`.

| Ruta | Qué hace | Acceso |
|---|---|---|
| `GET /diseases/{id}/case-definitions` | Todas las versiones, la más reciente primero | Pública |
| `GET /diseases/{id}/case-definitions/current` | La vigente (404 si no tiene) | Pública |
| `GET /diseases/{id}/case-definitions/{version}` | Una versión | Pública |
| `POST /diseases/{id}/case-definitions` (201) | Crea la versión siguiente como borrador (409 si ya hay uno) | EPIDEMIOLOGO, ADMINISTRADOR |
| `PUT /diseases/{id}/case-definitions/{version}` | Edita un borrador (409 si ya se publicó) | los mismos |
| `POST /diseases/{id}/case-definitions/{version}/publish` | El borrador pasa a vigente y la anterior a retirada | los mismos |

La 042 trae las de la DGE (enfermedad respiratoria viral de 2023 para COVID-19 e influenza; dengue,
paludismo y zika de 2021), con el texto literal y sus páginas. Escribe `case_definitions` y, de
`diseases`, la clasificación; audita `CREATE`, `UPDATE` y `PUBLISH`.

`GET /api/v1/diseases/stats` (pública, como el catálogo) da las tarjetas de la pantalla de
enfermedades de la web: registradas, activas, inactivas, altas en 30 días y `detectadas_30d`
(con un caso pendiente o validado en Nuevo León en 30 días). Su consulta vive en el servicio
(D37).

## Ejecución en desarrollo

Instalar los requerimientos de `procesamiento` y `microservicios/comun`,
configurar `JWT_SECRET_KEY`, `REDIS_URL` y `DATABASE_URL`, y levantar
`python -m microservicios.enfermedades.app` desde la raíz con `PYTHONPATH`
incluyendo `microservicios/comun`.

Comprobar `/health`, `/docs` y peticiones GET en ambos formatos
(XML por defecto y JSON con `?format=json`). Las rutas PUT/POST exigen un
JWT del servicio de identidad, con sesión activa en Redis.

Corre en `infra/docker-compose.yml`.
