> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-K: Monitoreo del sistema

Función de soporte: la salud de los servicios y el directorio que usan las apps para encontrarlos. El detalle está en [`arquitectura_v3.md`](../../arquitectura/arquitectura_v3.md) (§9). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- Los 29 servicios y su ruta `/health`.
- Redis (el estado y, hoy, el historial) y MongoDB (`historial_servicios`, D28).
- Servicio: `estado-servicios`. La consola de pruebas muestra el panel.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-K01 | `estado-servicios` sondea la salud de todos los servicios cada pocos segundos | El intervalo se configura (`SONDEO_SEGUNDOS`, 10 por omisión) | Soporte | Monitoreo | Alta | Hecho |
| RF-K02 | Hay un panel con el estado de cada servicio: `ok`, `degradado` o `caido` | Por servicio se ven el estado, la última revisión, la versión y las dependencias caídas, y un resumen de cuántos hay en cada estado | Soporte | Monitoreo | Alta | Hecho |
| RF-K03 | El historial de salud de cada servicio se guarda y se consulta | Cada sondeo es un documento de `historial_servicios` en MongoDB, que vive 30 días. Se consulta la disponibilidad y la latencia por servicio | Soporte | Monitoreo, Bases de datos | Alta | En parte: hoy el historial está en Redis; falta MongoDB (D-1, D28) |
| RF-K04 | El panel muestra la latencia de cada servicio | Cada sondeo mide cuánto tardó la respuesta | Soporte | Monitoreo | Media | Hecho |
| RF-K05 | El panel detecta qué dependencia falló | Marca caídas PostgreSQL, Redis, MongoDB o el bucket, según cuál no responda | Soporte | Monitoreo | Alta | En parte: detecta PostgreSQL y Redis; faltan MongoDB y el bucket (N4) |
| RF-K08 | Los registros de todos los contenedores se juntan en un solo lugar en la nube | Propuesta: Cloud Logging, con el `X-Correlation-ID` que ya llevan | Soporte | Monitoreo, Infraestructura | Alta | Falta (N6) |
| RF-K10 | Cada servicio responde su salud en `/health` | Informa el proceso, PostgreSQL, MongoDB, Redis, el bucket, el tiempo de respuesta y la versión. Un servicio que no usa MongoDB o el bucket lo dice | Soporte | Monitoreo, Microservicios | Alta | En parte: informa PostgreSQL, Redis y la versión; faltan MongoDB, el bucket y el tiempo (N3) |
| RF-K11 | Las apps preguntan a `estado-servicios` dónde está cada servicio | Responde la URL pública de cada uno. Detrás de nginx da `https://<dominio>/<servicio>` (D25) | 1.1, 2.1 | Monitoreo, Microservicios | Alta | En parte: hoy da `host:puerto`; falta nginx (S6) |
| RF-K12 | El panel cuenta los errores de cada servicio | Se ve el número de errores junto al estado | Soporte | Monitoreo | Alta | Falta (N4) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-K06 | Avisar cuando un servicio cae | El panel lo muestra; no hay envío de alertas |
| RF-K07 | CPU, memoria y disco de las máquinas | Se miden en las pruebas de volumen y de carga (RNF-A16 y RNF-A17), no en el panel |
| RF-K09 | Vista de monitoreo con más detalle para el administrador | El panel es uno solo, en la consola de pruebas |
