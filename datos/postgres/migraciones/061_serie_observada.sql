SET client_encoding = 'UTF8';
-- =============================================================================
-- 061_serie_observada.sql
-- Generado por datos/scripts/build_serie_observada.py: no editar a mano.
--
-- Series observadas para calibrar y validar los modelos (D50) y el servicio que
-- las importa (D53).
--
-- - observed_datasets: un conjunto de datos por version, con su enfermedad, su
--   region, su metrica, su periodo, su fuente, su licencia, su corte y su huella.
--   Importar otra vez el mismo codigo crea la version siguiente; nada se edita
--   ni se borra (D52).
-- - observed_points: el valor de cada periodo. Solo series agregadas: ningun
--   registro por persona llega a la base (RNF-I05).
-- - Permiso datasets.upload (EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR) y el rol
--   svc_importacion, duenio de las dos tablas. Nace con LOGIN y sin contrasenia,
--   como en la 032.
-- - La serie de D50: COVID19_NL_2020_SINTOMAS version 1, los casos confirmados de
--   Nuevo Leon por semana de inicio de sintomas, de 2020-03-01 a 2020-07-26
--   (22 semanas, 22259 casos). Sale de
--   datos/observados/covid19_nl_2020_semanal.csv, que documenta la fuente, el
--   corte, la huella y la regla de la ventana.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS observed_datasets (
    id           BIGSERIAL     PRIMARY KEY,
    code         VARCHAR(60)   NOT NULL,
    version      INTEGER       NOT NULL,
    name         VARCHAR(200)  NOT NULL,
    disease_id   BIGINT        NOT NULL,
    region_id    BIGINT        NOT NULL,
    metric       VARCHAR(30)   NOT NULL,
    period       VARCHAR(10)   NOT NULL,
    source       VARCHAR(500)  NOT NULL,
    license      VARCHAR(200)  NOT NULL,
    source_url   VARCHAR(500),
    cutoff_date  DATE          NOT NULL,
    sha256       CHAR(64)      NOT NULL,
    imported_by  BIGINT,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT uq_observed_datasets_version UNIQUE (code, version),
    CONSTRAINT ck_observed_datasets_codigo CHECK (code ~ '^[A-Z0-9_]{3,60}$'),
    CONSTRAINT ck_observed_datasets_version CHECK (version >= 1),
    CONSTRAINT ck_observed_datasets_metrica CHECK (metric IN
        ('casos_confirmados', 'hospitalizaciones', 'defunciones')),
    CONSTRAINT ck_observed_datasets_periodo CHECK (period IN ('semana', 'dia')),
    CONSTRAINT ck_observed_datasets_huella CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT fk_observed_datasets_disease
        FOREIGN KEY (disease_id) REFERENCES diseases (id),
    CONSTRAINT fk_observed_datasets_region
        FOREIGN KEY (region_id) REFERENCES regions (id),
    CONSTRAINT fk_observed_datasets_user
        FOREIGN KEY (imported_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_observed_datasets_serie ON observed_datasets (disease_id, region_id);

CREATE TABLE IF NOT EXISTS observed_points (
    dataset_id    BIGINT   NOT NULL,
    period_start  DATE     NOT NULL,
    value         INTEGER  NOT NULL,

    PRIMARY KEY (dataset_id, period_start),
    CONSTRAINT ck_observed_points_valor CHECK (value >= 0),
    CONSTRAINT fk_observed_points_dataset
        FOREIGN KEY (dataset_id) REFERENCES observed_datasets (id) ON DELETE CASCADE
);

COMMENT ON TABLE observed_datasets IS 'Conjunto de datos observados, agregado por periodo y region, para calibrar y validar (D50, D53). Uno por version; no se edita ni se borra. [importacion]';
COMMENT ON COLUMN observed_datasets.id IS 'Identificador interno. [llave primaria]';
COMMENT ON COLUMN observed_datasets.code IS 'Clave de la serie (mayusculas, digitos y guion bajo). Sus versiones comparten la clave.';
COMMENT ON COLUMN observed_datasets.version IS 'Version de la serie, desde 1. La asigna importacion: la siguiente de su clave.';
COMMENT ON COLUMN observed_datasets.name IS 'Nombre para mostrar.';
COMMENT ON COLUMN observed_datasets.disease_id IS 'Enfermedad. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN observed_datasets.region_id IS 'Region a la que corresponde la serie. Referencia a regions.id. [llave foranea]';
COMMENT ON COLUMN observed_datasets.metric IS 'Que se cuenta: casos_confirmados, hospitalizaciones o defunciones.';
COMMENT ON COLUMN observed_datasets.period IS 'Periodo de cada punto: semana (de domingo a sabado, como el SINAVE) o dia.';
COMMENT ON COLUMN observed_datasets.source IS 'Quien publica los datos y que archivo es.';
COMMENT ON COLUMN observed_datasets.license IS 'Licencia con que se publican. Solo se admiten datos de libre uso (D50).';
COMMENT ON COLUMN observed_datasets.source_url IS 'Donde se descarga la fuente. Opcional.';
COMMENT ON COLUMN observed_datasets.cutoff_date IS 'Fecha del corte de la fuente: la de su ultima actualizacion.';
COMMENT ON COLUMN observed_datasets.sha256 IS 'SHA-256 en hexadecimal del archivo del que salen los puntos: el que se importo o, si lo cargo una migracion, el de la fuente.';
COMMENT ON COLUMN observed_datasets.imported_by IS 'Quien lo importo. Nulo si lo cargo una migracion o si la cuenta se borro. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN observed_datasets.created_at IS 'Cuando se importo.';

COMMENT ON TABLE observed_points IS 'Valor observado de cada periodo de un conjunto (D50, D53). [importacion]';
COMMENT ON COLUMN observed_points.dataset_id IS 'Conjunto. Referencia a observed_datasets.id. [llave primaria] [llave foranea]';
COMMENT ON COLUMN observed_points.period_start IS 'Primer dia del periodo. [llave primaria]';
COMMENT ON COLUMN observed_points.value IS 'Conteo del periodo, entero no negativo.';

-- Con la accion 'upload' de la 034. Una accion nueva haria fallar la 034 al volver a
-- correr el dump, porque rehace el CHECK de las acciones, y la 034 no se edita (D7).
INSERT INTO permissions (code, resource, action, description) VALUES
    ('datasets.upload', 'datasets', 'upload', 'Importar un conjunto de datos observados (D53).')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code = 'datasets.upload'
WHERE r.code IN ('EPIDEMIOLOGO', 'ANALISTA', 'ADMINISTRADOR')
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'svc_importacion') THEN
        CREATE ROLE svc_importacion LOGIN;
    END IF;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM svc_importacion;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM svc_importacion;
GRANT USAGE ON SCHEMA public TO svc_importacion;

GRANT SELECT, INSERT ON observed_datasets, observed_points TO svc_importacion;
GRANT SELECT (id, code) ON diseases TO svc_importacion;
GRANT SELECT (id, code, parent_region_id) ON regions TO svc_importacion;
GRANT INSERT ON audit_log TO svc_importacion;
GRANT USAGE ON SEQUENCE observed_datasets_id_seq TO svc_importacion;

DO $$
DECLARE
    secuencia TEXT := pg_get_serial_sequence('public.audit_log', 'id');
BEGIN
    IF secuencia IS NOT NULL THEN
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO svc_importacion', secuencia);
    END IF;
END;
$$;

COMMENT ON ROLE svc_importacion IS 'Microservicio importacion (5226): duenio de observed_datasets y observed_points.';

INSERT INTO observed_datasets (code, version, name, disease_id, region_id, metric, period, source,
                               license, source_url, cutoff_date, sha256)
SELECT 'COVID19_NL_2020_SINTOMAS', 1,
       'Casos confirmados de COVID-19 en Nuevo León por semana de inicio de síntomas, primera ola de 2020',
       d.id, r.id, 'casos_confirmados', 'semana',
       'Secretaría de Salud, Dirección General de Epidemiología. Datos Abiertos de COVID-19, cierre anual 2020 (COVID19MEXICO2020.zip)',
       'Datos abiertos, Decreto DOF del 20-02-2015, art. 5, fr. III: libre uso, citando la fuente',
       'https://datosabiertos.salud.gob.mx/gobmx/salud/datos_abiertos/historicos/2020/COVID19MEXICO2020.zip',
       DATE '2021-10-31', '64c90685b68a1164bfa093eeef8c8d33d35d93d9d8b8f3d2d6315359a18dab90'
FROM diseases d, regions r
WHERE d.code = 'SARS_COV_2_ANCESTRAL' AND r.code = '19'
ON CONFLICT (code, version) DO NOTHING;

INSERT INTO observed_points (dataset_id, period_start, value)
SELECT o.id, v.inicio::date, v.valor
FROM observed_datasets o
CROSS JOIN (VALUES
    ('2020-03-01', 7),
    ('2020-03-08', 38),
    ('2020-03-15', 40),
    ('2020-03-22', 18),
    ('2020-03-29', 39),
    ('2020-04-05', 95),
    ('2020-04-12', 61),
    ('2020-04-19', 94),
    ('2020-04-26', 167),
    ('2020-05-03', 254),
    ('2020-05-10', 319),
    ('2020-05-17', 359),
    ('2020-05-24', 472),
    ('2020-05-31', 853),
    ('2020-06-07', 1560),
    ('2020-06-14', 1661),
    ('2020-06-21', 2072),
    ('2020-06-28', 2876),
    ('2020-07-05', 3295),
    ('2020-07-12', 3234),
    ('2020-07-19', 2684),
    ('2020-07-26', 2061)
) AS v (inicio, valor)
WHERE o.code = 'COVID19_NL_2020_SINTOMAS' AND o.version = 1
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version, description)
VALUES ('061', 'Series observadas: observed_datasets, observed_points, datasets.upload, svc_importacion y la serie de D50')
ON CONFLICT (version) DO NOTHING;

COMMIT;
