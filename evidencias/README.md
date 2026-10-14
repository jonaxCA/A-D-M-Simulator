# Evidencias — segundo parcial

Evidencia de funcionamiento de los microservicios. Cada archivo dice la fecha y el commit con
que se tomó.

**Nunca** se guardan aquí contraseñas, tokens (`access_token`, `refresh_token`,
`Authorization`), secretos ni el contenido de un `.env`. En capturas y archivos, se reemplazan
por `JWT_DE_EJEMPLO`, `REFRESH_DE_EJEMPLO` o `***`.

## Contenido

```text
evidencias/
  README.md
  pruebas/          pruebas automatizadas y verificación de privilegios PostgreSQL
  servicios/        12 carpetas con health.png, json.png y xml.png
  swagger/          capturas adicionales de los servicios que las incluyen
```

En la rama del grupo 14:00 hay tres imágenes por cada uno de los 12 servicios,
pero esto no prueba por sí solo que todos sus endpoints y escrituras hayan sido validados.
Las peticiones y respuestas completas deben conservarse y verificarse por operación.

| Archivo o directorio | Alcance | Estado |
|---|---|---|
| `pruebas/pruebas_unitarias_2026-10-13.txt` | Ejecución previa: 198 pruebas aprobadas, sin fallos informados | Histórico |
| `pruebas/pytest_microservicios.txt` | Última ejecución anterior a corregir XML: **291 passed, 3 xfailed, 34 subtests passed** | Histórico |
| `pruebas/pytest_microservicios_xml_corregido.txt` | Nueva ejecución después de corregir XML: 307 passed, 34 subtests passed in 1.64s | Histórico |
| `pruebas/pytest_microservicios_xsd.txt` | Ejecución con la validación XSD (D15): **322 passed**, con el detalle de las 15 pruebas de `test_xsd.py` | Histórico |
| `pruebas/pytest_microservicios_integracion.txt` | Resultado actual, con las pruebas de integración iniciales: **325 passed**, con el detalle de las 3 de `pruebas_integracion/` | Registrada |
| `pruebas/roles_postgres.txt` | Privilegios de roles por servicio: 21/21, según el registro existente | Registrado |
| `servicios/<servicio>/health.png` | Estado de salud de cada servicio | 12 imágenes |
| `servicios/<servicio>/json.png` | Respuesta en JSON de cada servicio | 12 imágenes |
| `servicios/<servicio>/xml.png` | Respuesta en XML de cada servicio | 12 imágenes |
| `swagger/` | Capturas adicionales de Swagger de algunos servicios | Parcial |

No se afirma que los 26 microservicios estén desplegados ni que se haya probado un flujo
de negocio contra los servicios desplegados. Las pruebas de integración iniciales
(`microservicios/pruebas_integracion/`) recorren el flujo de identidad con Redis y base
simulados; el flujo completo contra los contenedores debe verificarse por separado.

## Cómo se toma cada evidencia

### Pruebas (`pruebas/`)

Desde la raíz, con el entorno virtual activo (ver `docs/INSTALACION.md`, sección "Docker:
microservicios del grupo 14:00", paso 5):

```bash
python -m pytest microservicios -v
```

Cada archivo de resultados indica la fecha y el resultado de la ejecución.

### Peticiones (`peticiones/<servicio>/`)

Un archivo por operación y caso: `login_ok.md`, `login_captcha_vencido.md`,
`users_crear_sin_permiso.md`. Cada uno lleva:

1. URL completa y método.
2. Objetivo de la operación.
3. Parámetros de ruta y de consulta.
4. Encabezados (`Authorization: Bearer JWT_DE_EJEMPLO`, `Content-Type`, `Accept`).
5. Cuerpo de la petición, en JSON o XML.
6. Respuesta completa y código HTTP.
7. Qué cambió en PostgreSQL o en Redis, cuando aplique (la fila de `audit_log` o la llave
   creada, con su TTL).

Por servicio, al menos un caso de cada tipo que tenga:

- operación correcta, en JSON y en XML;
- parámetro inválido (422);
- registro inexistente (404);
- sin token (401) y sin permiso (403);
- error de negocio (409).

### Capturas (`servicios/` y `swagger/`)

- `servicios/<servicio>/`: Swagger (`http://localhost:<puerto>/docs`) o Postman, con la
  petición y la respuesta visibles, una en JSON y otra en XML. Colección de Postman:
  `docs/contratos/postman/`.
- Para contenedores: `docker ps` con los contenedores en `(healthy)` y
  `docker compose -f infra/docker-compose.yml ps` con Redis en `(healthy)`.

## Evidencia por servicio

Las imágenes existentes se marcaron, pero falta verificar las peticiones completas de cada operación.

| Servicio | Puerto | Peticiones | Captura JSON | Captura XML |
|---|---|---|---|---|
| `auth` | 5201 | [ ] | [x] | [x] |
| `sesiones` | 5202 | [ ] | [x] | [x] |
| `usuarios` | 5203 | [ ] | [x] | [x] |
| `roles` | 5204 | [ ] | [x] | [x] |
| `enfermedades` | 5211 | [ ] | [x] | [x] |
| `parametros` | 5212 | [ ] | [x] | [x] |
| `regiones` | 5213 | [ ] | [x] | [x] |
| `poblacion` | 5214 | [ ] | [x] | [x] |
| `tipos-intervencion` | 5215 | [ ] | [x] | [x] |
| `indicadores` | 5251 | [ ] | [x] | [x] |
| `series` | 5252 | [ ] | [x] | [x] |
| `zonas` | 5253 | [ ] | [x] | [x] |
