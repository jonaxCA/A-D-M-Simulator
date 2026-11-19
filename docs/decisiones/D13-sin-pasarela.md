# D13 - Sin pasarela: las apps usan el directorio de `estado-servicios`

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
Cada servicio publica su puerto. Las apps y la consola necesitan saber dónde está cada uno.

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
No hay pasarela de API. Las apps y la consola le piden la URL de cada servicio al directorio de `estado-servicios` y llaman directo.

## Consecuencias
- Cada servicio valida su propio JWT.
- La decisión se ajusta con D25: nginx pasa a ser la entrada y el directorio devolvería `https://<dominio>/<servicio>` en lugar de `host:puerto`. No vuelve a ser una pasarela de API.
