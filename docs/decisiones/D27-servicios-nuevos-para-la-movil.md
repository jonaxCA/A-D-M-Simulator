# D27 - Servicios nuevos para la app móvil

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
`docs/arquitectura/todo.md` indica que la app móvil pide tres servicios nuevos, que ya estaban entre los opcionales: `dispositivos` (sin él no se puede mandar `device_id`), `evidencias` (las fotos) y `vacunas` (los QR de lotes). Las tablas `devices`, `case_attachments` y `vaccine_lots` ya existen (migraciones 002 y 005). La rúbrica pide dos capacidades del dispositivo. Cada servicio de más es otro contenedor, otro rol de base, otro contrato y otras pruebas.

## Opciones consideradas
- Opción A: los tres.
- Opción B: un subconjunto, el que cubra las dos capacidades del dispositivo (la sincronización ya la cubre `sincronizacion`).
- Opción C: ninguno.

## Decisión
Opción A: los tres servicios, `dispositivos`, `evidencias` y `vacunas`, tal como están implementados en la rama `desarrollo-movil`. Cada uno trae su contenedor en `infra/docker-compose.yml`, su rol de base (migraciones 031 a 033), su contrato en `docs/contratos/` y sus pruebas.

## Consecuencias
- El catálogo de `docs/arquitectura/microservicios.md` ya incluye los tres. No cambia.
- Las migraciones 031 a 033 llegan con `desarrollo-movil`. Las siguientes libres empiezan en la 034.
- Fija el proceso P1. Un archivo en el bucket (D-3) exige al menos `evidencias`.
- Los cambios que siguen están en [`todo.md`](todo.md), sección «Cambios pendientes por D27». No están fusionados: llegan al integrar `desarrollo-movil`.
