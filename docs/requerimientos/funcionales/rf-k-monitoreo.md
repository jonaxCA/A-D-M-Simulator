> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-K: Monitoreo del sistema

Función de soporte: la salud de los servicios y el directorio que usan las apps para encontrarlos. El detalle está en [`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md) (§9). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- Los 31 servicios y su ruta `/health`.
- Redis (el estado y, hoy, el historial) y MongoDB (`historial_servicios`, D28).
- Servicio: `estado-servicios`. La consola de pruebas muestra el panel.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-K01 | `estado-servicios` sondea la salud de todos los servicios cada pocos segundos | El intervalo se configura (`SONDEO_SEGUNDOS`, 10 por omisión) | Soporte | Monitoreo | Alta | Hecho |
| RF-K02 | Hay un panel con el estado de cada servicio: `ok`, `degradado` o `caido` | Por servicio se ven el estado, la última revisión, la versión y las dependencias caídas, y un resumen de cuántos hay en cada estado | Soporte | Monitoreo | Alta | Hecho |
| RF-K03 | El historial de salud de cada servicio se guarda y se consulta | Cada sondeo es un documento de `historial_servicios` en MongoDB, que vive 30 días. Se consulta la disponibilidad y la latencia por servicio | Soporte | Monitoreo, Bases de datos | Alta | Hecho (D-1): `historial_servicios` con TTL de 30 días; `/history` da los últimos 30 sondeos y el resumen de 24 h |
| RF-K04 | El panel muestra la latencia de cada servicio | Cada sondeo mide cuánto tardó la respuesta | Soporte | Monitoreo | Media | Hecho |
| RF-K05 | El panel detecta qué dependencia falló | Marca caídas PostgreSQL, Redis, MongoDB o el bucket, según cuál no responda | Soporte | Monitoreo | Alta | En parte: detecta PostgreSQL, Redis, MongoDB y el bucket cuando el servicio los declara; falta que el bloque D los conecte (N4); verificado el 2026-11-16 con MongoDB y bucket de la demostración |
| RF-K06 | Avisar cuando un servicio cae | Los ADMINISTRADOR reciben un aviso `SYSTEM` cuando un servicio cae, se degrada o se recupera y el cambio dura 30 s; sin repetirlo y sin llenar la bandeja | Soporte | Monitoreo, Notificaciones | Media | Hecho (F7, 2026-11-21): `estado-servicios/alertas.py`; regresó del fuera de alcance |
| RF-K08 | Los registros de todos los contenedores se juntan en un solo lugar en la nube | Cloud Logging, con el `X-Correlation-ID` que ya llevan | Soporte | Monitoreo, Infraestructura | Alta | Hecho: `infra/docker-compose.cloud-logging.yml` (2026-11-20) |
| RF-K10 | Cada servicio responde su salud en `/health` | Informa el proceso, PostgreSQL, MongoDB, Redis, el bucket, el tiempo de respuesta y la versión. Un servicio que no usa MongoDB o el bucket lo dice | Soporte | Monitoreo, Microservicios | Alta | En parte: informa PostgreSQL, Redis, MongoDB, el bucket (o `no_usa`), el tiempo y la versión; MongoDB con el `ping` de `mongo.py` y el bucket con `archivos.ping()` (D2); verificado el 2026-11-16 con MongoDB y bucket de la demostración |
| RF-K11 | Las apps preguntan a `estado-servicios` dónde está cada servicio | Responde la URL pública de cada uno. Detrás de nginx da `https://<dominio>/<servicio>` (D25) | 1.1, 2.1 | Monitoreo, Microservicios | Alta | En parte: con `URL_PUBLICA=https://<dominio>/{servicio}` da la URL detrás de nginx; falta nginx (S6) |
| RF-K12 | El panel cuenta los errores de cada servicio | Se ve el número de errores junto al estado | Soporte | Monitoreo | Alta | Hecho (N4) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-K07 | CPU, memoria y disco de las máquinas | Se miden en las pruebas de volumen y de carga (RNF-A16 y RNF-A17), no en el panel |
| RF-K09 | Vista de monitoreo con más detalle para el administrador | El panel es uno solo, en la consola de pruebas |
