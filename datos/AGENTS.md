# AGENTS.md — datos

> **Estado: Vigente** · 2026-10-07 · Complementa el `AGENTS.md` de la raíz.

## Migraciones nuevas

1. Confirma el número con la persona: hay números reservados.
2. Copia la estructura de la 017: encabezado, `BEGIN;` … `COMMIT;` y registro en `schema_migrations`.
3. Hazla idempotente (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`) y agrega `COMMENT ON` a todo lo nuevo.
4. Copia el archivo tal cual al final de `postgres/dump_completo.sql` y actualiza el número de
   migraciones que menciona el encabezado del dump.
5. Si creaste tablas o secuencias, avisa en el PR: en las bases que ya existen hay que volver a
   correr los `GRANT` del paso 3 de `docs/INSTALACION.md`.

## Reglas

- Los datos sintéticos van solo en `postgres/semillas/`, nunca en migraciones.
- Los `.sql` van en UTF-8. Un archivo que se carga por su cuenta (una semilla, o una migración
  fuera del dump) empieza con `SET client_encoding = 'UTF8';`, en ASCII y antes de cualquier
  acento; el dump ya lo trae en su encabezado. Sin esa línea, `psql` en Windows lo lee como
  WIN1252 y los acentos quedan dañados en la base. Los generadores de semillas escriben UTF-8
  también en Windows.
- Las semillas no se editan a mano: se cambia su generador (`scripts/build_regiones_sql.py` o
  `scripts/gen_demo_data.py`) y se regenera el archivo. `backend_web/tests/test_archivos_sql.py`
  falla si el archivo ya no sale de su script; en la de demostración solo pueden cambiar los
  tres hashes de contraseña.
- No relajes las reglas de negocio de la base para que el código pase: `fn_version_aprobada`,
  el CHECK que impide aprobar la versión propia y el trigger que hace de `audit_log` una tabla
  de solo inserción.
- No edites a mano `censo/` ni `geo/`. Si un dato oficial está mal, corrígelo desde la fuente
  que cita el archivo.
- `population_size` va de 1,000 a 20,000,000 (migración 023); Nuevo León completo
  (5,784,442 habitantes) cabe.
