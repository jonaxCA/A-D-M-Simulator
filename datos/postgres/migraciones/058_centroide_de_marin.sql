SET client_encoding = 'UTF8';
-- =============================================================================
-- 058_centroide_de_marin.sql
-- Dominio: catalogos.
--
-- El marcador de un municipio (centroid_lat y centroid_lon) sale de
-- datos/geo/nl_centroides.json, que calcula datos/scripts/build_municipios_inegi.py
-- sobre la geometria oficial de INEGI. Marin (19034) es concavo y su centroide
-- caia fuera de el, dentro de Doctor Gonzalez, a 1.3 km de su frontera: los
-- mapas de marcadores lo dibujaban en el municipio equivocado. El script ahora
-- usa un punto interior cuando el centroide queda fuera (solo pasa con Marin):
--     19034  Marin  (25.874423, -99.964649)  ->  (25.886678, -100.022912)
--
-- Las instalaciones nuevas lo cargan ya corregido desde la semilla
-- nl_municipios_completos.sql (Marin no esta en 010), que corre despues del
-- dump: aqui la fila todavia no existe y no se toca nada. Esta migracion es para
-- las bases que ya existen. Idempotente: solo cambia la fila si todavia tiene el
-- punto viejo, asi que no pisa uno corregido por otro medio.
-- =============================================================================

BEGIN;

UPDATE regions
SET    centroid_lat = 25.886678,
       centroid_lon = -100.022912
WHERE  code = '19034'
  AND  level = 'municipio'
  AND  centroid_lat = 25.874423
  AND  centroid_lon = -99.964649;

INSERT INTO schema_migrations (version, description)
VALUES ('058', 'Catalogos: el marcador de Marin dentro de su municipio (su centroide caia en Doctor Gonzalez)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
