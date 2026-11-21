-- =============================================================================
-- 051_mfa.sql
-- Segundo factor (TOTP, RFC 6238) para los perfiles críticos (D40).
--
-- - user_mfa: el secreto de cada cuenta. enabled pasa a TRUE cuando la persona confirma
--   su primer código; last_counter impide reutilizar un código ya aceptado.
-- - mfa_backup_codes: códigos de respaldo de un solo uso; solo se guarda su SHA-256.
-- - Dueño: auth (svc_auth). Restablecer el MFA de una cuenta borra sus dos filas.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_mfa (
    user_id      BIGINT       PRIMARY KEY,
    secret       VARCHAR(64)  NOT NULL,
    enabled      BOOLEAN      NOT NULL DEFAULT FALSE,
    last_counter BIGINT,
    enrolled_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_user_mfa_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_user_mfa_habilitado
        CHECK (NOT enabled OR enrolled_at IS NOT NULL)
);

DROP TRIGGER IF EXISTS tg_user_mfa_updated_at ON user_mfa;
CREATE TRIGGER tg_user_mfa_updated_at
    BEFORE UPDATE ON user_mfa
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TABLE IF NOT EXISTS mfa_backup_codes (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    BIGINT       NOT NULL,
    code_hash  CHAR(64)     NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_mfa_backup_codes UNIQUE (user_id, code_hash),
    CONSTRAINT fk_mfa_backup_codes_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

COMMENT ON TABLE user_mfa IS 'Secreto TOTP de cada cuenta con segundo factor (D40). [auth]';
COMMENT ON COLUMN user_mfa.user_id IS 'Cuenta. Referencia a users.id. [llave primaria] [llave foranea]';
COMMENT ON COLUMN user_mfa.secret IS 'Secreto compartido en base32. Solo lo lee svc_auth; nunca sale en una respuesta salvo al enrolarse.';
COMMENT ON COLUMN user_mfa.enabled IS 'TRUE cuando la persona confirmo su primer codigo. Pendiente de confirmar, FALSE.';
COMMENT ON COLUMN user_mfa.last_counter IS 'Paso de 30 s del ultimo codigo aceptado; un codigo del mismo paso o anterior se rechaza.';
COMMENT ON COLUMN user_mfa.enrolled_at IS 'Cuando se confirmo el enrolamiento.';
COMMENT ON COLUMN user_mfa.created_at IS 'Cuando se genero el secreto.';
COMMENT ON COLUMN user_mfa.updated_at IS 'Ultima modificacion. La mantiene un trigger.';

COMMENT ON TABLE mfa_backup_codes IS 'Codigos de respaldo de un solo uso del segundo factor (D40). [auth]';
COMMENT ON COLUMN mfa_backup_codes.id IS 'Identificador interno. [llave primaria]';
COMMENT ON COLUMN mfa_backup_codes.user_id IS 'Cuenta. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN mfa_backup_codes.code_hash IS 'SHA-256 en hexadecimal del codigo; el codigo solo se muestra al generarlo.';
COMMENT ON COLUMN mfa_backup_codes.used_at IS 'Cuando se uso; un codigo usado no sirve otra vez.';
COMMENT ON COLUMN mfa_backup_codes.created_at IS 'Cuando se genero.';

REVOKE ALL ON user_mfa, mfa_backup_codes FROM svc_auth;
GRANT SELECT, INSERT, DELETE ON user_mfa, mfa_backup_codes TO svc_auth;
GRANT UPDATE (secret, enabled, last_counter, enrolled_at) ON user_mfa TO svc_auth;
GRANT UPDATE (used_at) ON mfa_backup_codes TO svc_auth;
GRANT USAGE ON SEQUENCE mfa_backup_codes_id_seq TO svc_auth;

INSERT INTO schema_migrations (version, description)
VALUES ('051', 'Auth: segundo factor TOTP y codigos de respaldo para los perfiles criticos (D40)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
