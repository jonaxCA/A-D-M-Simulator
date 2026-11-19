# D10 - Microservicios en el segundo parcial; apps de escritorio y móvil en el tercero

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
La rúbrica separa la construcción de los servicios (segundo parcial) de las aplicaciones cliente (tercer parcial).

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
El segundo parcial entrega los 26 servicios con sus contratos y la consola de pruebas hace de cliente. Las apps de escritorio y móvil se entregan en el tercero.

## Consecuencias
- La app móvil está en `frontend_movil/` desde el 2026-11-07. Se hizo en la rama `desarrollo-movil`, que ya está integrada en esta, y usa los servicios de D27.
- La app de escritorio se está construyendo en la rama `feat/app-escritorio` (MVP del 2026-11-09). En esta rama, `frontend_desktop/` todavía solo tiene su `AGENTS.md` y su `CLAUDE.md`.
- La regla de `AGENTS.md` que prohibía crear código en esas carpetas ya no aplica. El `AGENTS.md` de la raíz ya lo refleja para la móvil; falta para la de escritorio cuando se integre.
