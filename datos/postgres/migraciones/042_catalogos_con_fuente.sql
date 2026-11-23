SET client_encoding = 'UTF8';
-- =============================================================================
-- 042_catalogos_con_fuente.sql
-- Dominio: catálogos. Definiciones de caso versionadas, clasificación de las
-- enfermedades, versiones e intervalos de los parámetros y supuestos de
-- efectividad de cada tipo de intervención (D58, D7 del checklist).
--
-- - diseases: vía de transmisión y códigos CIE-10, con su fuente.
-- - case_definitions: la definición operacional de caso de cada enfermedad, con
--   versiones (borrador, vigente o retirada; una vigente por enfermedad). Trae
--   las de la DGE: enfermedad respiratoria viral (septiembre de 2023) para
--   COVID-19 e influenza, la de influenza de marzo de 2021 ya retirada, y las de
--   dengue, paludismo y zika de marzo de 2021. El texto es literal; solo se unen
--   los renglones y las viñetas van separadas por punto y coma. PATOGENO_X es
--   hipotético y no tiene definición.
-- - disease_parameter_versions: cada cambio de diseases.default_params es una
--   versión. La 1 son los parámetros al crear el historial; la 2 de COVID-19 e
--   influenza agrega los intervalos que ya traían las fuentes citadas
--   (intervalo: min, max y tipo IC95, RIC o rango).
-- - intervention_effectiveness: el supuesto de efectividad de cada tipo de
--   intervención (eficacia, reducción o detección), general o por enfermedad,
--   con valor de referencia, rango, fuente y marca de supuesto. No cambia lo
--   que se simula: cada intervención sigue llevando su propio valor.
-- - Los datos por enfermedad van juntos al final, marcados: la semilla de la
--   demostración los repite (gen_demo_data.py los lee de aquí), porque en una
--   instalación limpia DENGUE_DEMO, ZIKA_DEMO y MALARIA_DEMO llegan con ella,
--   después del dump.
-- - Es la 042, reservada para D: no rehace ningún CHECK de otra migración.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Clasificación de las enfermedades
-- -----------------------------------------------------------------------------
ALTER TABLE diseases
    ADD COLUMN IF NOT EXISTS transmission          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS icd10                 VARCHAR(60),
    ADD COLUMN IF NOT EXISTS classification_source TEXT;

ALTER TABLE diseases
    DROP CONSTRAINT IF EXISTS ck_diseases_transmission,
    ADD  CONSTRAINT ck_diseases_transmission
        CHECK (transmission IS NULL OR transmission IN ('respiratoria', 'vectorial'));

COMMENT ON COLUMN diseases.transmission IS 'Vía de transmisión: respiratoria (de persona a persona) o vectorial. NULL si no está clasificada (PATOGENO_X es hipotético).';
COMMENT ON COLUMN diseases.icd10 IS 'Códigos CIE-10 de la enfermedad, como los cita su fuente.';
COMMENT ON COLUMN diseases.classification_source IS 'Fuente de la vía de transmisión y de los códigos CIE-10.';

-- -----------------------------------------------------------------------------
-- case_definitions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_definitions (
    id           BIGSERIAL     PRIMARY KEY,
    disease_id   SMALLINT      NOT NULL,
    version      INTEGER       NOT NULL,
    status       VARCHAR(20)   NOT NULL DEFAULT 'borrador',
    criteria     JSONB         NOT NULL,
    source       TEXT          NOT NULL,
    source_url   TEXT,
    created_by   BIGINT,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    published_by BIGINT,
    published_at TIMESTAMPTZ,
    retired_at   TIMESTAMPTZ,

    CONSTRAINT fk_case_definitions_disease
        FOREIGN KEY (disease_id)   REFERENCES diseases (id) ON DELETE CASCADE,
    CONSTRAINT fk_case_definitions_created_by
        FOREIGN KEY (created_by)   REFERENCES users (id)    ON DELETE SET NULL,
    CONSTRAINT fk_case_definitions_published_by
        FOREIGN KEY (published_by) REFERENCES users (id)    ON DELETE SET NULL,
    CONSTRAINT uq_case_definitions_version UNIQUE (disease_id, version),
    CONSTRAINT ck_case_definitions_version CHECK (version >= 1),
    CONSTRAINT ck_case_definitions_status CHECK (status IN ('borrador', 'vigente', 'retirada')),
    CONSTRAINT ck_case_definitions_criteria CHECK (
        jsonb_typeof(criteria) = 'array' AND jsonb_array_length(criteria) >= 1),
    CONSTRAINT ck_case_definitions_source CHECK (char_length(btrim(source)) >= 3),
    -- Publicada (vigente o retirada) sabe cuándo; solo una retirada tiene fecha de retiro.
    CONSTRAINT ck_case_definitions_publicada CHECK (status = 'borrador' OR published_at IS NOT NULL),
    CONSTRAINT ck_case_definitions_retiro CHECK ((status = 'retirada') = (retired_at IS NOT NULL))
);

