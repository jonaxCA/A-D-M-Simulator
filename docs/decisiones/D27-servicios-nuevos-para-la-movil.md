# D27 - Servicios nuevos para la app móvil

Fecha: — · Estado: Pendiente

## Contexto
`docs/arquitectura/todo.md` indica que la app móvil pide tres servicios nuevos, que ya estaban entre los opcionales: `dispositivos` (sin él no se puede mandar `device_id`), `evidencias` (las fotos) y `vacunas` (los QR de lotes). Las tablas `devices`, `case_attachments` y `vaccine_lots` ya existen (migraciones 002 y 005). La rúbrica pide dos capacidades del dispositivo. Cada servicio de más es otro contenedor, otro rol de base, otro contrato y otras pruebas.

## Opciones consideradas
- Opción A: los tres.
- Opción B: un subconjunto, el que cubra las dos capacidades del dispositivo (la sincronización ya la cubre `sincronizacion`).
- Opción C: ninguno.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Fija el catálogo de la v3 (26 servicios hoy) y el proceso P1. Un archivo en el bucket (D-3) exige al menos `evidencias`.
