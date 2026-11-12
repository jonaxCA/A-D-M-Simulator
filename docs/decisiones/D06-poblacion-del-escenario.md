# D6 - Qué significa la población de un escenario

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
La migración 023 sube el tope de población a 20 millones para que quepa el estado completo, y los contratos ejemplifican con `population_size` de 200 000. Con un modelo de agentes, simular un agente por habitante es mucho más caro que el SEIR.

## Opciones consideradas
- Opción A: habitantes.
- Opción B: agentes simulados.
- Opción C: factor de escala calculado (cada agente representa N habitantes, con N = habitantes de `regions.population` / agentes). La propuesta la recomienda.
- Opción D: factor de escala arbitrario. La app de escritorio permite ajustar el factor a mano. Es la que el equipo quiere implementar; su viabilidad en el motor está por investigar.

## Decisión
opción C. population_size cuenta agentes simulados y el factor se calcula fuera del motor.

## Consecuencias
- Con un factor arbitrario, los habitantes representados ya no salen solo de `regions.population`. Hay que decidir si el factor se valida contra el censo o se guarda como supuesto (regla 8 de `AGENTS.md`).
- El factor no cambia el número de agentes, así que el costo de cómputo es el mismo.
- Si la viabilidad es negativa, la opción C queda como respaldo.

Depende de: D22
