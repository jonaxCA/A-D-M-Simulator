# D3 - Unidad de costo: personas-día, pesos o ambos por separado

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
Las intervenciones tienen costo unitario con fuente o marca de supuesto (`intervention_types.unit_cost`, `cost_source`, `cost_is_assumption`; regla 8 de `AGENTS.md`). Pareto y la comparación se calculan con esos costos. Falta decidir en qué unidad se expresan.

## Opciones consideradas
- Opción A: personas-día.
- Opción B: pesos.
- Opción C: ambos, por separado.

Los argumentos de cada unidad (qué mide, qué datos faltan, cómo entra la vacuna) están en la sección D3 de [`propuesta_correcciones_primer_parcial.md`](../propuesta_correcciones_primer_parcial.md). Esa sección recomienda la opción C.

## Decisión
Opción C: personas-día y pesos por separado.

- La frontera de Pareto usa personas-día.
- El costo directo en pesos aparece aparte, en la tabla comparativa, y no entra a la frontera.

## Consecuencias
Afecta el esquema de costos, `pareto`, `comparacion`, los reportes de escritorio y la interpretación del aviso de que no es una predicción.

- Mostrar pesos exige fuente o marca de supuesto para cada precio (regla 8 de `AGENTS.md`).
- La frontera no refleja el costo de vacunar en pesos. Cómo entra la vacunación queda abierto (ver [`todo.md`](todo.md)).
- Los cambios de código y documentos que siguen de esta decisión están en [`todo.md`](todo.md), sección «Cambios pendientes por D3». No están implementados.
