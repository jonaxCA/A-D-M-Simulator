SET client_encoding = 'UTF8';
-- =============================================================================
-- 056_nombres_oficiales_municipios.sql
-- Dominio: catalogos.
--
-- 010_datos_iniciales.sql cargo sin acento el nombre de cuatro de los diez
-- municipios del area metropolitana. Esta migracion les pone el nombre del
-- catalogo de INEGI (datos/geo/nl_catalogo_oficial.json):
--     19018  Garcia                    ->  García
--     19019  San Pedro Garza Garcia    ->  San Pedro Garza García
--     19031  Juarez                    ->  Juárez
--     19046  San Nicolas de los Garza  ->  San Nicolás de los Garza
--
-- Los otros seis de 010 ya coinciden con el catalogo, y los 41 restantes los
-- carga datos/postgres/semillas/nl_municipios_completos.sql con el nombre
-- oficial. Con esta migracion, los 51 municipios de regions quedan como los
-- publica INEGI, y las APIs que los muestran (zonas, regiones, series por
-- municipio) dejan de mezclar nombres con y sin acento.
--
-- POR QUE NO SE CORRIGE 010: ya esta aplicada en todas las bases. Editarla
-- dejaria las instalaciones nuevas con un nombre y las existentes con otro.
--
-- Es idempotente: cada fila se actualiza solo si todavia tiene el nombre sin
-- acento, asi que correrla dos veces no cambia nada y no pisa un nombre que
-- alguien haya corregido por otro medio. Buscar por clave y nombre a la vez
-- tambien la hace segura en una base que no haya corrido 012 (claves 19046 y
-- 19048 intercambiadas): ahi 19046 es Santa Catarina y no se toca. Las tablas
-- que apuntan a regions usan el id, no el nombre, asi que nada mas cambia.
-- =============================================================================

BEGIN;

UPDATE regions r
SET    name = v.oficial
FROM (VALUES
    ('19018', 'Garcia',                   'García'),
    ('19019', 'San Pedro Garza Garcia',   'San Pedro Garza García'),
    ('19031', 'Juarez',                   'Juárez'),
    ('19046', 'San Nicolas de los Garza', 'San Nicolás de los Garza')
) AS v(code, anterior, oficial)
WHERE  r.code  = v.code
  AND  r.level = 'municipio'
  AND  r.name  = v.anterior;

INSERT INTO schema_migrations (version, description)
VALUES ('056', 'Catalogos: nombre oficial de INEGI, con acento, de cuatro municipios de 010')
ON CONFLICT (version) DO NOTHING;

COMMIT;
