# Evidencias · grupo 14:00

Generadas el 2026-10-13 sobre la rama `feat/segundo-parcial-grupo-2pm`, con los 12 servicios
corriendo contra una base recién cargada (`dump_completo.sql` hasta la migración 026, más las
semillas) y el Redis de `infra/docker-compose.yml`. Cada servicio se conectó con su propio rol
de PostgreSQL (`svc_<servicio>`). Los pasos exactos están en la sección "Docker" de
`docs/INSTALACION.md`.

En ninguna captura aparece un token completo ni una contraseña: Swagger muestra el token como
`******` y se ocultó el bloque `curl`, que lo repite.

## Pruebas

| Archivo | Qué es | Resultado |
|---|---|---|
| [`pruebas/pytest_microservicios.txt`](pruebas/pytest_microservicios.txt) | Salida de `python -m pytest microservicios -q -rx` | 291 pasan, 3 `xfail` |
| [`pruebas/roles_postgres.txt`](pruebas/roles_postgres.txt) | Permisos de la migración 026 probados en la base real, rol por rol, dentro de `BEGIN … ROLLBACK` | 21 de 21 OK; `epidemia_app` conserva sus permisos; la 026 corre dos veces sin error |

Los 3 `xfail` documentan el mismo bug pendiente: `epidemia_comun.formatos.a_xml` usa claves
como `0-19` como etiqueta y el XML queda mal formado (ver `docs/MANUAL_TECNICO.md`, §14).

## Capturas de Swagger

Una carpeta por servicio en `servicios/`. En cada una:

- `health.png`: `/health?format=json` con PostgreSQL y Redis en `true`.
- `xml.png`: la ruta ejecutada en Swagger sin `?format` y con `Accept: application/xml`.
- `json.png`: la misma ruta con `?format=json`.

Las rutas protegidas se ejecutaron con el token de `admin` (ADMINISTRADOR), obtenido de `auth`.

| Servicio | Puerto | Ruta | Token | XML | JSON |
|---|---|---|---|---|---|
| [`auth`](servicios/auth/) | 5201 | `GET /api/v1/auth/captcha` | No | 200 | 200 |
| [`sesiones`](servicios/sesiones/) | 5202 | `GET /api/v1/sessions/current` | Sí | 200 | 200 |
| [`usuarios`](servicios/usuarios/) | 5203 | `GET /api/v1/users` | Sí (ADMINISTRADOR) | 200 | 200 |
| [`roles`](servicios/roles/) | 5204 | `GET /api/v1/roles` | Sí (ADMINISTRADOR) | 200 | 200 |
| [`enfermedades`](servicios/enfermedades/) | 5211 | `GET /api/v1/diseases/1` | No | 200 | 200 |
| [`parametros`](servicios/parametros/) | 5212 | `GET /api/v1/diseases/4/parameters` | No | 200 | 200 |
| [`regiones`](servicios/regiones/) | 5213 | `GET /api/v1/regions/2` | No | 200 | 200 |
| [`poblacion`](servicios/poblacion/) | 5214 | `GET /api/v1/regions/2/population` | No | 200 | 200 |
| [`tipos-intervencion`](servicios/tipos-intervencion/) | 5215 | `GET /api/v1/intervention-types` | No | 200 | 200 |
| [`indicadores`](servicios/indicadores/) | 5251 | `GET /api/v1/dashboard/indicators` | No | 200 | 200 |
| [`series`](servicios/series/) | 5252 | `GET /api/v1/series/cases/by-age?days=90` | Sí | 200 | 200 |
| [`zonas`](servicios/zonas/) | 5253 | `GET /api/v1/zones?days=90&size=3` | Sí | 200 | 200 |

Por el bug de `a_xml`, en `enfermedades` se capturó el detalle (el listado incluye
`letalidad_por_edad`) y en `parametros` la enfermedad 4 (Dengue), que no la tiene. En XML
siguen mal formados `GET /api/v1/diseases`, los parámetros de COVID-19 e influenza y
`GET /api/v1/regions/{id}/age-groups`; en JSON responden bien.
