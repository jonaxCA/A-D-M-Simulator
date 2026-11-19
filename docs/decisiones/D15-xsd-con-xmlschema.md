# D15 - XSD validado con `xmlschema`; XML leído con `defusedxml`

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
El XML entrante es entrada de un tercero y la rúbrica pide validarlo contra XSD.

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
El XSD se valida con `xmlschema` y el XML se lee con `defusedxml`.

## Consecuencias
- El XML entrante no se parsea con otra biblioteca.
- La app de escritorio valida con el mismo XSD que publican los servicios.
