SET client_encoding = 'UTF8';
-- =============================================================================
-- 053_alcances_de_usuario.sql
-- Permisos con alcance por región o institución (D43).
--
-- - user_scopes: una fila por región o por institución a las que se limita una
--   cuenta. Sin filas, la cuenta es nacional (sin límite). El permiso por
--   recurso y operación sigue en role_permissions; esto solo recorta los datos.
-- - La región cubre también a sus hijas (regions.parent_region_id); lo expande
--   el servicio roles al responder.
-- - svc_roles es dueño de user_scopes y lee regions e institutions.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_scopes (
    id             BIGSERIAL   PRIMARY KEY,
    user_id        BIGINT      NOT NULL,
    region_id      INTEGER,
    institution_id INTEGER,
    assigned_by    BIGINT,
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_user_scopes_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_scopes_region
        FOREIGN KEY (region_id) REFERENCES regions (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_scopes_institution
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_scopes_assigned_by
        FOREIGN KEY (assigned_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT ck_user_scopes_uno CHECK ((region_id IS NULL) <> (institution_id IS NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_scopes_region
    ON user_scopes (user_id, region_id) WHERE region_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_scopes_institution
    ON user_scopes (user_id, institution_id) WHERE institution_id IS NOT NULL;

COMMENT ON TABLE user_scopes IS 'Region o institucion a la que se limita una cuenta; sin filas la cuenta es nacional (D43).';

GRANT SELECT, INSERT, DELETE ON user_scopes TO svc_roles;
GRANT USAGE ON SEQUENCE user_scopes_id_seq TO svc_roles;
GRANT SELECT ON regions TO svc_roles;

INSERT INTO schema_migrations (version, description)
VALUES ('053', 'Identidad: user_scopes, alcance por region o institucion de una cuenta (D43)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