-- Una sola definición vigente por enfermedad.
CREATE UNIQUE INDEX IF NOT EXISTS uq_case_definitions_vigente
    ON case_definitions (disease_id) WHERE status = 'vigente';

COMMENT ON TABLE case_definitions IS
    'Definiciones operacionales de caso de cada enfermedad, versionadas (D58). Las escribe enfermedades: un borrador se edita; al publicarlo pasa a vigente y la vigente anterior a retirada. Lo publicado no cambia; solo se va en cascada si se borra la enfermedad, que el sistema da de baja lógica.';
COMMENT ON COLUMN case_definitions.id IS 'Identificador de la versión.';
COMMENT ON COLUMN case_definitions.disease_id IS 'Enfermedad. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN case_definitions.version IS 'Número de versión dentro de la enfermedad, desde 1.';
COMMENT ON COLUMN case_definitions.status IS 'borrador (se edita), vigente (una por enfermedad) o retirada.';
COMMENT ON COLUMN case_definitions.criteria IS 'Lista de criterios: [{clasificacion, texto}], por ejemplo caso sospechoso, caso confirmado o dengue con signos de alarma.';
COMMENT ON COLUMN case_definitions.source IS 'Documento de donde sale el texto: institución, título, fecha y páginas.';
COMMENT ON COLUMN case_definitions.source_url IS 'Dirección del documento, si la hay.';
COMMENT ON COLUMN case_definitions.created_by IS 'Quien la capturó; NULL si la cargó una migración. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN case_definitions.created_at IS 'Alta del borrador.';
COMMENT ON COLUMN case_definitions.published_by IS 'Quien la publicó; NULL si la cargó una migración. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN case_definitions.published_at IS 'Cuándo pasó a vigente.';
COMMENT ON COLUMN case_definitions.retired_at IS 'Cuándo la reemplazó otra versión.';

-- -----------------------------------------------------------------------------
-- disease_parameter_versions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS disease_parameter_versions (
    id          BIGSERIAL    PRIMARY KEY,
    disease_id  SMALLINT     NOT NULL,
    version     INTEGER      NOT NULL,
    params      JSONB        NOT NULL,
    reason      TEXT,
    changed_by  BIGINT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_disease_parameter_versions_disease
        FOREIGN KEY (disease_id) REFERENCES diseases (id) ON DELETE CASCADE,
    CONSTRAINT fk_disease_parameter_versions_user
        FOREIGN KEY (changed_by) REFERENCES users (id)    ON DELETE SET NULL,
    CONSTRAINT uq_disease_parameter_versions UNIQUE (disease_id, version),
    CONSTRAINT ck_disease_parameter_versions_version CHECK (version >= 1),
    CONSTRAINT ck_disease_parameter_versions_params CHECK (jsonb_typeof(params) = 'object')
);

COMMENT ON TABLE disease_parameter_versions IS
    'Cada versión de los parámetros de una enfermedad (diseases.default_params), completa (D58). La escribe parametros en la misma transacción que el cambio; no se edita ni se borra (D52), salvo en cascada si se borra la enfermedad, que el sistema da de baja lógica.';
COMMENT ON COLUMN disease_parameter_versions.id IS 'Identificador.';
COMMENT ON COLUMN disease_parameter_versions.disease_id IS 'Enfermedad. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN disease_parameter_versions.version IS 'Número de versión dentro de la enfermedad, desde 1.';
COMMENT ON COLUMN disease_parameter_versions.params IS 'Los parámetros completos de esa versión, como quedaron en default_params.';
COMMENT ON COLUMN disease_parameter_versions.reason IS 'Motivo del cambio, si se dio.';
COMMENT ON COLUMN disease_parameter_versions.changed_by IS 'Quien hizo el cambio; NULL si lo hizo una migración. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN disease_parameter_versions.created_at IS 'Cuándo se guardó la versión.';

