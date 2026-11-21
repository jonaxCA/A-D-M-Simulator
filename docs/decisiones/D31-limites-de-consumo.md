# D31 - Limites de consumo

Fecha: 2026-11-11 · Estado: Aceptada

## Contexto

## Opciones consideradas

## Decisión
Un contador por usuario y ruta en Redis (ratelimit:<usuario>:<ruta>), como ya propone §9.1 de la v2.
Más permisivo en casos y sincronizacion, más estricto en corridas.
Va en epidemia_comun, así lo heredan los 29 servicios.



## Consecuencias
