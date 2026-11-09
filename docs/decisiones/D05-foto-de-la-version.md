# D5 - Una versión es una fotografía: congela población y parámetros

Fecha: sin registrar (segundo parcial) · Estado: Aceptada

## Contexto
Corregir un parámetro del catálogo cambiaba el significado de las versiones ya aprobadas o simuladas. La población municipal tenía el mismo problema.

## Opciones consideradas
No quedó registrado qué otras opciones se consideraron.

## Decisión
Una versión guarda su población por grupo de edad (migración 023) y congela los parámetros de la enfermedad al enviarse a revisión (migración 024). Mientras es borrador usa los parámetros vivos del catálogo; al salir de borrador usa los congelados.

## Consecuencias
- Todo lo revisable y simulable queda congelado. El trigger `fn_version_aprobada` solo deja simular versiones aprobadas.
- Las versiones anteriores a la 024 no tienen `disease_params` y no hay `CHECK` que lo obligue.
- Una corrección del catálogo no llega a una versión ya enviada: hace falta una versión nueva.
- Todo código que lea una versión fuera de borrador debe usar sus parámetros congelados.