-- -----------------------------------------------------------------------------
-- intervention_effectiveness
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intervention_effectiveness (
    id                   BIGSERIAL     PRIMARY KEY,
    intervention_type_id SMALLINT      NOT NULL,
    parameter            VARCHAR(20)   NOT NULL,
    disease_id           SMALLINT,
    reference_value      NUMERIC(6,4),
    range_min            NUMERIC(6,4),
    range_max            NUMERIC(6,4),
    source               TEXT          NOT NULL,
    is_assumption        BOOLEAN       NOT NULL,
    updated_by           BIGINT,
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT fk_intervention_effectiveness_type
        FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id) ON DELETE RESTRICT,
    CONSTRAINT fk_intervention_effectiveness_disease
        FOREIGN KEY (disease_id) REFERENCES diseases (id) ON DELETE CASCADE,
    CONSTRAINT fk_intervention_effectiveness_user
        FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT uq_intervention_effectiveness
        UNIQUE NULLS NOT DISTINCT (intervention_type_id, parameter, disease_id),
    CONSTRAINT ck_intervention_effectiveness_parameter
        CHECK (parameter IN ('eficacia', 'reduccion', 'deteccion')),
    CONSTRAINT ck_intervention_effectiveness_rango CHECK (
        (reference_value IS NULL OR reference_value BETWEEN 0 AND 1)
        AND (range_min IS NULL OR range_min BETWEEN 0 AND 1)
        AND (range_max IS NULL OR range_max BETWEEN 0 AND 1)
        AND (range_min IS NULL OR range_max IS NULL OR range_min <= range_max)
        AND (reference_value IS NULL OR range_min IS NULL OR range_min <= reference_value)
        AND (reference_value IS NULL OR range_max IS NULL OR reference_value <= range_max)),
    CONSTRAINT ck_intervention_effectiveness_source CHECK (char_length(btrim(source)) >= 3)
);

COMMENT ON TABLE intervention_effectiveness IS
    'Supuestos de efectividad de cada tipo de intervención (D58): el valor de referencia y el rango de su parámetro de efecto, general (disease_id NULL) o para una enfermedad, con su fuente o la marca de supuesto. Lo escribe tipos-intervencion. No cambia lo que se simula: cada intervención lleva su propio valor.';
COMMENT ON COLUMN intervention_effectiveness.id IS 'Identificador.';
COMMENT ON COLUMN intervention_effectiveness.intervention_type_id IS 'Tipo de intervención. Referencia a intervention_types.id. [llave foranea]';
COMMENT ON COLUMN intervention_effectiveness.parameter IS 'Parámetro de efecto del tipo, como en su param_schema: eficacia, reduccion o deteccion.';
COMMENT ON COLUMN intervention_effectiveness.disease_id IS 'Enfermedad a la que aplica; NULL si es general. Referencia a diseases.id. [llave foranea]';
COMMENT ON COLUMN intervention_effectiveness.reference_value IS 'Valor de referencia, de 0 a 1.';
COMMENT ON COLUMN intervention_effectiveness.range_min IS 'Límite inferior del rango plausible, de 0 a 1.';
COMMENT ON COLUMN intervention_effectiveness.range_max IS 'Límite superior del rango plausible, de 0 a 1.';
COMMENT ON COLUMN intervention_effectiveness.source IS 'Fuente con su cita, o el razonamiento del supuesto.';
COMMENT ON COLUMN intervention_effectiveness.is_assumption IS 'true si el valor es un supuesto o una derivación del equipo, no una medición directa de la fuente.';
COMMENT ON COLUMN intervention_effectiveness.updated_by IS 'Último que lo cambió; NULL si lo cargó una migración. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN intervention_effectiveness.updated_at IS 'Último cambio.';

-- -----------------------------------------------------------------------------
-- Datos por enfermedad
-- -----------------------------------------------------------------------------
-- <datos-por-enfermedad>
-- Este bloque lo repite datos/postgres/semillas/demo_datos_nl.sql (gen_demo_data.py lo
-- lee de aquí): en una instalación limpia, DENGUE_DEMO, ZIKA_DEMO y MALARIA_DEMO
-- llegan con esa semilla, después del dump. Todo es idempotente.
UPDATE diseases SET transmission = 'respiratoria', icd10 = 'U07.1, U07.2',
       classification_source = 'OMS, códigos CIE-10 de uso de emergencia para COVID-19 (U07.1 virus identificado, U07.2 virus no identificado). https://www.who.int/standards/classifications/frequently-asked-questions/covid-19-emergency-icd-codes'
 WHERE code = 'SARS_COV_2_ANCESTRAL' AND classification_source IS NULL;
