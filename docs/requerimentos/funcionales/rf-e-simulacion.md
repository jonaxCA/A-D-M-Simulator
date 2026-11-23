> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-E: Simulación

Es la primera mitad del proceso **P3** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md): el ANALISTA lanza réplicas de las versiones aprobadas y el simulador las corre en segundo plano. El algoritmo está en [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles), RF-D (versiones aprobadas) y RF-H (la app de escritorio).
- PostgreSQL: `simulation_batches`, `simulation_runs` (con el resumen, 038), `notifications`.
- Redis: candado por versión, una cola por motor y el avance de cada corrida.
- MongoDB: `series_corridas` (D28).
- Servicios: `corridas`, `simulador`, `notificaciones`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-E01 | El ANALISTA lanza corridas desde la app de escritorio. La web no lanza (D4) | Solo se lanza una versión `aprobado` (D5, RN-13); con otra, `corridas` responde un error. Queda `RUN` de `simulation_run` en la auditoría | 3.1 | Escritorio, Microservicios | Alta | Hecho |
| RF-E02 | Lanzar no espera a que la corrida termine | `corridas` responde 202, registra la corrida `encolado` y la mete a la cola de su motor en Redis | 3.1 | Microservicios | Alta | Hecho |
| RF-E03 | El número de réplicas se elige: 30 por omisión y 100 como máximo (D8) | Con menos de 30, la app pide confirmación. Más de 100 no se acepta | 3.1 | Escritorio, Microservicios | Alta | En parte: `corridas` valida el tope de 100 (D8, migración 036); los lotes con varias réplicas llegan con la app de escritorio |
| RF-E04 | Las réplicas usan las semillas 1 a N, las mismas en todas las versiones comparadas (D8) | Dos versiones lanzadas con N réplicas tienen las mismas N semillas | 3.1 | Microservicios | Alta | Hecho |
| RF-E05 | El avance de cada corrida se puede seguir | El simulador publica el avance en Redis y `corridas` lo entrega junto con el estado | 3.2, 3.3 | Microservicios, Escritorio | Alta | Hecho |
| RF-E06 | El ANALISTA cancela una corrida, o todas las que esperan de una versión | La corrida pasa a `cancelado`; queda `CANCEL` en la auditoría | 3.3 | Escritorio, Microservicios | Media | Hecho |
| RF-E07 | El ANALISTA reintenta una corrida fallida sin duplicar resultados (D44) | `POST /api/v1/runs/{id}/retry` regresa la misma corrida a `encolado`, con su semilla y prioridad, solo si estaba `fallido` (409 en otro caso); queda `RUN` en la auditoría y la serie se reescribe por `{run_id, dia}` (D38). Un reintento automático no aplica: con la misma semilla repetiría el mismo error | 3.3 | Microservicios | Media | Hecho (servicio); el escritorio todavía no ofrece «Reintentar» |
| RF-E08 | Prioridad en la cola (D44) | `priority` `baja`, `normal` o `alta` (migración 054); el simulador toma antes las altas, y dentro de cada prioridad en orden de llegada. Solo el ADMINISTRADOR pide `alta`. No hay reparto entre usuarios (RNF-B08 sigue fuera) | 3.1 | Microservicios | Media | Hecho (servicio); el escritorio todavía no la ofrece |
| RF-E14 | Tiempo estimado para terminar (D44) | `GET /api/v1/runs/{id}` da `queue_position` y `estimated_seconds`, la mediana de las últimas 50 corridas completadas con el mismo motor, población y horizonte; sin historial, `null` con `estimate_reason` | 3.3 | Microservicios | Baja | Hecho (servicio); el escritorio todavía no lo muestra |
| RF-E09 | Un lote lanza N réplicas por cada versión aprobada elegida | Cada réplica es una corrida en `simulation_runs` | 3.1 | Escritorio, Microservicios | Alta | Hecho |
| RF-E11 | Al terminar o fallar una corrida, se avisa a quien la pidió | El simulador crea el aviso por medio de `notificaciones`. No hay notificaciones push | 3.2, 3.4 | Microservicios | Alta | Hecho |
| RF-E12 | Toda corrida se puede repetir | La corrida guarda la versión congelada, la semilla y la versión del motor (`engine_version`); queda `RUN` en la auditoría al empezar y al cerrar | 3.2 | Microservicios, Bases de datos | Alta | Hecho |
| RF-E15 | El lote elige su motor: `seir-ref`, `abm-ref` o `abm-gpu` (D2, D22, D23). Cada motor tiene su simulador y su cola | `corridas` solo acepta un motor que esté habilitado en ese despliegue. Sin GPU, `abm-ref` es el respaldo | 3.1, 3.2 | Microservicios, Escritorio | Alta | En parte: `corridas` ya lo acepta solo si `MOTORES_HABILITADOS` lo nombra; el escritorio todavía no ofrece `abm-gpu` (RF-H20) |
| RF-E19 | Al arrancar, el simulador recupera las corridas que quedaron a medias (D19) | Las `ejecutando` se cierran como `fallido` y las `encolado` de su motor vuelven a la cola | 3.2 | Microservicios | Alta | Hecho |
| RF-E20 | El simulador guarda el resumen de la corrida en `simulation_runs` y la serie diaria en MongoDB, en `series_corridas` (D28) | Hay un documento por día de cada corrida, que se recupera por `run_id`. `simulation_results` deja de usarse | 3.2 | Microservicios, Bases de datos | Alta | Hecho (D-1): el resumen va a `simulation_runs` (038) y la serie a `series_corridas`; `simulation_results` se retiró (041) |
| RF-E17 | Barrido de calibración: se lanza una calibración de `seir-ref` contra una serie observada y se sigue su avance (D50, reabierto) | `POST /api/v1/calibrations` de `calibracion` responde 202 y la encola; `calibracion-trabajador` corre el ABC por rechazo y guarda el resultado al terminar. Lanzan EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`calibrations.run`, 062), con `RUN` en la auditoría; se cancela con `CANCEL`. Una interrumpida se reencola hasta 3 intentos (D38) | 3.1, 3.2 | Microservicios | Media | Hecho (servicio, E7): falta que el escritorio la lance (A4) |
| RF-E21 | Dos peticiones a la vez no lanzan dos veces la misma versión | `corridas` toma un candado por versión en Redis mientras registra el lote | 3.1 | Microservicios | Media | Hecho |

Las corridas pasan por los estados de la base: `encolado`, `ejecutando`, `completado`, `fallido` y `cancelado` (RN-21).

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-E13 | Límite de corridas a la vez | Cada simulador toma una corrida de su cola; el tope por lote ya está en RF-E03 |
| RF-E16 | Rechazar corridas que no caben en memoria | El límite de población ya lo ponen el XSD y la validación (RF-D03) |
| RF-E18 | Guardar resultados parciales | Una corrida interrumpida se cierra como fallida y se vuelve a lanzar |
