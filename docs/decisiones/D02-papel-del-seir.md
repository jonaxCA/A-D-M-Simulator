# D2 - Papel del SEIR frente al modelo basado en agentes

Fecha: — · Estado: Pendiente

## Contexto
El motor actual es un SEIR estocástico por grupos de edad, sin agentes (`procesamiento/motor`). Los documentos de arquitectura describen un sistema final con agentes. D22 decidió hacer el ABM, así que falta decir qué pasa con el SEIR.

## Opciones consideradas
Las opciones de la «Corrección 2» no están en el repositorio, así que no se pueden listar aquí. Hay que recuperarlas o definirlas de nuevo antes de decidir.

Propuestas por validar, sacadas de `decisiones/todo.md` y de `brechas_v3.md`:
- Opción A: el SEIR queda como motor de referencia y respaldo del ABM. Es lo que ya propone la v2 y `todo.md`.
- Opción B: el SEIR se retira cuando el ABM funcione.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Define qué algoritmo se presenta como «algoritmo complejo» ante la rúbrica y qué hace `simulador` si el ABM falla. Depende de D22 y D23; condiciona D6 y D8.

Depende de: D22
