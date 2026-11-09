# D9 - XML por defecto y JSON por parámetro o cabecera

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
Los servicios atienden a la app de escritorio (XML) y a la móvil (JSON), y la rúbrica pide ambos formatos.

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
Las respuestas son XML por defecto. JSON se pide con `?format=json` o con `Accept: application/json`. Si chocan, manda `?format`.

## Consecuencias
- Un cliente JSON debe pedirlo siempre de forma explícita.
- Cada contrato lleva ejemplo en XML y en JSON.
