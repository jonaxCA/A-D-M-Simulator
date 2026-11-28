# D14 - Pruebas con `pytest`

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
El equipo necesitaba un solo comando para las pruebas del monolito, el motor y los servicios.

## Opciones consideradas
`unittest`, que `pytest` también corre.

## Decisión
Se usa `pytest`, que corre también las pruebas escritas con `unittest`: `python -m pytest`.

## Consecuencias
- Un solo comando desde la raíz.
