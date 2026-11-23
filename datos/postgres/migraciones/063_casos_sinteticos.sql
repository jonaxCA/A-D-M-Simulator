-- =============================================================================
-- 063_casos_sinteticos.sql
-- Dominio: vigilancia.
--
-- El comentario de cases de la 008 dice que los casos alimentan la
-- recalibracion del modelo. En la demostracion son sinteticos (RNF-I15) y no se
-- usan para calibrar: se calibra con una serie publica agregada, la de la 061
-- (D50). La 008 no se edita (D7).
-- =============================================================================

BEGIN;

COMMENT ON TABLE cases IS 'Casos capturados en campo desde la app movil. En la demostracion son sinteticos (RNF-I15) y no se usan para calibrar (D50).';

INSERT INTO schema_migrations (version, description)
VALUES ('063', 'Vigilancia: cases es sintetica y no calibra (D50)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