UPDATE diseases SET transmission = 'respiratoria', icd10 = 'J09-J11',
       classification_source = 'Secretaría de Salud, DGE. Definiciones operacionales de enfermedades sujetas a vigilancia convencional, marzo de 2021, p. 31.'
 WHERE code = 'INFLUENZA_ESTACIONAL' AND classification_source IS NULL;
UPDATE diseases SET transmission = 'vectorial', icd10 = 'A97.0, A97.1, A97.2, A97.9',
       classification_source = 'Secretaría de Salud, DGE. Definiciones operacionales de enfermedades sujetas a vigilancia convencional, marzo de 2021, pp. 60-61 (transmitido por Aedes aegypti y Ae. albopictus).'
 WHERE code = 'DENGUE_DEMO' AND classification_source IS NULL;
UPDATE diseases SET transmission = 'vectorial', icd10 = 'U06.9',
       classification_source = 'Secretaría de Salud, DGE. Definiciones operacionales de enfermedades sujetas a vigilancia convencional, marzo de 2021, pp. 66-67.'
 WHERE code = 'ZIKA_DEMO' AND classification_source IS NULL;
UPDATE diseases SET transmission = 'vectorial', icd10 = 'B50, B51',
       classification_source = 'Secretaría de Salud, DGE. Definiciones operacionales de enfermedades sujetas a vigilancia convencional, marzo de 2021, p. 62.'
 WHERE code = 'MALARIA_DEMO' AND classification_source IS NULL;

-- Enfermedad respiratoria viral (COVID-19 e influenza): DGE, septiembre de 2023.
WITH erv AS (
    SELECT jsonb_build_array(
        jsonb_build_object('clasificacion', 'Caso sospechoso de enfermedad respiratoria viral', 'texto',
            'Persona de cualquier edad que en los últimos 5 días para casos de ETI (Ambulatorios) y en los últimos 7 días para casos IRAG (Hospitalizados) haya presentado al menos uno de los siguientes signos y síntomas: tos, fiebre o cefalea*. Acompañados de al menos uno de los siguientes signos o síntomas: Disnea; Mialgias; Artralgias; Odinofagia; Escalofríos; Dolor torácico; Rinorrea; Polipnea; Anosmia; Disgeusia; Conjuntivitis. *En menores de cinco años de edad, la irritabilidad puede sustituir a la cefalea.'),
        jsonb_build_object('clasificacion', 'Caso de infección respiratoria aguda grave (IRAG)', 'texto',
            'Toda persona que cumpla con la definición de caso sospechoso de Enfermedad Respiratoria Viral y con presencia de alguno de los siguientes datos de gravedad: disnea y/o dolor torácico.'),
        jsonb_build_object('clasificacion', 'Caso de enfermedad tipo influenza (ETI)', 'texto',
            'Toda persona que cumpla con la definición de caso sospechoso de Enfermedad Respiratoria Viral en los últimos cinco días de inicio de los datos clínicos sin la presencia de datos de gravedad (disnea y/o dolor torácico).'),
        jsonb_build_object('clasificacion', 'Caso confirmado por laboratorio', 'texto',
            'Persona que cumpla con la definición operacional de caso sospechoso y que cuente con diagnóstico confirmado por laboratorio mediante la prueba RT-PCR. Son válidos para el sistema de vigilancia epidemiológica los resultados emitidos por los miembros del SINAVE (Red Nacional de Laboratorios de Salud Pública y Laboratorios de apoyo a la vigilancia epidemiológica-RNLSP/LAVE-) y aquellos laboratorios que hayan sido aprobados mediante la evaluación a la competencia técnica por el InDRE, registrando en el informe de prueba el estuche comercial utilizado para el procesamiento.'),
        jsonb_build_object('clasificacion', 'Defunción con diagnóstico confirmado por laboratorio', 'texto',
            'Persona fallecida que cumpla con la definición operacional de caso sospechoso, que haya sido confirmado por laboratorio mediante la prueba RT-PCR.')
    ) AS criterios
)
INSERT INTO case_definitions (disease_id, version, status, criteria, source, source_url, published_at)
SELECT d.id, v.version, 'vigente', erv.criterios,
       'Secretaría de Salud, Dirección General de Epidemiología. Lineamiento estandarizado para la vigilancia epidemiológica y por laboratorio de la enfermedad respiratoria viral, septiembre de 2023, pp. 30-31. Las definiciones operacionales solo las actualiza el CONAVE.',
       'https://www.gob.mx/cms/uploads/attachment/file/636504/Lineamiento_Estandarizado_Para_La_Vigilancia_Epidemiol_gica_Y_Por_Laboratorio_De_La_Enfermedad_Respiratoria_Viral_-_Septiembre_2023.pdf',
       now()
