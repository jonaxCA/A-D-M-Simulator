# D32 - Cierre de los tres procesos de la v3

Fecha: 2026-11-16 · Estado: Aceptada

## Contexto
[`procesos_v3.md`](../arquitectura/procesos_v3.md) dejó tres preguntas que ninguna decisión cubría: a quién avisa P1, si la móvil cumple con «actualización de información» (C9) y si P2 guarda un archivo en GCS. La rúbrica pide notificación en cada proceso y un archivo en bucket «cuando corresponda».

## Opciones consideradas
- Aviso de P1: uno por lote a los EPIDEMIOLOGO, uno por caso, o uno al CAPTURISTA con el resultado de su lote.
- Actualización en la móvil: quedarse con lo que hay o agregar la edición de un caso pendiente antes de mandarlo.
- Archivo de P2: ninguno, o el XML de intercambio en GCS.

## Decisión
- **Aviso de P1:** `sincronizacion` manda un aviso por lote a los EPIDEMIOLOGO cuando el lote crea al menos un caso nuevo. Un reintento del mismo lote no vuelve a avisar. Uno por caso llenaría la bandeja: un lote trae hasta 100.
- **Actualización en la móvil (C9):** basta con aplicar dosis (`doses_used` en `vaccine_lots`, con auditoría) y marcar avisos como leídos. No se agrega editar casos.
- **Archivo de P2:** P2 queda sin bucket. P1 (fotos) y P3 (reporte) ya lo usan, y el XML se puede volver a generar desde la versión en PostgreSQL. Guardarlo en GCS queda solo si sobra tiempo.

## Consecuencias
- Hay que implementar el aviso en `sincronizacion`, que hoy no llama a `notificaciones`. El CHECK `ck_notifications_type` (migración 029) no tenía un tipo para casos: la migración 037 agregó `NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED` (2026-11-16).
- C9 sale de `brechas_v3.md` sin código nuevo.
- Quien implementa D30 solo atiende fotos y reportes.
- Si el profesor pide archivo en los tres procesos, el XML de intercambio es el candidato.

Depende de: D28, D30
