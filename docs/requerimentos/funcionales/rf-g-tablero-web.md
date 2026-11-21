> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-G: Tablero de control (sistema web)

Es la visualización de P1 (paso 1.9) y de P3 (paso 3.7) de [`procesos_v3.md`](../../arquitectura/procesos_v3.md). La web es el monolito Flask: va directo a PostgreSQL y no llama a los microservicios, salvo por las curvas de una corrida (D20). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles), RF-C (casos) y RF-F (resultados).
- PostgreSQL: `cases`, `regions`, `diseases`, `simulation_runs`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-G01 | El tablero (`/dashboard`) muestra los indicadores de los casos capturados | Cuenta los casos pendientes y los validados. Un caso recién sincronizado aparece al recargar | 1.9 | Web | Alta | Hecho |
| RF-G02 | Las gráficas de la web usan Highcharts (lo pide la materia) | Las curvas del tablero, del monitoreo epidemiológico y de una corrida son de Highcharts | 1.9, 3.7 | Web | Alta | Hecho |
| RF-G03 | El mapa (`/mapa`) muestra los casos por municipio | Cada municipio de Nuevo León se pinta según sus casos | 1.9 | Web | Alta | Hecho |
| RF-G04 | El monitoreo epidemiológico (`/monitoreo`) se filtra por periodo | La serie cambia según los días elegidos | Soporte | Web | Media | Hecho |
| RF-G05 | El monitoreo epidemiológico se filtra por enfermedad y por región | La serie y los totales cambian según el filtro | Soporte | Web | Media | Hecho |
| RF-G06 | El monitoreo epidemiológico desglosa los casos por edad y por sexo | Se ve una serie por grupo de edad y otra por sexo | Soporte | Web | Media | Hecho |
| RF-G09 | El estado de una corrida se actualiza sin recargar la página | La pantalla de la corrida pregunta su estado y cambia cuando la corrida termina | 3.7 | Web | Media | Hecho |
| RF-G11 | Cada rol ve lo que le toca. El CAPTURISTA entra solo al tablero y al mapa (D1) | Cualquier otra pantalla responde 403 al CAPTURISTA. La bitácora es solo del ADMINISTRADOR | 1.9 | Web, Seguridad | Alta | En parte: falta revisar los candados contra D1 |
| RF-G12 | El tablero y el monitoreo epidemiológico exportan a CSV | Salen el resumen del tablero y la serie del monitoreo | Soporte | Web | Media | Hecho |
| RF-G15 | La web muestra la comparación de corridas, solo como consulta (D4) | ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR ven la vista; no exporta ni imprime, que es del escritorio | Soporte | Web | Media | Hecho |
| RF-G16 | La web recibe archivos | El ANALISTA o el ADMINISTRADOR (`reports.upload`) sube el reporte de una comparación, que se valida por su contenido, su tamaño y su huella, y va al bucket (D30, D35) | Soporte | Web | Alta | Falta (D-5): la rúbrica lo pide y hoy la web no recibe archivos |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-G07 | Ocupación hospitalaria | No hay fuente para ese dato |
| RF-G08 | Alertas cuando un indicador pasa de un umbral | No hay umbrales definidos ni decisión que los pida |
| RF-G10 | Tablero legible en el teléfono | Pasa a RNF-E03 |
| RF-G13 | Tablero configurable por usuario | Ningún proceso lo pide |
| RF-G14 | Resultados de simulación junto a datos reales | La calibración queda fuera (D24) |
| — | Capturar casos desde la web | La captura es solo de la app móvil (D1) |
| — | Crear o editar escenarios y lanzar corridas desde la web | Son de la app de escritorio (D4) |
