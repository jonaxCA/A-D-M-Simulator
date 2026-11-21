SET client_encoding = 'UTF8';
-- =============================================================================
-- 052_instituciones_y_perfiles.sql
-- Institución y región de cada cuenta, y los perfiles nuevos (D42).
--
-- - institutions: catálogo de instituciones. Empieza vacío: no se inventan
--   instituciones; el ADMINISTRADOR las da de alta (servicio usuarios).
-- - users.institution_id y users.region_id: opcionales. Dicen a qué institución
--   y a qué región pertenece la cuenta (perfil). No restringen por sí solos lo
--   que ve: eso es el alcance de la 053 (D43).
-- - Roles INVESTIGADOR y AUTORIDAD_SANITARIA (RF de usuarios, retroalimentación).
--   Sus permisos son un supuesto de solo lectura, a validar con el líder.
-- - svc_usuarios es dueño de institutions.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS institutions (
    id         SERIAL       PRIMARY KEY,
    code       VARCHAR(30)  NOT NULL,
    name       VARCHAR(160) NOT NULL,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_institutions_code UNIQUE (code),
    CONSTRAINT uq_institutions_name UNIQUE (name),
    CONSTRAINT ck_institutions_code CHECK (code = upper(code))
);

COMMENT ON TABLE institutions IS 'Catalogo de instituciones a las que pertenece una cuenta (D42).';

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS institution_id INTEGER,
    ADD COLUMN IF NOT EXISTS region_id      INTEGER;

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS fk_users_institution,
    ADD  CONSTRAINT fk_users_institution
        FOREIGN KEY (institution_id) REFERENCES institutions (id) ON DELETE SET NULL,
    DROP CONSTRAINT IF EXISTS fk_users_region,
    ADD  CONSTRAINT fk_users_region
        FOREIGN KEY (region_id) REFERENCES regions (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_users_institution ON users (institution_id);
CREATE INDEX IF NOT EXISTS ix_users_region      ON users (region_id);

COMMENT ON COLUMN users.institution_id IS 'Institucion de la cuenta; opcional (D42).';
COMMENT ON COLUMN users.region_id IS 'Region asignada a la cuenta; opcional (D42). El alcance que limita datos esta en user_scopes (D43).';

INSERT INTO roles (code, name, description, is_system) VALUES
    ('INVESTIGADOR', 'Investigador',
     'Consulta escenarios, corridas, casos y reportes, y exporta escenarios. Solo lectura (supuesto D42).', TRUE),
    ('AUTORIDAD_SANITARIA', 'Autoridad sanitaria',
     'Consulta escenarios, corridas, casos y reportes. Solo lectura (supuesto D42).', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code IN
    ('catalogs.read', 'scenarios.read', 'simulations.read', 'cases.read',
     'reports.read', 'reports.export')
WHERE r.code IN ('INVESTIGADOR', 'AUTORIDAD_SANITARIA')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code = 'scenarios.export'
WHERE r.code = 'INVESTIGADOR'
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT, UPDATE ON institutions TO svc_usuarios;
GRANT USAGE ON SEQUENCE institutions_id_seq TO svc_usuarios;
GRANT SELECT ON institutions TO svc_roles;
GRANT SELECT ON regions TO svc_usuarios;

INSERT INTO schema_migrations (version, description)
VALUES ('052', 'Identidad: institutions, users.institution_id y users.region_id, roles INVESTIGADOR y AUTORIDAD_SANITARIA (D42)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