FROM erv, (VALUES ('SARS_COV_2_ANCESTRAL', 1), ('INFLUENZA_ESTACIONAL', 2)) AS v(code, version)
JOIN diseases d ON d.code = v.code
ON CONFLICT (disease_id, version) DO NOTHING;

-- Lo que sigue sale de un mismo documento de la DGE, de marzo de 2021.
INSERT INTO case_definitions (disease_id, version, status, criteria, source, source_url, published_at, retired_at)
SELECT d.id, 1, v.status, v.criterios,
       'Secretaría de Salud, Dirección General de Epidemiología. Vigilancia epidemiológica convencional de casos nuevos de enfermedad: definiciones operacionales de enfermedades sujetas a vigilancia convencional, marzo de 2021, ' || v.paginas || '.',
       'https://epidemiologia.salud.gob.mx/gobmx/salud/documentos/manuales/DefinicionesOperacionales_Padecimientos_Sujetos_a_VE.pdf',
       now(), CASE WHEN v.status = 'retirada' THEN now() END
FROM (VALUES
    -- Influenza de 2021: la reemplaza la de enfermedad respiratoria viral de 2023 (versión 2).
    ('INFLUENZA_ESTACIONAL', 'retirada', 'p. 31', jsonb_build_array(
        jsonb_build_object('clasificacion', 'Caso sospechoso de influenza', 'texto',
            'Se considera caso sospechoso de influenza a todo caso o defunción que cumpla con los criterios de Enfermedad Tipo Influenza (ETI) o Infección Respiratoria Aguda Grave (IRAG).'),
        jsonb_build_object('clasificacion', 'Enfermedad tipo influenza (ETI)', 'texto',
            'Persona de cualquier edad que presente o refiera haber tenido fiebre mayor o igual a 38° C, tos y cefalea, acompañadas de uno o más de los siguientes signos o síntomas: rinorrea, coriza, artralgias, mialgias, postración, odinofagia, dolor torácico, dolor abdominal, congestión nasal o diarrea. Importante: En menores de cinco años de edad, se considera un signo cardinal la irritabilidad, en sustitución de la cefalea; En mayores de 65 años o en pacientes inmunocomprometidos, no se requerirá la fiebre como signo cardinal.'),
        jsonb_build_object('clasificacion', 'Infección respiratoria aguda grave (IRAG)', 'texto',
            'Persona de cualquier edad que presente dificultad al respirar, con antecedente de fiebre mayor o igual a 38° C y tos, con uno o más de los siguientes síntomas: ataque al estado general, dolor torácico o polipnea. En pacientes inmunocomprometidos o con manejo terapéutico con antipiréticos no se presentará el pico febril descrito en la definición operacional; Así mismo en pacientes con apoyo respiratorio automatizado no se requerirá la tos como signo indispensable para su ingreso como sospechoso a influenza.'))),
    ('DENGUE_DEMO', 'vigente', 'pp. 60-61', jsonb_build_array(
        jsonb_build_object('clasificacion', 'Dengue no grave (A97.0 y A97.9)', 'texto',
            'Toda persona de cualquier edad que resida o que proceda, en los 14 días previos al inicio de signos y síntomas, de una región donde exista transmisión de la enfermedad y que presente fiebre y dos o más de los siguientes signos y síntomas: Náusea, vómitos, exantema; Mialgias, artralgia; Cefalea, dolor retro-ocular; Petequias o prueba del torniquete positiva; Leucopenia. En menores de 5 años, el único signo a considerar puede ser la fiebre.'),
        jsonb_build_object('clasificacion', 'Dengue con signos de alarma (A97.1)', 'texto',
            'Todo caso probable que además de cumplir con cuadro de Dengue No Grave, presente uno o más de los siguientes signos de alarma: Dolor abdominal intenso y continuo, o dolor a la palpación del abdomen; Vómito persistente o incoercible; Acumulación de líquidos (ascitis, derrame pleural, pericárdico); Sangrado de mucosas; Letargo o irritabilidad; Hipotensión postural (lipotimia); Hepatomegalia mayor de 2 cm; Aumento progresivo del hematocrito; Disminución progresiva de plaquetas; Disminución progresiva de la hemoglobina.'),
        jsonb_build_object('clasificacion', 'Dengue grave (A97.2)', 'texto',
            'Todo caso probable de Dengue que presenta uno o más de los siguientes hallazgos: Choque debido a extravasación grave de plasma evidenciado por: taquicardia, extremidades frías y llenado capilar igual o mayor a tres segundos, pulso débil o indetectable, presión diferencial convergente ≤ 20 mm hipotensión arterial en fase tardía, acumulación de líquidos que conlleve a insuficiencia respiratoria; Sangrado grave, según la evaluación del médico tratante (ejemplos: hematemesis, melena, metrorragia voluminosa, sangrado del sistema nervioso central); Compromiso grave de órganos tales como: daño hepático importante (AST o ALT>1000), afección renal, sistema nervioso central (alteración de la conciencia), corazón (miocarditis) u otros órganos.'))),
    ('MALARIA_DEMO', 'vigente', 'p. 62', jsonb_build_array(
        jsonb_build_object('clasificacion', 'Paludismo por Plasmodium falciparum (B50)', 'texto',
            'Toda persona que resida o provenga de área con antecedente de transmisión de paludismo (en los últimos tres años) y que en el último mes presente o haya presentado fiebre más los siguientes signos y síntomas: cefalea, diaforesis y escalofríos.'),
        jsonb_build_object('clasificacion', 'Paludismo por Plasmodium vivax (B51)', 'texto',
            'La enfermedad puede comenzar con malestar indefinido y fiebre, que aumenta poco a poco en un lapso de varios días, seguido por escalofríos fuertes y aumento rápido de la temperatura, que por lo regular se acompaña de cefalalgia y náusea y culmina en sudores profusos. Después de un lapso sin fiebre se repite el ciclo de escalofríos, fiebre y sudores todos los días, en días alternos o cada tercer día.'))),
    ('ZIKA_DEMO', 'vigente', 'pp. 66-67', jsonb_build_array(
        jsonb_build_object('clasificacion', 'Infección por virus Zika (U06.9)', 'texto',
            'Paciente que presente exantema y al menos dos o más de los siguientes signos o síntomas: Fiebre; Cefalea; Conjuntivitis (no purulenta/hiperemia); Artralgias; Mialgias; Edema periarticular; Prurito; Dolor retroocular. Y que se identifique alguna asociación epidemiológica: Presencia del vector Aedes aegypti o Aedes albopictus, o; Antecedente de visita o residencia en áreas de transmisión en las dos semanas previas al inicio del cuadro clínico, o; Existencia de casos confirmados en la localidad; Tenga antecedente de contacto sexual sin protección en las 2 semanas previas a la aparición de los síntomas, con una persona que en las 8 semanas previas al contacto sexual tenga antecedente de residencia o viaje a un área con transmisión local del VZIK o con presencia de vectores.')))
) AS v(code, status, paginas, criterios)
JOIN diseases d ON d.code = v.code
ON CONFLICT (disease_id, version) DO NOTHING;

