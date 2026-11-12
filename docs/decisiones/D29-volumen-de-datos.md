# D29 - Volumen de datos de alto volumen

Fecha: 2026-11-11 · Estado: Aceptada

## Contexto
La rúbrica pide un conjunto considerable de datos y medir con y sin Redis. Qué es «considerable» depende del proyecto, y el profesor lo confirma cuando el sistema esté diseñado.

## Opciones consideradas
Candidato: las series diarias por corrida del ABM. La cifra no está propuesta.

## Decisión
El volumen se genera con el SEIR sobre series_corridas, sin depender del ABM.

- Cifra propuesta: unas 10,000 corridas de 180 días, alrededor de 1.8 millones de documentos diarios. Son un par de minutos de cómputo.
- Se mide: tiempo de inserción, consultas con y sin índice, consultas con y sin la caché de Redis, y uso de recursos.
- Del lado de PostgreSQL, gen_demo_data.py puede generar cientos de miles de casos para medir casos y series con y sin caché.
- Si el ABM llega a tiempo, sus corridas se suman a la misma colección; la medición no cambia.

## Consecuencias
Fija la prueba de rendimiento, las pruebas con Locust y el tamaño de la instancia. Depende de D6, D8 y D28.

Depende de: D6, D8, D28
