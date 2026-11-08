# D8 - Cuántas réplicas usa una comparación y cómo se resumen

Fecha: 2026-11-08 · Estado: Propuesta

## Contexto
Una comparación pone corridas lado a lado. Con un modelo de agentes estocástico, una sola corrida no basta para comparar dos escenarios. Cada corrida guarda su semilla (`seed`). Estaba marcada para revisar en el tercer parcial; ya llegó.

## Opciones consideradas
- Número de réplicas: fijo o configurable. La propuesta (sección D8) recomienda N = 30 fijo.
- Resumen: media, mediana o intervalo entre percentiles. La propuesta recomienda mediana y banda del percentil 5 al 95.

## Decisión
Propuesta, sin confirmar por el equipo.

Número de réplicas: **configurable**. El analista elige cuántas réplicas tiene cada lote en la aplicación de escritorio. La base acepta de 1 a 200 y el valor por defecto es 30.

Piso: **30** como referencia. Si el analista elige menos de 30, la aplicación de escritorio pide confirmación («¿seguro que quieres bajar de 30 réplicas?»). La base no lo impide.

Resumen de resultados: por escenario se muestran **la media, la mediana y el intervalo entre percentiles 5 y 95**.

## Consecuencias
- El escritorio controla el número de réplicas. La web no lanza corridas (D4).
- Un lote con más réplicas tarda más y produce más resultados. El tope de 200 evita saturar la cola.
- Bajar de 30 réplicas es posible, con confirmación. El aviso es de la app de escritorio; la base sigue aceptando de 1 a 200.
- La frontera sobre medianas y el aviso de bandas encimadas no están confirmados. Ver [`todo.md`](todo.md), sección «Cambios pendientes por D8».

Depende de: D22
