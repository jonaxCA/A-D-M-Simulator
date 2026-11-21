-- =============================================================================
-- 050_dispositivos_de_sesion.sql
-- Dispositivos desde los que una cuenta puede iniciar sesión (D41, RF-A08).
--
-- - session_devices guarda, por cuenta, el SHA-256 del identificador que envía el
--   cliente en cada login y su estado: pendiente, autorizado o revocado. No es la
--   tabla devices (teléfonos que sincronizan, RF-A09).
-- - Dueño: sesiones (svc_sesiones). Registra, autoriza, revoca y anota el último uso;
--   nunca borra ni cambia el dueño o el identificador.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS session_devices (
    id            BIGSERIAL    PRIMARY KEY,
    user_id       BIGINT       NOT NULL,
    device_hash   CHAR(64)     NOT NULL,
    label         VARCHAR(80),
    status        VARCHAR(12)  NOT NULL DEFAULT 'pendiente',
    authorized_by BIGINT,
    authorized_at TIMESTAMPTZ,
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_session_devices      UNIQUE (user_id, device_hash),
    CONSTRAINT fk_session_devices_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_session_devices_auth
        FOREIGN KEY (authorized_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT ck_session_devices_estado
        CHECK (status IN ('pendiente', 'autorizado', 'revocado')),
    CONSTRAINT ck_session_devices_hash
        CHECK (device_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_session_devices_autorizado
        CHECK (status <> 'autorizado' OR authorized_at IS NOT NULL)
);

COMMENT ON TABLE session_devices IS 'Dispositivos desde los que una cuenta inicia sesion (D41). Uno nuevo queda pendiente hasta que la persona o un ADMINISTRADOR lo autoriza. [sesiones]';
COMMENT ON COLUMN session_devices.id IS 'Identificador interno. [llave primaria]';
COMMENT ON COLUMN session_devices.user_id IS 'Cuenta duenia. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN session_devices.device_hash IS 'SHA-256 en hexadecimal del identificador que envia el cliente; el identificador no se guarda.';
COMMENT ON COLUMN session_devices.label IS 'Nombre que el cliente da al dispositivo, para reconocerlo en la lista.';
COMMENT ON COLUMN session_devices.status IS 'pendiente, autorizado o revocado. Solo un autorizado puede abrir sesion.';
COMMENT ON COLUMN session_devices.authorized_by IS 'Quien lo autorizo (la propia cuenta o un ADMINISTRADOR). Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN session_devices.authorized_at IS 'Cuando se autorizo.';
COMMENT ON COLUMN session_devices.last_seen_at IS 'Ultimo inicio de sesion aceptado desde el dispositivo.';
COMMENT ON COLUMN session_devices.created_at IS 'Primera vez que se vio el dispositivo.';

CREATE INDEX IF NOT EXISTS ix_session_devices_user ON session_devices (user_id);

REVOKE ALL ON session_devices FROM svc_sesiones;
GRANT SELECT, INSERT ON session_devices TO svc_sesiones;
GRANT UPDATE (label, status, authorized_by, authorized_at, last_seen_at)
    ON session_devices TO svc_sesiones;
GRANT USAGE ON SEQUENCE session_devices_id_seq TO svc_sesiones;

INSERT INTO schema_migrations (version, description)
VALUES ('050', 'Sesiones: dispositivos autorizados por cuenta (D41, RF-A08)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
