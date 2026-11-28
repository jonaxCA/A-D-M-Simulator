SET client_encoding = 'UTF8';
-- =============================================================================
-- 062_calibraciones.sql
-- Dominio: simulacion. Calibracion de seir-ref contra una serie observada (D50).
--
-- - calibrations: una calibracion por peticion, con su conjunto observado (061),
--   su motor y su version, el metodo y su version, la configuracion con que
--   corre (rangos, muestras, semillas, cuantil y ventanas), el estado de la
--   regla 7, los intentos (D38), el avance y, al completarse, el resultado entero
--   en JSONB: parametros con su intervalo, aceptadas, banda semanal y metricas.
--   Con la misma configuracion el resultado es el mismo, asi que reencolarla no
--   duplica nada.
-- - Permiso calibrations.run (EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR): lanzar y
--   cancelar. Consultar usa simulations.read. Con la accion 'run', que ya admite
--   el CHECK de la 034.
-- - El rol svc_calibracion, duenio de calibrations. Nace con LOGIN y sin
--   contrasenia, como en la 032. audit_log.entity_type no tiene CHECK: la
--   entidad 'calibration' no pide migracion.
-- - Es la 062, de la reserva de E. Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS calibrations (
    id              BIGSERIAL     PRIMARY KEY,
    dataset_id      BIGINT        NOT NULL,
    engine          VARCHAR(20)   NOT NULL,
    engine_version  VARCHAR(40)   NOT NULL,
    method          VARCHAR(30)   NOT NULL,
    method_version  VARCHAR(30)   NOT NULL,
    config          JSONB         NOT NULL,
    status          VARCHAR(20)   NOT NULL DEFAULT 'encolado',
    attempts        SMALLINT      NOT NULL DEFAULT 0,
    progress        SMALLINT      NOT NULL DEFAULT 0,
    result          JSONB,
    error           TEXT,
    requested_by    BIGINT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,

    CONSTRAINT ck_calibrations_motor CHECK (engine IN ('seir-ref')),
    CONSTRAINT ck_calibrations_config CHECK (jsonb_typeof(config) = 'object'),
    CONSTRAINT ck_calibrations_estado CHECK (status IN
        ('encolado', 'ejecutando', 'completado', 'fallido', 'cancelado')),
    CONSTRAINT ck_calibrations_intentos CHECK (attempts BETWEEN 0 AND 3),
    CONSTRAINT ck_calibrations_avance CHECK (progress BETWEEN 0 AND 100),
    CONSTRAINT ck_calibrations_resultado CHECK (
        (status = 'completado') = (result IS NOT NULL)),
    CONSTRAINT ck_calibrations_fin CHECK (
        (status IN ('completado', 'fallido', 'cancelado')) = (finished_at IS NOT NULL)),
    CONSTRAINT fk_calibrations_dataset
        FOREIGN KEY (dataset_id) REFERENCES observed_datasets (id),
    CONSTRAINT fk_calibrations_user
        FOREIGN KEY (requested_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_calibrations_pendientes
    ON calibrations (status) WHERE status IN ('encolado', 'ejecutando');
CREATE INDEX IF NOT EXISTS ix_calibrations_dataset ON calibrations (dataset_id);

COMMENT ON TABLE calibrations IS 'Calibracion de un motor contra un conjunto observado: ABC por rechazo (D50). La lanza calibracion y la corre calibracion-trabajador. [calibracion]';
COMMENT ON COLUMN calibrations.id IS 'Identificador interno. [llave primaria]';
COMMENT ON COLUMN calibrations.dataset_id IS 'Serie observada contra la que se calibra. Referencia a observed_datasets.id. [llave foranea]';
COMMENT ON COLUMN calibrations.engine IS 'Motor que se calibra. Solo seir-ref por ahora (D50).';
COMMENT ON COLUMN calibrations.engine_version IS 'Version del motor: la calibracion solo vale para ella (D50).';
COMMENT ON COLUMN calibrations.method IS 'Metodo de calibracion: abc-rechazo.';
COMMENT ON COLUMN calibrations.method_version IS 'Version del algoritmo de procesamiento/calibracion (calibracion-0.1).';
COMMENT ON COLUMN calibrations.config IS 'Lo pedido: muestras, semillas, cuantil y semilla del muestreo. Con esto y el conjunto la calibracion se repite bit a bit.';
COMMENT ON COLUMN calibrations.status IS 'encolado, ejecutando, completado, fallido o cancelado.';
COMMENT ON COLUMN calibrations.attempts IS 'Veces que el trabajador la empezo. Al arrancar reencola las interrumpidas hasta 3 intentos (D38).';
COMMENT ON COLUMN calibrations.progress IS 'Avance de 0 a 100. El vivo esta en Redis; aqui, el del ultimo cambio de estado.';
COMMENT ON COLUMN calibrations.result IS 'El resultado completo: parametros con mediana y p5-p95, aceptadas, banda semanal, metricas por ventana y versiones. Solo si esta completada.';
COMMENT ON COLUMN calibrations.error IS 'Por que fallo, en espanol. Nulo si no fallo.';
COMMENT ON COLUMN calibrations.requested_by IS 'Quien la pidio. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN calibrations.created_at IS 'Cuando se pidio.';
COMMENT ON COLUMN calibrations.started_at IS 'Cuando la empezo el trabajador por ultima vez.';
COMMENT ON COLUMN calibrations.finished_at IS 'Cuando termino, fallo o se cancelo.';

INSERT INTO permissions (code, resource, action, description) VALUES
    ('calibrations.run', 'calibrations', 'run', 'Lanzar y cancelar una calibracion (D50).')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code = 'calibrations.run'
WHERE r.code IN ('EPIDEMIOLOGO', 'ANALISTA', 'ADMINISTRADOR')
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_calibracion') THEN
        CREATE ROLE svc_calibracion LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_calibracion;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_calibracion;
GRANT USAGE ON SCHEMA public TO svc_calibracion;

GRANT SELECT, INSERT, UPDATE ON calibrations TO svc_calibracion;
GRANT USAGE ON SEQUENCE calibrations_id_seq TO svc_calibracion;
GRANT SELECT ON observed_datasets, observed_points, region_age_groups TO svc_calibracion;
GRANT SELECT (id, code, name, default_params, is_active) ON diseases TO svc_calibracion;
GRANT SELECT (id, code, name, level, parent_region_id) ON regions TO svc_calibracion;
GRANT SELECT (id, username, full_name) ON users TO svc_calibracion;
GRANT INSERT ON audit_log TO svc_calibracion;

DO $$
DECLARE
    secuencia TEXT := pg_get_serial_sequence('public.audit_log', 'id');
BEGIN
    IF secuencia IS NOT NULL THEN
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO svc_calibracion', secuencia);
    END IF;
END;
$$;

COMMENT ON ROLE svc_calibracion IS 'Microservicio calibracion (5246) y su trabajador: duenio de calibrations.';

INSERT INTO schema_migrations (version, description)
VALUES ('062', 'Simulacion: calibrations, el permiso calibrations.run y el rol svc_calibracion (D50)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
