# D2 - Papel del SEIR frente al modelo basado en agentes

Fecha: 2026-11-08 · Estado: Aceptada

## Contexto
El motor actual es un SEIR estocástico por grupos de edad, sin agentes (`procesamiento/motor`). Los documentos de arquitectura describen un sistema final con agentes. D22 decidió hacer el ABM, así que falta decir qué pasa con el SEIR.

## Opciones consideradas
Opciones de la sección D2 de [`propuesta_correcciones_primer_parcial.md`](../propuesta_correcciones_primer_parcial.md):
- Opción A: el SEIR queda como control experimental. Motores al final: SEIR, ABM en Python y ABM en FLAME GPU. Es la recomendada en la propuesta.
- Opción B: el SEIR queda como respaldo del ABM. Motores al final: SEIR y ABM en FLAME GPU.

## Decisión
Opción A: el SEIR queda como control experimental. Al final hay tres motores: SEIR, ABM en Python y ABM en FLAME GPU.

El SEIR no se retira. Sirve para medir qué aporta el ABM en nuestros propios escenarios.

## Consecuencias
- Si FLAME GPU falla, queda un ABM funcionando: el de Python.
- El aporte del ABM se mide contra el SEIR, en los mismos escenarios.
- Los motores cambian de nombre: `python-ref` → `seir-ref`, `numba` → `abm-ref`, `cuda` → `abm-gpu`. La base solo los acepta con una migración nueva, porque el CHECK de la 014 los tiene fijos. Hecho el 2026-11-12 con la migración 035, junto con el contrato que cumplen los tres motores (`docs/contratos/motor/`).
- El ABM depende de D22 (decidido) y de D23 (CPU o GPU). Con esta opción, FLAME GPU ya está en la lista de motores; D23 toma la opción B: el ABM en GPU corre en FLAME GPU, con créditos de GCP.
- Los cambios de código y documentos que siguen de esta decisión están en [`todo.md`](todo.md), sección «Cambios pendientes por D2». No están implementados.

Depende de: D22
