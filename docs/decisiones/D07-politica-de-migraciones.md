# D7 - Política de migraciones: datos contra esquema

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
Las migraciones son el esquema de la base y una migración aplicada nunca se edita (regla 6 de `AGENTS.md`). Aun así hay migraciones que corrigen datos (012 corrige claves INEGI y 019 es una corrección manual de población) y otras que se generan con scripts y no se editan a mano (020 y 021). No hay una regla escrita para corregir datos.

## Opciones consideradas
Propuestas por validar:
- Opción A: toda corrección de datos va en una migración nueva, con su fuente.
- Opción B: separar esquema de datos; los datos de referencia viven en semillas regenerables.
- Opción C: esquema y datos con reglas distintas. El esquema nunca se edita en un archivo aplicado. Los datos (valores de un `INSERT`) se corrigen en la fuente solo si se corrigen juntos el archivo de migración y el bloque del dump, hay una migración correctiva idempotente y el chequeo pasa.

La sección D7 de [`propuesta_correcciones_primer_parcial.md`](../propuesta_correcciones_primer_parcial.md) recomendaba la opción C.

## Decisión
Opción C.

- **Esquema** (tablas, columnas, restricciones, triggers, funciones): nunca se edita un archivo aplicado. Siempre un número nuevo.
- **Datos** (valores de un `INSERT`): se corrigen en el archivo de migración y en el bloque del dump, juntos, con una migración correctiva idempotente. El chequeo `verifica_migraciones.py` debe pasar.

La opción B no se adopta.

## Consecuencias
- Hay una excepción a la regla 6 de `AGENTS.md`: para valores de datos sí se edita un archivo aplicado, siempre con su migración correctiva. Lo demás de la regla sigue igual.
- Cada corrección de datos toca tres lugares: el archivo de migración, el bloque del dump y la migración correctiva nueva.
- Solo las migraciones nuevas siguen la regla de datos. Las ya aplicadas no se corrigen en la fuente, aunque tengan datos mal.
- Las migraciones 020 y 021 (generadas por scripts) no se corrigen por ahora: el equipo considera que no pasa nada.
- Toca `datos/`, `verifica_migraciones.py`, el README de migraciones y la base de pruebas. D16 depende de esta decisión.
- Los cambios pendientes están en [`todo.md`](todo.md), sección «Cambios pendientes por D7». No están implementados.
