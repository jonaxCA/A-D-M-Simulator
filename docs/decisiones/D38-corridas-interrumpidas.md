# D38 - Corridas interrumpidas: se reencolan, no se cierran como fallidas

Fecha: 2026-11-19 · Estado: Aceptada · Cambia RNF-C03

## Contexto
La retroalimentación pide probar qué pasa si un trabajador se detiene después de guardar los resultados y antes de confirmar la corrida: no deben quedar corridas duplicadas ni resultados perdidos (demostración, paso 12).

Hoy, al arrancar, el simulador cierra como `fallido` toda corrida `ejecutando` de su motor. La serie se guarda en MongoDB antes de confirmar (`feat/bloque-D`), así que en ese caso queda una corrida fallida con su serie huérfana, y `banda()` la cuenta.

Lo que ya existe y se aprovecha:
- La transición condicionada a `ejecutando`.
- El índice único `{run_id, dia}` de `series_corridas`.
- La semilla, `engine_version` y `scenario_checksum` de cada corrida (migración 038).
- Que la misma entrada, semilla y versión dan la misma salida (ficha, §6).

## Opciones consideradas
- Opción A: seguir cerrándolas como fallidas, y que el usuario pida otra corrida.
- Opción B: reencolarlas y repetirlas con la misma semilla, con un tope de intentos.
- Opción C: dar por buena la serie ya guardada y confirmar la corrida sin volver a correrla.

## Decisión
Opción B. La A pierde resultados que se pueden recuperar. La C confirma una serie sin el resumen ni la auditoría de su ejecución, y no distingue una serie completa de una a medias.

**Al arrancar** (y cuando Redis vuelve), el simulador busca las corridas `ejecutando` de su motor:
- Si su `engine_version` es la del motor que arranca y no pasan del tope de intentos, regresan a `encolado` (transición condicionada, con auditoría `RUN`, motivo «reinicio del trabajador»). Se vuelven a meter a la cola con el `reencolar()` que ya existe, que no duplica lo que ya está en ella.
- Si la versión del motor cambió, o llegan al tope (3 intentos), se cierran como `fallido` con el motivo, y su serie se borra.

**Al repetirla:**
- Antes de escribir, se borra lo que haya de ese `run_id` en `series_corridas`, y luego se inserta. Por el índice único y la misma semilla, el resultado es el mismo y nunca hay días duplicados.
- La corrida se confirma (`ejecutando` → `completado`) solo después de guardar la serie. Si otro proceso ya la confirmó, la transición no aplica y la serie no se toca (`descartar_serie`).

**Lo que se cuenta como resultado:**
- `banda()` y `resultados` solo cuentan las series de corridas `completado`. `resultados` le pasa a la agregación los `run_id` completados que lee de PostgreSQL.
- Una corrida `fallida` o `cancelada` no deja serie.

**Serie perdida tras confirmar.** Pasa si MongoDB estaba caído y el proceso murió con la serie pendiente en memoria.
- En su ciclo de reintento, el simulador busca las corridas `completado` de su motor que no tienen serie, y la regenera con la misma semilla.
- Solo la guarda si `engine_version` y `scenario_checksum` coinciden y el resumen regenerado es igual al guardado. Si no coinciden, lo registra y no escribe nada.

**Migración 045** (reserva del bloque E): `simulation_runs.attempts SMALLINT NOT NULL DEFAULT 0`, con `CHECK (attempts BETWEEN 0 AND 3)`. Se suma 1 cada vez que una corrida pasa a `ejecutando`.

## Consecuencias
- Una corrida interrumpida termina `completado` con su serie, o `fallido` sin serie. No hay corridas duplicadas, porque es el mismo `run_id`, ni días duplicados, por el índice.
- RNF-C03 cambia: «una corrida interrumpida se reencola hasta 3 veces».
- Una corrida que tumba al trabajador cada vez se detiene en el tercer intento.
- La prueba de F5 la demuestra matando el proceso entre `guardar_serie` y la confirmación.
- `abm-gpu` solo se repite exacto en la misma GPU y con la misma versión de FLAME GPU (ficha, §6). Si cambia de máquina se repite igual, y la serie puede diferir dentro del ruido. Se anota en la ficha.
