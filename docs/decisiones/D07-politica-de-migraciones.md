# D7 - Política de migraciones: datos contra esquema

Fecha: — · Estado: Pendiente

## Contexto
Las migraciones son el esquema de la base y una migración aplicada nunca se edita (regla 6 de `AGENTS.md`). Aun así hay migraciones que corrigen datos (012 corrige claves INEGI y 019 es una corrección manual de población) y otras que se generan con scripts y no se editan a mano (020 y 021). No hay una regla escrita para corregir datos.

## Opciones consideradas
Propuestas por validar (no hay opciones registradas):
- Opción A: toda corrección de datos va en una migración nueva, con su fuente.
- Opción B: separar esquema de datos; los datos de referencia viven en semillas regenerables.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
D16 depende de esta decisión. Toca `datos/`, `verifica_migraciones.py` y la base de pruebas.