-- Versión 1: los parámetros de hoy.
INSERT INTO disease_parameter_versions (disease_id, version, params, reason)
SELECT id, 1, default_params, 'Parámetros vigentes al crear el historial de versiones (042).'
FROM diseases
ON CONFLICT (disease_id, version) DO NOTHING;

-- Los intervalos que ya traían las fuentes citadas en cada parámetro. Solo si el
-- valor sigue siendo el de esa fuente y el parámetro aún no tiene intervalo. Un
-- UPDATE por parámetro: con UPDATE ... FROM, una enfermedad con varias filas solo
-- recibiría una.
UPDATE diseases SET default_params = jsonb_set(default_params, '{r0,intervalo}', '{"min": 2.39, "max": 3.44, "tipo": "IC95"}')
 WHERE code = 'SARS_COV_2_ANCESTRAL' AND jsonb_typeof(default_params -> 'r0') = 'object'
   AND (default_params -> 'r0' ->> 'valor')::numeric = 2.87 AND NOT (default_params -> 'r0' ? 'intervalo');
UPDATE diseases SET default_params = jsonb_set(default_params, '{letalidad,intervalo}', '{"min": 0.003, "max": 0.009, "tipo": "IC95"}')
 WHERE code = 'SARS_COV_2_ANCESTRAL' AND jsonb_typeof(default_params -> 'letalidad') = 'object'
   AND (default_params -> 'letalidad' ->> 'valor')::numeric = 0.005 AND NOT (default_params -> 'letalidad' ? 'intervalo');
