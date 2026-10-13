# Evidencias — segundo parcial

Evidencia de funcionamiento de los microservicios. Cada archivo dice la fecha y el commit con
que se tomó.

**Nunca** se guardan aquí contraseñas, tokens (`access_token`, `refresh_token`,
`Authorization`), secretos ni el contenido de un `.env`. En capturas y archivos, se reemplazan
por `JWT_DE_EJEMPLO`, `REFRESH_DE_EJEMPLO` o `***`.

## Contenido

```
evidencias/
  README.md
  pruebas/          resultado de las pruebas automáticas
  peticiones/       petición y respuesta reales de cada servicio, en JSON y XML
  capturas/         capturas de Swagger, Postman y del estado de los contenedores
```

`peticiones/` y `capturas/` se crean al subir su primera evidencia.

| Carpeta | Archivo | Qué es | Estado |
|---|---|---|---|
| `pruebas/` | `pruebas_unitarias_2026-10-13.txt` | Salida de `pytest -v` de la biblioteca común y de los 12 servicios: **198 pasan, 0 fallan**. Base de datos y Redis simulados. | Hecho |
| `peticiones/` | `<servicio>/<operacion>_<caso>.md` | Petición y respuesta contra los servicios levantados con la base real | Pendiente |
| `capturas/` | `<servicio>/<operacion>_<formato>.png` | Swagger o Postman ejecutando la petición | Pendiente |
| `capturas/` | `docker/` | `docker ps` y `docker compose ps` con los contenedores `healthy` | Pendiente |

## Cómo se toma cada evidencia

### Pruebas (`pruebas/`)

Desde la raíz, con el entorno virtual activo, una carpeta a la vez (ver
`docs/INSTALACION.md`, Paso M6):

```bash
python -m pytest microservicios/<carpeta> -v -p no:cacheprovider --no-header
```

El archivo se nombra `pruebas_unitarias_<AAAA-MM-DD>.txt` y empieza con la fecha, la rama y el
commit.

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

### Capturas (`capturas/`)

- `capturas/<servicio>/`: Swagger (`http://127.0.0.1:<puerto>/docs`) o Postman, con la
  petición y la respuesta visibles, una en JSON y otra en XML. Colección de Postman:
  `docs/contratos/postman/`.
- `capturas/docker/`: `docker ps` con los contenedores en `(healthy)` y
  `docker compose -f infra/docker-compose.yml ps` con Redis en `(healthy)`.

## Pendiente por servicio

Marca cada casilla al subir su evidencia.

| Servicio | Puerto | Peticiones | Captura JSON | Captura XML |
|---|---|---|---|---|
| `auth` | 5201 | [ ] | [ ] | [ ] |
| `sesiones` | 5202 | [ ] | [ ] | [ ] |
| `usuarios` | 5203 | [ ] | [ ] | [ ] |
| `roles` | 5204 | [ ] | [ ] | [ ] |
| `enfermedades` | 5211 | [ ] | [ ] | [ ] |
| `parametros` | 5212 | [ ] | [ ] | [ ] |
| `regiones` | 5213 | [ ] | [ ] | [ ] |
| `poblacion` | 5214 | [ ] | [ ] | [ ] |
| `tipos-intervencion` | 5215 | [ ] | [ ] | [ ] |
| `indicadores` | 5251 | [ ] | [ ] | [ ] |
| `series` | 5252 | [ ] | [ ] | [ ] |
| `zonas` | 5253 | [ ] | [ ] | [ ] |
