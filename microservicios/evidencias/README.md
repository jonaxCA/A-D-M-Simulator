# EPIDEMIA - Servicio evidencias

El servicio de los archivos (D30). Guarda en el bucket de Cloud Storage dos cosas:
- las fotos (JPEG, PNG o WebP) y los PDF de los casos, en la tabla `case_attachments`;
- el reporte (PDF) de una comparación, en la tabla `comparison_reports` (migración 039, D35).

Cada archivo pesa hasta 20 MB. La base guarda solo su ruta, tipo, tamaño, huella SHA-256, quién lo subió y cuándo. Todo es privado: se abre con una URL firmada que vence en 15 minutos (RNF-D17) o se descarga con token.

- Puerto externo: 5224. Puerto interno en Docker: 8000.
- Contrato en `docs/contratos/evidencias/openapi.json`, con un ejemplo JSON y uno XML por ruta en `ejemplos/`, salvo la descarga, que regresa el archivo.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/cases/{case_id}/attachments` | CAPTURISTA, solo en los casos que reportó (D1: el ADMINISTRADOR no captura) | Guarda el archivo que viene **tal cual en el cuerpo**. **201**, o **200** si esa foto ya estaba en el caso |
| GET | `/api/v1/cases/{case_id}/attachments` | Los cuatro roles que leen casos | Las evidencias del caso, de la más vieja a la más nueva |
| GET | `/api/v1/attachments/{id}` | Los cuatro | Tipo, tamaño, huella, quién la subió y cuándo |
| GET | `/api/v1/attachments/{id}/url` | Los cuatro | URL firmada para abrirla sin token, y cuándo vence |
| GET | `/api/v1/attachments/{id}/content` | Los cuatro | El archivo, con su tipo, leído del bucket |
| DELETE | `/api/v1/attachments/{id}` | ADMINISTRADOR | Borra el registro y el objeto |
| POST | `/api/v1/reports?runs=12,15[&title=…]` | ANALISTA y ADMINISTRADOR (`reports.upload`) | Guarda el PDF del reporte de una comparación. **201**, o **200** si ese PDF ya estaba con esas corridas |
| GET | `/api/v1/reports[?runs=12]` | Los roles con `reports.read`: EPIDEMIOLOGO, ANALISTA, ADMINISTRADOR, INVESTIGADOR y AUTORIDAD_SANITARIA | Los 100 más recientes; con `runs`, los que comparan al menos esas corridas |
| GET | `/api/v1/reports/{id}` | Los mismos | Corridas, título, tamaño, huella, quién y cuándo |
| GET | `/api/v1/reports/{id}/url` | Los mismos | URL firmada del PDF y cuándo vence (RF-F17) |
| DELETE | `/api/v1/reports/{id}` | ADMINISTRADOR | Borra el registro y el objeto |

**Cómo se sube:**
- El cuerpo es el archivo, no un formulario multipart. Desde OkHttp: `file.asRequestBody("image/jpeg".toMediaType())`. El `Content-Type` puede ser el del archivo o `application/octet-stream`. El tipo lo decide el contenido, no el encabezado ni la extensión.
- **Huella (RNF-C09):** si el cliente manda `X-Content-SHA256` con la SHA-256 del archivo y no coincide con lo que llegó, responde 422. La huella siempre se guarda.
- **Reintentos:** la misma foto subida otra vez al mismo caso responde 200 con la que ya estaba, así que la app puede reintentar sin miedo a duplicarla. En otro caso sí es otra evidencia. Con los reportes pasa igual: mismo PDF y mismas corridas.
- **Bucket caído (RNF-C19):** si el bucket no responde, la subida da 503 `SERVICIO_NO_DISPONIBLE` con `Retry-After` y no queda ningún registro. El caso ya existe en `casos` y no se toca, y la app conserva la foto para reintentar.

**Cómo se abre:**
- `privacy` queda en `privado`.
- La URL firmada es de lectura y vence en 15 minutos. Ninguna es permanente, y la respuesta lleva `Cache-Control: private, no-store`.
- La descarga por `/content` lleva `Cache-Control: private, no-store` y `X-Content-Type-Options: nosniff`.

**Otros:**
- Borrar es para errores, como una foto con datos personales. La bitácora conserva su huella.
- Un caso capturado sin conexión no tiene `id` hasta que se sincroniza: la app sube sus fotos con el `case_id` que regresa el lote.
- La comparación no se guarda en ningún lado, así que un reporte se identifica por sus corridas (`run_ids`), que tienen que existir en `simulation_runs`. La web y el escritorio usan la misma ruta (D35). La web no importa `epidemia_comun`: sube por HTTP (D36).

| Caso | Respuesta |
|------|-----------|
| Archivo vacío, de un tipo no permitido (un reporte solo es PDF) o enviado como formulario; huella que no coincide; `runs` vacío, inválido o con corridas que no existen; id inválido | 422 `DATOS_INVALIDOS` |
| Archivo de más de 20 MB | 413 `DATOS_INVALIDOS` |
| El rol no puede, o el caso lo reportó otra persona | 403 `PERMISO_INSUFICIENTE` |
| No existe el caso, la evidencia, el reporte o su objeto | 404 `NO_ENCONTRADO` |
| Redis, PostgreSQL o el bucket caídos | 503 `SERVICIO_NO_DISPONIBLE` |

## Cómo funciona

Las reglas están en `datos.py` (evidencias) y `reportes.py`. Antes vivían en `backend_web/evidencias.py` (E8). Sus pruebas contra la base están en `tests/test_evidencias_bd.py`. El bucket se usa con la interfaz de archivos de `epidemia_comun` (`archivos.py`; ver «Archivos» en `microservicios/comun/README.md`).

1. Revisa el caso, o las corridas, y quién lo pide antes de leer el cuerpo. No lee más de 20 MB.
2. Un candado de la transacción (`pg_advisory_xact_lock`) sobre la huella hace que dos subidas del mismo archivo se esperen, y la segunda encuentra la primera.
3. Sube el objeto y luego escribe su registro, con el `CREATE` en la bitácora en la misma transacción. Si el registro falla, borra el objeto.
   - Las evidencias van a `evidencias/<case_id>/<uuid>.<ext>`. Las subidas antes de D2 conservan `evidence/...`.
   - Los reportes van a `reportes/<primera corrida>/<uuid>.pdf`.
4. Borrar quita el registro, con su `DELETE` en la bitácora, y ya confirmado, el objeto. Si el bucket no responde en ese momento, el objeto queda huérfano y se anota en el registro del servicio.

## Variables

| Variable | Para qué |
|----------|----------|
| `DATABASE_URL` | Rol `svc_evidencias` (migraciones 032 y 039) |
| `JWT_SECRET_KEY` y `REDIS_URL` | Lo de todos los servicios. Opcionales: `JWT_ISSUER` y `JWT_AUDIENCE` |
| `ARCHIVOS` | `gcs` en el compose y en GCP. `disco` para correrlo sin bucket, con `ARCHIVOS_DIR`; así no firma URLs |
| `BUCKET_NOMBRE` | El bucket: `epidemia-archivos` en el emulador; en GCP, el que crea `infra/crea_bucket.sh` |
| `STORAGE_EMULATOR_HOST` | `http://bucket:4443` en el compose (el emulador). Vacía en GCP |
| `BUCKET_URL_PUBLICA` | Con el emulador, el host que va en las URLs firmadas (`http://localhost:4443`), para que las abra el navegador |
| `DEPENDENCIAS=bucket` | Pone el bucket en su `/health` |

En GCP, las credenciales son las de la cuenta de servicio de la máquina, sin llaves en el `.env`. Ver `infra/docker-compose.gcs.yml` y `docs/DESPLIEGUE_GCP.md`.

## Probarlo

```bash
python -m pytest microservicios/evidencias
ARCHIVOS=disco ARCHIVOS_DIR=/tmp/archivos python -m microservicios.evidencias.app
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: image/jpeg" \
     -H "X-Content-SHA256: $(sha256sum foto.jpg | cut -d' ' -f1)" \
     --data-binary @foto.jpg "http://127.0.0.1:5224/api/v1/cases/418/attachments?format=json"
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5224/api/v1/attachments/12/url?format=json"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/pdf" \
     --data-binary @comparacion.pdf "http://127.0.0.1:5224/api/v1/reports?runs=12,15&format=json"
```

`microservicios/pruebas_integracion/contenedores/test_compose_evidencias.py` prueba lo mismo contra el compose, con el emulador, incluso con el bucket detenido.