UPDATE diseases SET default_params = jsonb_set(default_params, '{incubacion_dias,intervalo}', '{"min": 4.5, "max": 5.8, "tipo": "IC95"}')
 WHERE code = 'SARS_COV_2_ANCESTRAL' AND jsonb_typeof(default_params -> 'incubacion_dias') = 'object'
   AND (default_params -> 'incubacion_dias' ->> 'valor')::numeric = 5.1 AND NOT (default_params -> 'incubacion_dias' ? 'intervalo');
UPDATE diseases SET default_params = jsonb_set(default_params, '{dias_hospitalizacion,intervalo}', '{"min": 4, "max": 21, "tipo": "rango"}')
 WHERE code = 'SARS_COV_2_ANCESTRAL' AND jsonb_typeof(default_params -> 'dias_hospitalizacion') = 'object'
   AND (default_params -> 'dias_hospitalizacion' ->> 'valor')::numeric = 8.0 AND NOT (default_params -> 'dias_hospitalizacion' ? 'intervalo');
UPDATE diseases SET default_params = jsonb_set(default_params, '{r0,intervalo}', '{"min": 1.19, "max": 1.37, "tipo": "RIC"}')
 WHERE code = 'INFLUENZA_ESTACIONAL' AND jsonb_typeof(default_params -> 'r0') = 'object'
   AND (default_params -> 'r0' ->> 'valor')::numeric = 1.28 AND NOT (default_params -> 'r0' ? 'intervalo');
UPDATE diseases SET default_params = jsonb_set(default_params, '{infeccioso_dias,intervalo}', '{"min": 4.31, "max": 5.29, "tipo": "IC95"}')
 WHERE code = 'INFLUENZA_ESTACIONAL' AND jsonb_typeof(default_params -> 'infeccioso_dias') = 'object'
   AND (default_params -> 'infeccioso_dias' ->> 'valor')::numeric = 4.8 AND NOT (default_params -> 'infeccioso_dias' ? 'intervalo');

-- Versión 2 donde los intervalos cambiaron algo.
INSERT INTO disease_parameter_versions (disease_id, version, params, reason)
SELECT d.id, 2, d.default_params,
       'Intervalos de incertidumbre tomados de las fuentes que ya citaba cada parámetro (D58).'
FROM diseases d
JOIN disease_parameter_versions v ON v.disease_id = d.id AND v.version = 1
WHERE d.default_params IS DISTINCT FROM v.params
ON CONFLICT (disease_id, version) DO NOTHING;

INSERT INTO intervention_effectiveness
    (intervention_type_id, parameter, disease_id, reference_value, range_min, range_max, source, is_assumption)
