> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-C: Vigilancia epidemiológica (captura en campo)

Es el proceso **P1** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md): el CAPTURISTA registra casos con su ubicación y fotos desde la app Android, aunque no tenga conexión, y los manda después. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y teléfono registrado), RF-B (catálogos) y RF-I (la app).
- PostgreSQL: `cases`, `case_attachments`, `vaccine_lots`.
- Redis: candado y resultado de cada lote.
- Cloud Storage: las fotos (D30).
- Servicios: `sincronizacion`, `casos`, `evidencias`, `vacunas`, `notificaciones`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-C01 | La app registra un caso con enfermedad, municipio, fecha, edad, sexo, resultado de la prueba y severidad. No se captura el nombre ni otro dato que identifique a la persona | El caso queda pendiente en el teléfono con su `local_uuid` | 1.4 | Móvil | Alta | Hecho |
| RF-C02 | La app toma la ubicación del GPS al capturar | El caso guarda latitud y longitud | 1.4 | Móvil | Alta | Hecho |
| RF-C03 | La app toma fotos del caso y las sube cuando el caso ya existe en el servidor | Las fotos se reducen a 1600 px y pierden el EXIF. `evidencias` guarda en `case_attachments` la ruta, el tipo, el tamaño, la huella, la privacidad, quién y cuándo; queda `CREATE` en la auditoría. El archivo va al bucket | 1.5, 1.7 | Móvil, Microservicios | Alta | Hecho: el archivo va al bucket (D2, 2026-11-22); en local, el emulador del compose. En GCP, al crear el bucket (`infra/crea_bucket.sh`) |
| RF-C04 | La app lee el QR de un lote de vacuna y lo registra | `vacunas` da de alta el lote en `vaccine_lots`; queda `CREATE` en la auditoría. Un lote caducado no se registra (RN-10) | 1.8 | Móvil, Microservicios | Media | Hecho |
| RF-C05 | La app lee también el código de barras de un lote de vacuna | Igual que RF-C04 | 1.8 | Móvil | Media | Hecho |
| RF-C06 | El formulario se valida en el teléfono | Un campo obligatorio vacío o un valor fuera de rango no deja guardar y dice por qué | 1.4 | Móvil | Alta | Hecho |
| RF-C07 | La captura funciona sin conexión | Sin red, el caso y sus fotos se guardan en el teléfono (Room) y no se pierden al cerrar la app | 1.4, 1.5 | Móvil | Alta | Hecho |
| RF-C08 | Con red, la app manda sola los casos pendientes, en lotes de hasta 100 | `sincronizacion` crea los casos por medio de `casos`; quedan `SYNC` de `sync_batches` y `CREATE` de `cases` en la auditoría | 1.6 | Móvil, Microservicios | Alta | Hecho |
| RF-C09 | Un caso no se duplica aunque el lote se mande dos veces | Un reintento usa el mismo lote. El servidor no repite un `local_uuid` y responde el resultado guardado del lote (7 días en Redis) | 1.6 | Microservicios, Bases de datos | Alta | Hecho |
| RF-C10 | El servidor asigna su identificador a cada caso | La app guarda el `case_id` como comprobante del envío | 1.6 | Microservicios | Alta | Hecho |
| RF-C12 | El servidor valida cada caso al recibirlo | Un caso con datos inválidos se rechaza con su motivo, sin detener el resto del lote; la app lo muestra como rechazado | 1.6 | Microservicios | Alta | Hecho |
| RF-C13 | La app aplica dosis a un lote de vacuna | `vacunas` suma a `doses_used`; queda `UPDATE` en la auditoría. No se aplica a un lote caducado ni más dosis de las que tiene (RN-11, RN-30) | 1.8 | Móvil, Microservicios | Media | Hecho |
| RF-C14 | La app muestra qué se envió, qué se rechazó y qué falta | Cada caso aparece como enviado, rechazado o pendiente | 1.6 | Móvil | Alta | Hecho |
| RF-C19 | Cuando un lote trae casos nuevos, se avisa a los EPIDEMIOLOGO | `sincronizacion` crea un aviso por lote, no uno por caso, por medio de `notificaciones`. Un reintento del mismo lote no vuelve a avisar (D32) | 1.6 | Microservicios | Alta | Hecho |
| RF-C20 | La web muestra la foto de un caso con una URL firmada | Solo un rol con permiso recibe la URL, y vence en minutos | 1.9 | Web, Microservicios | Alta | En parte: `GET /api/v1/attachments/{id}/url` de `evidencias` (D2) responde la URL, que vence en 15 minutos; falta la web (C) |
| RF-C11 | Corregir un caso ya registrado, sin sobrescribir en silencio lo que cambió otra persona | `PATCH /cases/{id}` con `If-Match` (la versión que se leyó): el EPIDEMIOLOGO corrige cualquier caso pendiente o validado y el CAPTURISTA los suyos pendientes. Si el caso cambió, 412 y nada se toca; la sincronización lo regresa como conflicto con el caso actual. Cada cambio queda en el historial (`case_history`) | 1.6, 1.9 | Microservicios, Móvil | Alta | Hecho en el servidor (D47, 2026-11-22); falta en la móvil (B4) |
| RF-C15 | Validar, descartar o marcar como duplicado un caso, con su motivo | `POST /cases/{id}/status`, solo el EPIDEMIOLOGO; descartar, duplicado y reabrir piden motivo, y duplicado el caso original. Quien lo capturó recibe `CASE_REJECTED` | 1.9 | Microservicios | Alta | Hecho en el servidor (D47, 2026-11-22); falta en la web o el escritorio |
| RF-C22 | Cada enfermedad tiene su formulario de captura, con versiones, validaciones y campos obligatorios | `casos` guarda las versiones (borrador, publicado, retirado; lo publicado no cambia), la app baja las vigentes y cada caso trae la versión con que se capturó y sus respuestas, validadas contra ella (D48) | 1.3, 1.4, 1.6 | Microservicios, Móvil | Alta | Hecho en el servidor (D48, 2026-11-22); falta en la móvil (B4) |
| RF-C23 | Se avisa de los casos con datos incompletos | Quien capturó un caso sin edad, sexo, inicio de síntomas, resultado, gravedad o ubicación recibe un aviso con lo que falta (uno por captura o por lote) y `GET /cases/incomplete` los lista | 1.6 | Microservicios, Móvil | Media | Hecho en el servidor (D49, 2026-11-22); falta el panel de la móvil (B4) |
| RF-C24 | Campañas de salud, con aviso a los capturistas | El EPIDEMIOLOGO o el ADMINISTRADOR crea, edita o cancela una campaña (enfermedad, municipio o estado, fechas); los CAPTURISTA reciben un aviso. Sin coberturas | Soporte | Microservicios | Media | Hecho en el servidor (D49, 2026-11-22) |
| RF-C25 | Cada persona apaga los avisos que no quiere | De los que le tocan por su perfil; `SYSTEM` no se apaga, y un aviso apagado no se crea | Soporte | Microservicios | Media | Hecho en el servidor (D49, 2026-11-22); ninguna app tiene todavía la pantalla |
| RF-C21 | Un teléfono revocado deja de sincronizar | `sincronizacion` rechaza el lote; los casos vuelven a pendientes en el teléfono y la app cierra la sesión | 1.6 | Microservicios, Móvil | Media | Hecho |
| RF-C16 | Cargar series históricas para calibrar. Reabierto por D50 | La 061 trae la serie de D50 (casos confirmados de COVID-19 en Nuevo León por semana, DGE, del 2020-03-01 al 2020-07-26), con su fuente, licencia, corte y huella; otras series entran por `importacion` (D53). Nunca registros por persona, y `cases` no calibra (063) | Soporte | Bases de datos, Microservicios | Media | Hecho (D50, D53) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-C17 | Agregar casos por AGEB | El catálogo llega a municipio. El tablero y el mapa agregan por municipio (RF-G03) |
| RF-C18 | No publicar zonas con menos de N casos | No hay umbral definido ni decisión que lo pida |
