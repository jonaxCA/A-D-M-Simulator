# D44 - Prioridad en la cola, tiempo estimado y reintento manual de una corrida fallida

Fecha: 2026-11-20 · Estado: Aceptada · Reabre RF-E07, RF-E08 y RF-E14 · Amplía D38

## Contexto
La retroalimentación pide prioridades en la cola, un tiempo estimado y reintentos seguros. Hoy la cola de cada motor atiende en orden de llegada, ninguna ruta da una estimación y una corrida `fallido` solo se repite lanzando otra.

## Opciones consideradas
- Prioridad: A) una lista de Redis por prioridad y `BRPOP` con las llaves en orden; B) un conjunto ordenado con puntaje.
- Reintento: A) lanzar otra corrida enlazada a la original; B) regresar la misma corrida a `encolado`.
- Estimación: A) una cifra fija por motor; B) la mediana de lo medido.

## Decisión
- **Prioridad:** A. `simulation_runs.priority` (`baja`, `normal` por omisión, `alta`; migración 054). Cada motor tiene `queue:simulaciones:<motor>` (normal), `…:alta` y `…:baja`; el simulador hace `BRPOP` en ese orden, así que toma antes las altas y, dentro de cada cola, en orden de llegada. Sin reparto entre usuarios (RNF-B08 sigue fuera): una cola de altas que nunca se vacía retrasa a las demás, y por eso solo el `ADMINISTRADOR` pide `alta` (403 para otro rol). `baja` y `normal`, los dos roles que lanzan. `POST /runs` acepta `priority`. Al reencolar desde la base (D19, D38) cada corrida regresa a la cola de su prioridad.
- **Estimación:** B. `GET /runs/{id}` agrega `priority`, `queue_position` (lugar entre las encoladas de su motor, por prioridad y luego id) y `estimated_seconds`: la mediana de lo que tardaron las últimas 50 corridas `completado` del mismo motor, población y horizonte. Una `ejecutando` regresa lo que falta; una `encolado`, lo que falta más una corrida por cada una de delante o ejecutándose, suponiendo que duran igual. Sin historial o ya terminada, `estimated_seconds` es `null` y `estimate_reason` dice por qué; no hay cifra inventada. `estimate_samples` es el número de corridas medidas.
- **Reintento:** B. `POST /runs/{id}/retry` (ANALISTA y ADMINISTRADOR, `simulations.run`) pasa `fallido` a `encolado` con una transición condicionada (`WHERE status = 'fallido'`), con la misma semilla, el mismo `run_id` y la misma prioridad (salvo `alta` reintentada por un ANALISTA, que baja a `normal`: solo el ADMINISTRADOR pide `alta`), y reinicia `attempts`, `progress` y `error_message`. Audita `RUN` (motivo «reintento manual»). Dos reintentos a la vez, o uno sobre otro estado, dan 409. No hay otra corrida ni serie duplicada: la serie se reescribe por `{run_id, dia}` (D38). Una `cancelado` no se reintenta; se lanza otra. El reintento es manual: reintentar sola una fallida por el motor no sirve, porque con la misma semilla repite el mismo error.
- Migración 054: la columna con su `CHECK` y `GRANT UPDATE (error_message, progress, attempts)` a `svc_corridas`.

## Consecuencias
- Las colas `:alta` y `:baja` entran a la tabla de llaves de Redis; siguen sin TTL.
- Si Redis falla al reintentar, la corrida queda `encolado` en la base y el simulador la mete a su cola al recuperarse (D19); la respuesta es 202, porque eso es lo que quedó guardado.
- Un reintento no conserva `forzar_error` (no se guarda en la base).
- Los clientes pueden mostrar la prioridad, la posición y el tiempo estimado, y ofrecer «Reintentar» en una fallida; ninguno lo hace todavía.
