SET client_encoding = 'UTF8';
-- =============================================================================
-- 039_reportes_de_comparacion.sql
-- Dominio: resultados y archivos. Los reportes de una comparacion en el bucket
-- (D30, D35, RF-F17, RF-G16).
--
-- - comparison_reports: los metadatos del reporte (PDF) que sube el ANALISTA o el
--   ADMINISTRADOR desde el escritorio o la web. El archivo vive en Cloud Storage,
--   nunca en la base. La comparacion no se guarda en ningun lado: se identifica
--   por las corridas que compara (run_ids).
-- - La escribe el servicio evidencias, que pasa a ser el de los archivos: recibe
--   SELECT, INSERT y DELETE (un reporte se sube o se borra, no se edita) y lee el
--   id de simulation_runs para revisar que las corridas existan.
-- - case_attachments.storage_path cambia su comentario: las evidencias nuevas van
--   al prefijo evidencias/ del bucket (RNF-K18). La 008 no se edita (D7).
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS comparison_reports (
    id           BIGSERIAL     PRIMARY KEY,
    run_ids      BIGINT[]      NOT NULL,
    title        VARCHAR(200),
    storage_path VARCHAR(255)  NOT NULL,
    mime_type    VARCHAR(80)   NOT NULL DEFAULT 'application/pdf',
    size_bytes   BIGINT        NOT NULL,
    sha256       CHAR(64)      NOT NULL,
    privacy      VARCHAR(20)   NOT NULL DEFAULT 'privado',
    uploaded_by  BIGINT        NOT NULL,
    uploaded_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_comparison_reports_path UNIQUE (storage_path),
    CONSTRAINT fk_comparison_reports_uploader
        FOREIGN KEY (uploaded_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_comparison_reports_runs CHECK (cardinality(run_ids) BETWEEN 1 AND 100),
    CONSTRAINT ck_comparison_reports_size CHECK (size_bytes > 0 AND size_bytes <= 20971520),
    CONSTRAINT ck_comparison_reports_mime CHECK (mime_type = 'application/pdf'),
    CONSTRAINT ck_comparison_reports_hash CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_comparison_reports_privacy CHECK (privacy = 'privado')
);

CREATE INDEX IF NOT EXISTS ix_comparison_reports_runs ON comparison_reports USING GIN (run_ids);
CREATE INDEX IF NOT EXISTS ix_comparison_reports_hash ON comparison_reports (sha256);

COMMENT ON TABLE comparison_reports IS
    'Reportes de una comparacion (PDF) subidos desde el escritorio o la web (D35, RF-F17). El archivo vive en Cloud Storage; aqui solo sus metadatos. Los escribe el servicio evidencias.';
COMMENT ON COLUMN comparison_reports.id IS 'Identificador del reporte. [llave primaria]';
COMMENT ON COLUMN comparison_reports.run_ids IS 'Corridas que compara el reporte (simulation_runs.id), en el orden en que se compararon.';
COMMENT ON COLUMN comparison_reports.title IS 'Titulo que le da quien lo sube. Opcional.';
COMMENT ON COLUMN comparison_reports.storage_path IS 'Ruta del objeto en el bucket: reportes/{id de la primera corrida}/{uuid}.pdf.';
COMMENT ON COLUMN comparison_reports.mime_type IS 'Tipo validado por el contenido en el servidor: solo application/pdf.';
COMMENT ON COLUMN comparison_reports.size_bytes IS 'Tamanio del archivo; hasta 20 MB.';
COMMENT ON COLUMN comparison_reports.sha256 IS 'Huella SHA-256 del contenido, revisada al subirlo (RNF-C09).';
COMMENT ON COLUMN comparison_reports.privacy IS 'Siempre privado: se abre solo con una URL firmada que vence (RNF-D17).';
COMMENT ON COLUMN comparison_reports.uploaded_by IS 'Quien lo subio. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN comparison_reports.uploaded_at IS 'Cuando se subio.';
COMMENT ON COLUMN case_attachments.storage_path IS
    'Ruta del objeto en el bucket: evidencias/{case_id}/{uuid}.{ext} (D30); las subidas antes de D2 conservan evidence/{case_id}/...';

GRANT SELECT, INSERT, DELETE ON comparison_reports TO svc_evidencias;
GRANT USAGE ON SEQUENCE comparison_reports_id_seq TO svc_evidencias;
GRANT SELECT (id) ON simulation_runs TO svc_evidencias;

COMMENT ON ROLE svc_evidencias IS 'Microservicio evidencias (5224): duenio de case_attachments y comparison_reports.';

INSERT INTO schema_migrations (version, description)
VALUES ('039', 'Reportes de una comparacion en el bucket: comparison_reports y su rol (D30, D35)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
