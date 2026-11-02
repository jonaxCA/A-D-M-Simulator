# D28 - Qué datos van a MongoDB

Fecha: — · Estado: Pendiente

## Contexto
La rúbrica pide almacenamiento real con inserción, consulta, actualización, agregación e índices. La v2 propone candidatos (§9.1).

## Opciones consideradas
Candidatos:
- el historial de `estado-servicios`, hoy en Redis;
- los lotes crudos de `sincronizacion`;
- las series diarias de las corridas del ABM.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Define las colecciones, los índices y el versionamiento (diseño de MongoDB que pide la rúbrica), y agrega un contenedor y una dependencia nuevos. Depende de D21.

Depende de: D21
