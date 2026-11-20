> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-F: Resultados y comparación

Es la segunda mitad del proceso **P3** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md): el ANALISTA compara los resultados contra su costo y exporta un reporte; EPIDEMIOLOGO y ANALISTA consultan en la web. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-E (corridas completadas) y RF-H (la app de escritorio).
- PostgreSQL: `simulation_runs`, `simulation_results`, `intervention_types` (costo).
- MongoDB: `series_corridas` (D28).
- Redis: la caché de `resultados`.
- Cloud Storage: el reporte (D30).
- Servicios: `resultados`, `comparacion`, `pareto`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-F01 | Cada corrida entrega sus curvas diarias | `resultados` responde un punto por día simulado, con los compartimentos del modelo | 3.5, 3.7 | Microservicios | Alta | Hecho |
| RF-F02 | El resultado se desglosa por grupo de edad | La serie diaria trae totales; el desglose por grupo sale de `desglose_por_grupo` del resumen (D28) | 3.5 | Microservicios | Media | Verificar: que la web y el escritorio muestren `desglose_por_grupo` |
| RF-F04 | Cada corrida entrega su resumen: casos acumulados, hospitalizaciones, fallecimientos, pico de casos activos, día del pico y tasa de ataque | `resultados` responde los seis indicadores | 3.5, 3.7 | Microservicios | Alta | Hecho |
| RF-F05 | El costo de cada escenario se calcula con el costo unitario de sus intervenciones, en personas-día y en pesos por separado (D3) | `pareto` responde el costo de cada intervención y el total. La frontera usa personas-día; los pesos van aparte en la tabla | 3.5 | Microservicios | Alta | Hecho |
| RF-F06 | Las réplicas de una versión se resumen con media, mediana y la banda del percentil 5 al 95 (D8) | Se usan solo las semillas comunes a todas las versiones comparadas. Este parcial el resumen se calcula en el escritorio | 3.5 | Escritorio | Alta | Hecho |
| RF-F07 | La comparación dibuja la frontera de Pareto sobre las medianas, contra el costo | Un escenario dominado queda fuera de la frontera. La pantalla muestra opciones y costos, y no recomienda ninguno (RN-36) | 3.5 | Escritorio, Microservicios | Alta | Hecho |
| RF-F08 | Las curvas de varias versiones se ven juntas, cada una con su banda | La gráfica muestra la mediana y la banda de cada versión | 3.5 | Escritorio | Alta | Hecho |
| RF-F09 | La comparación se exporta a CSV | Salen la tabla y las curvas | 3.6 | Escritorio | Alta | Hecho |
| RF-F11 | La comparación se exporta a un reporte en PDF, o se imprime | El reporte trae la tabla, la frontera, las curvas y el aviso de que no es una predicción | 3.6 | Escritorio | Alta | Hecho |
| RF-F17 | El reporte se sube a Cloud Storage y se comparte con una URL firmada | PostgreSQL guarda los metadatos del reporte, en una tabla nueva. La exportación queda en la auditoría. La web abre el reporte con una URL que vence en minutos | 3.6, 3.7 | Escritorio, Microservicios, Web | Alta | Falta (D-3): hoy el reporte queda en la computadora |
| RF-F19 | Toda pantalla de resultados muestra el aviso de que no es una predicción (`AVISO_SIMULACION`) | El aviso llega del servidor y se ve en la web, en el escritorio y en el reporte (RN-35) | 3.5 a 3.7 | Web, Escritorio, Microservicios | Alta | Hecho |
| RF-F20 | Los conteos se entregan junto con el factor de escala: habitantes del censo entre agentes simulados (D6) | `resultados` responde el factor. La pantalla lo muestra | 3.5 | Microservicios, Escritorio | Media | Hecho: el escritorio lo muestra en el diálogo de escala (RF-H21) |
| RF-F21 | La web consulta una corrida: su resumen y sus curvas | EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR ven la corrida. Con D28, el resumen sale de `simulation_runs` y las curvas se piden a `resultados`; si `resultados` no responde, se ve el resumen sin curvas (D20) | 3.7 | Web | Alta | Hecho (D-1): el resumen sale de `simulation_runs` y las curvas de `resultados` con el JWT de la sesión (D34); sin `resultados`, el resumen sin curvas |
| RF-F22 | `comparacion` pide los resultados a `resultados` y aprovecha su caché | Una comparación repetida no vuelve a leer la serie completa | 3.5 | Microservicios | Media | Hecho |
| RF-F23 | La pantalla avisa cuando las bandas de dos escenarios se enciman (D8) | Si las bandas se cruzan, la comparación lo dice junto a la frontera | 3.5 | Escritorio | Media | Hecho: la comparación y su PDF muestran el aviso (RF-H22) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-F03 | Resultados por municipio | Un escenario es de una sola región |
| RF-F10 | Exportar las gráficas en PNG | Se cubre con el PDF (RF-F11) |
| RF-F12 | Análisis de sensibilidad | Ningún proceso lo pide |
| RF-F13 | Encimar la curva simulada con datos reales | La calibración queda fuera (D24): los resultados son escenarios, no pronósticos |
| RF-F14 | Error cuadrático y R² contra datos reales | Igual que RF-F13 |
| RF-F15 | Mapa de incidencia | Es el mapa de casos del tablero web (RF-G03) |
| RF-F16 | Animar la evolución sobre el mapa | La visualización 3D y las animaciones quedan fuera |
| RF-F18 | Marcar resultados como favoritos | Ningún proceso lo pide |
| — | Resumir las réplicas en el servidor | Queda para la entrega final (D8) |
