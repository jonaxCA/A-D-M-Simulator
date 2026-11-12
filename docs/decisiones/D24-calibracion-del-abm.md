# D24 - Calibración y parámetros de los agentes

Fecha: 2026-11-11 · Estado: Aceptada

## Contexto
Todo parámetro de enfermedad lleva su fuente o la marca de supuesto (regla 8). La calibración estaba fuera de alcance y no hay fuente ni serie histórica para calibrar (§9.2 de la v2).

## Opciones consideradas
- Opción A: sin calibración; parámetros de literatura con su fuente o marcados como supuesto.
- Opción B: calibrar contra una serie histórica (hay que conseguir la fuente).

## Decisión
Opcion A.
- No hay serie histórica ni fuente para calibrar (§9.2 de la v2), y conseguirla y limpiarla no cabe en el parcial.
- Calibrar agrega un segundo algoritmo que documentar (entradas, complejidad, pruebas) sin datos con qué probarlo.
- AVISO_SIMULACION ya presenta los resultados como escenarios, no como pronóstico. Con la opción A el aviso sigue siendo cierto.
- La calibración pasa a «Trabajo futuro» del expediente final.


## Consecuencias
Con la opción A los resultados se presentan como escenarios, no como pronóstico (aviso `AVISO_SIMULACION`). 

Depende de: D22
