# D28 - Qué datos van a MongoDB

Fecha: 2026-11-11 · Estado: Aceptada

## Contexto
La rúbrica pide almacenamiento real en MongoDB con inserción, consulta, actualización, agregación e índices. La v2 propone candidatos (§9.1).

## Opciones consideradas
Candidatos:
- el historial de `estado-servicios`, hoy en Redis;
- los lotes crudos de `sincronizacion`;
- las series diarias de las corridas del ABM.

## Decisión
Las dos colecciones estado-servicios y series diarias de las corridas del ABM.

- historial_servicios: el historial de estado-servicios, que hoy vive en Redis y es lo único que D19 admite perder. Es de alta frecuencia y se consulta agregado: disponibilidad por servicio, latencia promedio, último error y dependencia caída. Alimenta directo el panel de monitoreo que pide la rúbrica.
- series_corridas: un documento por día de cada corrida, con su run_id, motor, semilla y compartimentos por grupo de edad. Funciona desde hoy con el SEIR, sin esperar al ABM, y es la base del volumen de D29. Sustituye a simulation_results como tabla puente.

Los lotes crudos de sincronizacion quedan como tercera colección solo si sobra tiempo.
Lo que hay que construir:
- Contenedor de MongoDB en infra/docker-compose.yml y su cliente en microservicios/comun.
- Índices: {servicio, fecha} en el historial con TTL (por ejemplo, 30 días); {run_id, dia} y {batch_id} en las series.
- Campo version_esquema en cada documento, para el versionamiento que pide el diseño de MongoDB.
- /health/mongodb en fabrica.py y la columna de MongoDB en el panel de estado-servicios.
- Demostración de inserción, consulta, actualización, agregación, índices, filtrado y recuperación por run_id.


## Consecuencias
Define las colecciones, los índices y el versionamiento (diseño de MongoDB que pide la rúbrica), y agrega un contenedor y una dependencia nuevos. Depende de D21.

Depende de: D21
