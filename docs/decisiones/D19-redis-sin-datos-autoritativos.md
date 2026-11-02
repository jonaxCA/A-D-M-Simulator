# D19 - Redis sin datos autoritativos

Fecha: — · Estado: Por confirmar

## Contexto
Redis guarda sesiones, caché, candados, la cola de corridas y el historial de `estado-servicios`. `decisiones/todo.md` la listaba como «por registrar o confirmar».

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
PostgreSQL es la fuente de verdad. Lo que está en Redis se puede reconstruir o perder sin dañar datos.

## Consecuencias
- Hoy el historial de `estado-servicios` está en Redis y se pierde si Redis cae. D28 propone moverlo a MongoDB.
- Si Redis cae se pierden la cola y el progreso de las corridas; falta verificar que se puedan reencolar desde PostgreSQL.
