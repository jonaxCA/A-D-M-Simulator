# D11 - Rutas de las API en inglés

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
Las tablas y columnas del esquema están en inglés y el catálogo de servicios necesitaba rutas uniformes.

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
Las rutas van en inglés y versionadas, por ejemplo `/api/v1/scenarios`.

## Consecuencias
- Coinciden con los nombres de las tablas.
- Los nombres de los servicios siguen en español (D12), así que hay dos idiomas que no se deben mezclar.
- Con nginx (D25) el nombre del servicio pasa a ser el prefijo de la ruta pública.
