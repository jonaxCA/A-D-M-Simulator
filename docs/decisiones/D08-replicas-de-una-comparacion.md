# D8 - Cuántas réplicas usa una comparación y cómo se resumen

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
Una comparación pone corridas lado a lado. Con un modelo de agentes estocástico, una sola corrida no basta para comparar dos escenarios. Cada corrida guarda su semilla (`seed`). Estaba marcada para revisar en el tercer parcial; ya llegó.

## Opciones consideradas
- Número de réplicas: fijo o configurable. La propuesta (sección D8) recomienda N = 30 fijo.
- Resumen: media, mediana o intervalo entre percentiles. La propuesta recomienda mediana y banda del percentil 5 al 95.

## Decisión
- Réplicas configurables, 30 por omisión; con menos de 30 la app pide confirmación.
- Mismas semillas (1 a N) en todos los escenarios comparados, para que las diferencias se deban a las intervenciones.
- Resumen por escenario: media, mediana y banda del percentil 5 al 95.
- La frontera de Pareto se calcula sobre medianas, y la pantalla avisa cuando las bandas de dos escenarios se enciman.
- Tope real de 100. El escritorio topa en 100 por GET /runs, mientras la base acepta 200 y nadie lee max_replicas_por_lote. Se documenta 100 como tope y se ajusta system_settings con una migración.
- El cálculo se queda en el cliente (frontend_desktop/app/resumen.py) este parcial. Moverlo a comparacion y pareto queda para la entrega final.


## Consecuencias
- El escritorio controla el número de réplicas. La web no lanza corridas (D4).
- Un lote con más réplicas tarda más y produce más resultados. El tope de 200 evita saturar la cola.
- Bajar de 30 réplicas es posible, con confirmación. El aviso es de la app de escritorio; la base sigue aceptando de 1 a 200.
- La frontera sobre medianas ya la calcula el escritorio; el aviso de bandas encimadas falta. Ver [`todo.md`](todo.md), sección «Cambios pendientes por D8».

Depende de: D22
