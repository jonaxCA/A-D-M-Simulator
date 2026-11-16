> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RNF-I: Ética y uso responsable

El sistema es un proyecto universitario que simula escenarios: no es una herramienta de predicción ni de asesoría sanitaria. Cómo leer la tabla: [`README.md`](../README.md).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Componente | Estado |
|---|---|---|---|---|
| RNF-I05 | No se captura ningún dato que identifique a una persona | Ver RNF-D15 | Móvil, Bases de datos | Hecho |
| RNF-I06 | La población simulada es sintética | Ningún agente corresponde a una persona real: el motor recibe un total de agentes, o un conteo por grupo de edad | Microservicios | Hecho |
| RNF-I08 | Toda pantalla de resultados dice que no es una predicción | Ver RF-F19 | Web, Escritorio | Hecho |
| RNF-I09 | Los supuestos están a la vista | Todo parámetro de enfermedad y todo costo lleva su fuente o la marca de supuesto (RF-B09) | Web, Microservicios | Hecho |
| RNF-I10 | No se le pone precio a una vida | La frontera usa personas-día; el costo en pesos va aparte y no entra a la frontera (D3) | Microservicios, Escritorio | Hecho |
| RNF-I11 | Nunca se muestra una sola curva como si fuera el resultado | La comparación muestra la mediana con su banda del percentil 5 al 95 (D8) | Escritorio | Hecho |
| RNF-I15 | Los datos de la demostración son sintéticos | `gen_demo_data.py` genera los casos; no hay datos reales de pacientes | Bases de datos | Hecho |
| RNF-I16 | El sistema no decide: muestra opciones y costos | La comparación no recomienda un escenario (RN-36) | Escritorio, Web | Hecho |
| RNF-I18 | Las limitaciones del modelo están escritas | Están en [`ficha_simulador.md`](../../arquitectura/ficha_simulador.md); sin calibración, los resultados son escenarios y no pronósticos (D24) | Microservicios | Hecho |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RNF-I01 | Cumplir la Ley General de Salud | El proyecto no opera con datos reales ni tiene convenio con una dependencia; lo que aplica es RNF-I05 y RNF-I15 |
| RNF-I02 | Cumplir la NOM-017-SSA2-2012 | Igual que RNF-I01 |
| RNF-I03 | Cumplir la NOM-004-SSA3-2012 | Igual que RNF-I01 |
| RNF-I04 | Cumplir las leyes de protección de datos | Igual que RNF-I01 |
| RNF-I07 | Publicar solo con un mínimo de casos por zona | No hay umbral definido (ver RF-C18) |
| RNF-I12 | Consentimiento informado en campo | Los datos de la demostración son sintéticos |
| RNF-I13 | Derecho al olvido | No se guardan datos personales |
| RNF-I14 | Retención limitada | Pasa a RNF-K07 |
| RNF-I17 | Decisiones trazables a sus supuestos | Se cubre con RNF-I09 y RNF-J12 |
