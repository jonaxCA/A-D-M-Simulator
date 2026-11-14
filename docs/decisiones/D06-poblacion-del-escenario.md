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
Opción C. `population_size` cuenta agentes simulados y el factor se calcula fuera del motor: factor = habitantes de la región (`regions.population`, Censo 2020) / agentes.

## Consecuencias
- El motor nunca ve el factor: simula los agentes, y sus resultados son de esos agentes. El factor lo calcula `procesamiento/analitica/escala.py`, igual para los tres motores.
- Como los habitantes salen del censo, el factor tiene fuente (regla 8). No hay columna nueva ni campo en el escritorio: eso era la opción D, que no se eligió.
- Una versión estratificada toma la población completa del censo, así que su factor es 1. Solo una sin estratificar puede simular menos agentes que habitantes, que es lo que abarata el ABM.
- Los conteos llevados a habitantes son una extrapolación: suponen que los no simulados se comportan como los simulados. Se muestran aproximados (≈) y junto a los de la corrida, nunca en su lugar. La tasa de ataque y los días de pico no se escalan.
- Con más agentes que habitantes el factor queda menor que 1, y se avisa.
- Implementado el 2026-11-14: lo muestran la web (detalle del escenario y de la corrida) y `resultados` (campo `escala`).

Depende de: D22