SELECT t.id, v.parametro, d.id, v.valor, v.minimo, v.maximo, v.fuente, v.supuesto
FROM (VALUES
    ('CUBREBOCAS', 'eficacia', NULL, 0.85, 0.66, 0.93, true,
     'DERIVADO POR EL EQUIPO de Chu et al. 2020, Lancet 395(10242):1973-1987: el uso de cubrebocas se asoció con menos infecciones (aOR 0.15, IC95% 0.07-0.34; certeza baja), sobre todo en entornos de atención médica y con respiradores N95. La eficacia se toma como 1 - aOR; con cubrebocas de tela o quirúrgicos en la comunidad el efecto esperado es menor. doi:10.1016/S0140-6736(20)31142-9'),
    ('VACUNACION', 'eficacia', 'SARS_COV_2_ANCESTRAL', 0.95, 0.903, 0.976, false,
     'Polack et al. 2020, N Engl J Med 383(27):2603-2615: la vacuna BNT162b2 tuvo 95% de eficacia contra COVID-19 desde 7 días después de la segunda dosis (intervalo creíble 95%: 90.3-97.6). El motor la aplica como protección completa de una fracción de los vacunados. doi:10.1056/NEJMoa2034577'),
    ('VACUNACION', 'eficacia', 'INFLUENZA_ESTACIONAL', 0.59, 0.51, 0.67, false,
     'Osterholm et al. 2012, Lancet Infect Dis 12(1):36-44: eficacia agrupada de la vacuna trivalente inactivada en adultos, 59% (IC95% 51-67), contra influenza confirmada por RT-PCR o cultivo. El motor la aplica como protección completa de una fracción de los vacunados. doi:10.1016/S1473-3099(11)70295-X'),
    ('TESTEO_AISLAMIENTO', 'deteccion', 'SARS_COV_2_ANCESTRAL', 0.14, 0.10, 0.18, true,
     'DERIVADO POR EL EQUIPO de Li et al. 2020, Science 368(6490):489-493: entre el 10 y el 23 de enero de 2020 se reportó solo el 14% (IC95% 10-18%) de las infecciones en China. Se toma como la fracción de infecciosos que detecta un sistema de pruebas al inicio de una epidemia; con más pruebas es mayor. doi:10.1126/science.abb3221'),
    ('CIERRE_TRABAJO', 'reduccion', NULL, 0.51, 0.30, 0.72, true,
     'DERIVADO POR EL EQUIPO de los Informes de Movilidad Comunitaria COVID-19 de Google (archivo 2020_MX_Region_Mobility_Report.csv, Nuevo León, consultado el 2026-11-23): en los días hábiles de abril de 2020 las visitas a lugares de trabajo bajaron en promedio 50.6% respecto a la línea base de enero y febrero (de 41% a 72% según el día); de junio a diciembre, entre 30% y 38%. Se supone que los contactos en el trabajo bajan en la misma proporción que las visitas. https://www.google.com/covid19/mobility/'),
    ('REDUCCION_AFORO', 'reduccion', NULL, 0.30, 0.18, 0.54, true,
     'DERIVADO POR EL EQUIPO de los Informes de Movilidad Comunitaria COVID-19 de Google (archivo 2020_MX_Region_Mobility_Report.csv, Nuevo León, consultado el 2026-11-23): de agosto a octubre de 2020 las visitas a comercios y lugares de recreación bajaron entre 30% y 31% (promedio de días hábiles) respecto a la línea base de enero y febrero; en abril, 54%, y en diciembre, 18%. Se supone que los contactos en la comunidad bajan en la misma proporción que las visitas. https://www.google.com/covid19/mobility/'),
    ('CIERRE_ESCUELAS', 'reduccion', NULL, 1.0, NULL, NULL, true,
     'SUPUESTO DEL EQUIPO: un cierre total quita todos los contactos de la capa escuela, así que la reducción vale 1 por definición (es el valor por omisión de su param_schema). Un cierre parcial, con turnos alternados o aforo reducido, se captura con un valor menor. Ningún estudio lo mide de forma directa.')
) AS v(tipo, parametro, enfermedad, valor, minimo, maximo, supuesto, fuente)
JOIN intervention_types t ON t.code = v.tipo
LEFT JOIN diseases d ON d.code = v.enfermedad
WHERE v.enfermedad IS NULL OR d.id IS NOT NULL
ON CONFLICT (intervention_type_id, parameter, disease_id) DO NOTHING;
-- </datos-por-enfermedad>

-- -----------------------------------------------------------------------------
-- Permisos
-- -----------------------------------------------------------------------------
GRANT SELECT, INSERT ON case_definitions TO svc_enfermedades;
GRANT UPDATE (status, criteria, source, source_url, published_by, published_at, retired_at)
    ON case_definitions TO svc_enfermedades;
GRANT USAGE ON SEQUENCE case_definitions_id_seq TO svc_enfermedades;
GRANT UPDATE (transmission, icd10, classification_source) ON diseases TO svc_enfermedades;

GRANT SELECT, INSERT ON disease_parameter_versions TO svc_parametros;
GRANT USAGE ON SEQUENCE disease_parameter_versions_id_seq TO svc_parametros;

GRANT SELECT, INSERT, UPDATE ON intervention_effectiveness TO svc_tipos_intervencion;
GRANT USAGE ON SEQUENCE intervention_effectiveness_id_seq TO svc_tipos_intervencion;
GRANT SELECT (id, code, name) ON diseases TO svc_tipos_intervencion;
GRANT INSERT ON audit_log TO svc_tipos_intervencion;

INSERT INTO schema_migrations (version, description)
VALUES ('042', 'Definiciones de caso, clasificación, versiones e intervalos de parámetros y supuestos de efectividad (D58)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
