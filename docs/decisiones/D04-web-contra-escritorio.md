# D4 - Reparto del trabajo con escenarios entre la web y la app de escritorio

Fecha: 2026-11-07 · Estado: Aceptada

## Contexto
La rúbrica pide que la app de escritorio consuma solo XML, atienda un proceso distinto al de la móvil y no sea una copia de la web. Hoy la web hace todo el trabajo con escenarios. `escenarios-xml` ya exporta e importa escenarios en XML validado con XSD.

## Opciones consideradas
Propuestas por validar, tal como estaban en el registro:
- Opción A: el escritorio concentra el diseño, la importación y exportación en XML y el envío a revisión (proceso P2 de `brechas_v3.md`); la web conserva consulta, tablero y resultados.
- Opción B: la web conserva todo lo de escenarios y el escritorio se dedica a simulación, comparación y reportes (proceso P3).

Ninguna de las dos se adopta completa. De A se toma que el escritorio haga el diseño y la edición detallada del XML. De B se toma que la web conserve aprobar versiones y la vista de comparación.

## Decisión
Reparto de tareas, según la sección D4 de la propuesta:

| Tarea                                                               | Web               | Escritorio                                   |
| ---                                                                 | ---               | ---                                          |
| Crear un escenario sencillo y enviarlo a revisión                   | No                | Sí                                           |
| Aprobar o rechazar versiones                                        | Sí                | No                                           |
| Edición detallada del XML (población, calendario de intervenciones) | No                | Sí                                           |
| Lanzar una corrida                                                  | No                | Sí                                           |
| Lanzar lotes de decenas de réplicas                                 | No                | Sí                                           |
| Comparar y ver la frontera                                          | Vista de consulta | Comparador completo, exportación e impresión |

Además, la web conserva la consulta en solo lectura de escenarios, corridas y resultados. Así el epidemiólogo ve lo que aprueba.

## Consecuencias
Define el proceso de la app de escritorio, sus cuatro microservicios mínimos y qué se quita de la web, si algo. Depende de D1 para saber qué rol usa cada app.

- El escritorio crea y envía escenarios, hace la edición detallada del XML, lanza corridas y lotes, y tiene el comparador completo. Su proceso es P2 y P3 de la [arquitectura v3](../arquitectura/brechas_v3.md).
- La web conserva aprobar o rechazar versiones, la vista de comparación y la consulta en solo lectura de escenarios, corridas y resultados. La comparación no exporta ni imprime.
- Cuadra con D1: el analista, que usa la app de escritorio, crea y corre escenarios; el epidemiólogo, que usa la web, aprueba y consulta.
- La app de escritorio no se construye en el segundo parcial (D10). Su proceso queda escrito en la arquitectura v3 y su código va en el tercer parcial.
- Implementada en la web el 2026-11-11: se quitaron las rutas y los botones de crear, versionar, duplicar, editar intervenciones, enviar a revisión, ejecutar y re-ejecutar. Como la web ya no corre simulaciones, `frontend_web/run.py` tampoco cierra al arrancar las corridas encoladas o en ejecución: eran sus hilos, y hoy serían las del simulador.

Depende de: D1
