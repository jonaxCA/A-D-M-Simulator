# EPIDEMIA - Servicio evidencias

Fotos (JPEG, PNG o WebP) y PDF de los casos, hasta 20 MB cada uno (tabla `case_attachments`).
El archivo vive en el volumen de Docker del servicio, en lugar de Cloud Storage; la base guarda
su ruta, tipo, tamaño y huella SHA-256.

Puerto externo: 5224; puerto interno en Docker: 8000. Contrato en
`docs/contratos/evidencias/openapi.json`, con un ejemplo JSON y uno XML por ruta en
`ejemplos/` (salvo la descarga, que regresa el archivo).

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/cases/{case_id}/attachments` | CAPTURISTA (solo en los casos que reportó) y ADMINISTRADOR | Guarda el archivo que viene **tal cual en el cuerpo**. **201**, o **200** si esa foto ya estaba en el caso |
| GET | `/api/v1/cases/{case_id}/attachments` | Los cuatro roles que leen casos | Las evidencias del caso, de la más vieja a la más nueva |
| GET | `/api/v1/attachments/{id}` | Los cuatro | Tipo, tamaño, huella, quién la subió y cuándo |
| GET | `/api/v1/attachments/{id}/content` | Los cuatro | El archivo, con su tipo |
| DELETE | `/api/v1/attachments/{id}` | ADMINISTRADOR | Borra el registro y el archivo |

- El cuerpo es el archivo, no un formulario multipart: desde OkHttp,
  `file.asRequestBody("image/jpeg".toMediaType())`. El `Content-Type` puede ser el del archivo o
  `application/octet-stream`: el tipo lo decide el contenido, no el encabezado ni la extensión.
- La misma foto subida otra vez al mismo caso responde 200 con la que ya estaba: la app puede
  reintentar una subida sin miedo a duplicarla. En otro caso, sí es otra evidencia.
- `privacy` queda en `privado`: todas se descargan con token. La descarga lleva
  `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff`.
- Borrar es para errores, como una foto con datos personales. La bitácora conserva su huella.
- Un caso capturado sin conexión no tiene `id` hasta que se sincroniza: la app sube sus fotos
  con el `case_id` que regresa el lote.

| Caso | Respuesta |
|------|-----------|
| Archivo vacío, de un tipo no permitido o enviado como formulario; id inválido | 422 `DATOS_INVALIDOS` |
| Archivo de más de 20 MB | 413 `DATOS_INVALIDOS` |
| El rol no puede, o el caso lo reportó otra persona | 403 `PERMISO_INSUFICIENTE` |
| No existe el caso, la evidencia o su archivo | 404 `NO_ENCONTRADO` |
| Redis caído | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

Las reglas están en `backend_web/evidencias.py`, con sus pruebas contra la base
(`backend_web/tests/test_evidencias.py`):

1. Revisa el caso y quién lo reportó antes de leer el cuerpo, y no lee más de 20 MB.
2. Un candado de la transacción (`pg_advisory_xact_lock`) sobre el caso y la huella hace que dos
   subidas de la misma foto se esperen; la segunda encuentra la primera.
3. Escribe el archivo en `evidence/<case_id>/<uuid>.<ext>` dentro de `EVIDENCIAS_DIR` y luego
   su registro, con el `CREATE` en la bitácora en la misma transacción. Si el registro falla,
   borra el archivo.
4. Borrar quita el registro (con su `DELETE` en la bitácora) y, ya confirmado, el archivo.

## Variables

`DATABASE_URL` (rol `svc_evidencias`, migración 032), `JWT_SECRET_KEY`, `REDIS_URL` y
`EVIDENCIAS_DIR` (en el compose, `/var/lib/epidemia/evidencias`, montada en el volumen
`evidencias-datos`); opcionales `JWT_ISSUER` y `JWT_AUDIENCE`. `docker compose down -v` borra
el volumen y, con él, los archivos.

## Probarlo

```bash
python -m pytest microservicios/evidencias
python -m unittest backend_web.tests.test_evidencias
EVIDENCIAS_DIR=/tmp/evidencias python -m microservicios.evidencias.app
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: image/jpeg" \
     --data-binary @foto.jpg "http://127.0.0.1:5224/api/v1/cases/418/attachments?format=json"
curl -H "Authorization: Bearer $TOKEN" -o foto.jpg "http://127.0.0.1:5224/api/v1/attachments/12/content"
```
