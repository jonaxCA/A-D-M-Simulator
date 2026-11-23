> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-K: Almacenamiento y datos

Dónde va cada dato y por qué. La regla está en [`brechas_v3.md`](../../arquitectura/brechas_v3.md) (§9.3) y el inventario en [`matrices_v3.md`](../../arquitectura/matrices_v3.md). Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-K01 | PostgreSQL cuida la integridad | Llaves foráneas y restricciones (`CHECK`) en las tablas; los estados válidos los fija la base | Bases de datos | Hecho |
| RNF-K02 | Un escenario no se sobrescribe | Cada cambio es una versión nueva, y la versión congela su población y sus parámetros (D5) | Bases de datos | Hecho |
| RNF-K03 | MongoDB guarda lo de alta frecuencia que se agrega más de lo que se edita (D28) | Dos colecciones: `historial_servicios` y `series_corridas`. Se demuestran inserción, consulta, actualización, agregación, índices y recuperación por `run_id` | Bases de datos | Hecho (D-1) |
| RNF-K05 | Todo lo que va a Redis tiene vencimiento | Cada llave se escribe con su tiempo de vida: captcha 300 s, sesión 8 h, resultado de lote 7 días, avance de corrida 24 h, caché de `resultados` 300 s | Bases de datos | Hecho |
| RNF-K07 | Cada dato tiene definido cuánto vive | El inventario de datos dice la retención de cada tabla, colección y archivo | Bases de datos | Falta: la retención de las tablas de PostgreSQL y de los archivos está «Por definir» en `matrices_v3.md` |
| RNF-K08 | Un registro no entra dos veces | Ver RF-C09 | Bases de datos | Hecho |
| RNF-K11 | PostgreSQL es la fuente de verdad | Si Redis o MongoDB se pierden, lo que queda en PostgreSQL basta para seguir (D19) | Bases de datos | Hecho |
| RNF-K12 | Ningún archivo va dentro de la base | PostgreSQL guarda solo el identificador, la ruta, el tipo, el tamaño, el propietario, la fecha, la huella y la privacidad. El archivo va a Cloud Storage (D30) | Bases de datos | Hecho (D2): el archivo va al bucket y la base guarda sus metadatos (`case_attachments`, `comparison_reports`) |
| RNF-K14 | Las consultas frecuentes tienen su índice | En MongoDB: `{run_id, dia}` único y `{scenario_version_id, motor, dia}` en `series_corridas` (D28: `{batch_id}` no sirve para comparar); `{servicio, fecha}` con TTL en `historial_servicios`. Se mide con y sin índice (D29) | Bases de datos | Hecho: los índices existen (`test_mongo_real.py`) y se midieron con y sin ellos: 5 ms contra 849 ms la serie de una corrida ([`docs/pruebas/volumen/2026-11-18`](../../pruebas/volumen/2026-11-18/LEEME.md)) |
| RNF-K16 | Cada tabla tiene un solo servicio dueño | Solo el dueño escribe en ella; el catálogo dice quién escribe y quién lee cada tabla | Bases de datos, Microservicios | Hecho |
| RNF-K17 | Los documentos de MongoDB llevan su versión de esquema | Cada documento tiene `version_esquema`; quien lee acepta las versiones que conoce | Bases de datos | Hecho (D-1) |
| RNF-K18 | Un solo bucket privado para los archivos | Sin lectura pública. Propuesta: los prefijos `evidencias/` y `reportes/` | Infraestructura, Bases de datos | Hecho en local con el emulador (D2): prefijos `evidencias/` y `reportes/`. En GCP lo crea `infra/crea_bucket.sh` (acceso uniforme, sin acceso público); falta correrlo (con F) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-K04 | Resultados que no se modifican | Se cubre con la versión congelada (RNF-K02) y con RNF-J12 |
| RNF-K06 | Archivar datos viejos en Cloud Storage | El volumen de D29 no lo pide |
| RNF-K09 | Respaldo diario | Ver RNF-C05 |
| RNF-K10 | Consistencia eventual en resultados | Se cubre con RNF-K11 |
| RNF-K13 | Comprimir las series | El volumen de D29 no lo pide |
| RNF-K15 | Particionar las series por periodo | El volumen de D29 no lo pide |
