# EPIDEMIA — Índice de cierre del segundo parcial

**Rama revisada:** `feat/segundo-parcial-grupo-2pm` — commit `215b4a5` (13 oct 2026).

**Estado:** documentación de corrección, no certificación del sistema completo.

## Documentos para revisar antes de entregar

| Documento | Qué contiene |
|---|---|
| [`REPORTE_TECNICO_SEGUNDO_PARCIAL.md`](REPORTE_TECNICO_SEGUNDO_PARCIAL.md) | Estado real, 12 servicios integrados, responsables, corrección XML, evidencias, pendientes y preparación del cierre |
| [`MANUAL_TECNICO.md`](MANUAL_TECNICO.md) | Arquitectura y operación de los 12 servicios del grupo 14:00 |
| [`arquitectura/arquitectura_v2.md`](arquitectura/arquitectura_v2.md) | Diagrama y organización implementada del grupo 14:00 |
| [`CHECKLIST_SEGUNDO_PARCIAL.md`](CHECKLIST_SEGUNDO_PARCIAL.md) | Plan general de 26 servicios (propuesta; no equivale a lista de completados) |
| [`../evidencias/README.md`](../evidencias/README.md) | Evidencias disponibles y faltantes |
| [`../evidencias/pruebas/pytest_microservicios_xml_corregido.txt`](../evidencias/pruebas/pytest_microservicios_xml_corregido.txt) | Última suite registrada: 307 passed y 34 subtests passed |
| [`INSTALACION.md`](INSTALACION.md) | Instalación, monolito, Redis y ejecución de microservicios |

## Verificación documental

- El PR #115 quedó fusionado en la rama de las 14:00.
- El serializador XML admite claves de edad como `0-19` y `80+` mediante `<entrada clave="...">`.
- La suite anterior de 291 passed y 3 xfailed se conserva como evidencia histórica; la posterior registra 307 passed.
- Hay 36 capturas (`health`, `json`, `xml`) para los 12 servicios del grupo de las 14:00.
- El despliegue conjunto de 26 microservicios, la demostración de extremo a extremo y las excepciones de alcance siguen pendientes de verificación.

**Antes de generar el ZIP:** revisar el reporte con el equipo, incorporar lo pendiente y crear el archivo desde un único commit de entrega, sin secretos.
