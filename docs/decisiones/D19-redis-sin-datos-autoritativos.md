# D19 - Redis sin datos autoritativos

Fecha: — · Estado: Por confirmar

## Contexto
Redis guarda sesiones, caché, candados, la cola de corridas, el resultado de cada lote de sincronización y el historial de `estado-servicios`. `decisiones/todo.md` la listaba como «por registrar o confirmar».

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
PostgreSQL es la fuente de verdad. Lo que está en Redis se puede reconstruir o perder sin dañar datos.

## Consecuencias
Redis guarda en disco (`--appendonly yes` y el volumen `redis-datos` de `infra/docker-compose.yml`), así que un reinicio no borra nada. Lo que sigue aplica si Redis no está o si se pierde su volumen:

- **Sesiones:** sin Redis, los servicios responden 503 porque la verificación del token falla cerrada. Si se pierden sus datos, se cierran todas las sesiones y cada persona vuelve a entrar. En la app móvil los casos sin enviar se quedan en el teléfono y se mandan cuando esa cuenta vuelve a entrar.
- **Lotes de sincronización:** el resultado de cada lote vive 7 días en Redis. Si se pierde, el teléfono reenvía el lote con el mismo `batch_id`. `casos` reconoce cada caso por su `local_uuid` y responde «duplicado», que la app cuenta como enviado, así que no se duplican casos.
- **Candados:** vencen solos. Si uno se pierde, dos peticiones del mismo lote pueden procesarse a la vez; `local_uuid` también evita duplicados ahí.
- **Cola de corridas:** la corrida se guarda como `encolado` en PostgreSQL antes de entrar a la cola, y si Redis no está en ese momento se cancela, en vez de quedar colgada. Al arrancar, el trabajador cierra como fallidas las que estaban `ejecutando`. Si se pierde la cola, las `encolado` se quedan así: nada las vuelve a encolar solo. Hoy se reencolan a mano, con el id solo, en `queue:simulaciones:<motor>`; falta que el simulador lo haga al arrancar.
- **Historial de `estado-servicios`:** se pierde. D28 propone moverlo a MongoDB.
- **Caché:** perderla solo cuesta tiempo.
