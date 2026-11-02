# D17 - Migraciones SQL numeradas en lugar de Alembic

Fecha: 2026-09-24 (primera migración) · Estado: Por confirmar

## Contexto
La base se versiona con archivos SQL en `datos/postgres/migraciones/`. Cada uno registra su aplicación en `schema_migrations`. `decisiones/todo.md` la listaba como «por registrar o confirmar».

## Opciones consideradas
- Opción A: SQL numerado, sin Alembic.
- Opción B: Alembic.

## Decisión
En uso: opción A. Falta que el equipo la confirme.

## Consecuencias
- Cualquiera lee el esquema sin conocer una herramienta.
- No hay migraciones hacia atrás automáticas.
- Dos personas pueden elegir el mismo número (D16).
