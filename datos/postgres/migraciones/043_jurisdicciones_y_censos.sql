SET client_encoding = 'UTF8';
-- =============================================================================
-- 043_jurisdicciones_y_censos.sql
-- Generado por datos/scripts/build_censos_y_jurisdicciones.py: no editar a mano.
--
-- Dominio: catálogos. Jurisdicciones sanitarias, periodos de referencia y
-- versiones de la población (D56, D7 del checklist).
--
-- - health_areas y health_area_municipalities: las 8 jurisdicciones sanitarias de
--   Nuevo León y sus municipios (Reglamento Interior de Servicios de Salud de NL,
--   art. 27; datos/geo/nl_jurisdicciones_sanitarias.json). Monterrey se reparte
--   entre la 1, la 2 y la 3: va en las tres, marcado como parcial.
-- - census_population: la población total de Nuevo León y de cada municipio en
--   los censos y conteos de INEGI de 1990 a 2020 (7 años, 364 filas).
-- - population_versions: cada ajuste de la población de una región (total, 60 y
--   más y bandas de edad) es una versión, con su periodo de referencia, su fuente
--   y su motivo. Las escribe poblacion en la misma transacción que el ajuste.
-- - Los municipios se ligan por su clave INEGI (regions.code) y no por
--   regions.id: en una instalación limpia el dump corre antes que la semilla de
--   los 41 municipios que no trae la 010. Una prueba revisa que cada clave exista.
-- - Idempotente (D7).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS health_areas (
    id          SMALLSERIAL   PRIMARY KEY,
    state_code  VARCHAR(2)    NOT NULL,
    number      SMALLINT      NOT NULL,
    name        VARCHAR(160)  NOT NULL,
    description TEXT          NOT NULL,
    source      TEXT          NOT NULL,
    source_url  TEXT,

    CONSTRAINT uq_health_areas_numero UNIQUE (state_code, number),
    CONSTRAINT ck_health_areas_numero CHECK (number >= 1)
);

COMMENT ON TABLE health_areas IS
    'Jurisdicciones sanitarias (áreas sanitarias) de cada estado, con su fuente (D56). Solo lectura: las carga esta migración.';
COMMENT ON COLUMN health_areas.id IS 'Identificador.';
COMMENT ON COLUMN health_areas.state_code IS 'Clave INEGI del estado (19, Nuevo León).';
COMMENT ON COLUMN health_areas.number IS 'Número de la jurisdicción dentro del estado.';
COMMENT ON COLUMN health_areas.name IS 'Nombre oficial.';
COMMENT ON COLUMN health_areas.description IS 'Circunscripción tal como la escribe la fuente.';
COMMENT ON COLUMN health_areas.source IS 'Documento de donde sale la división.';
COMMENT ON COLUMN health_areas.source_url IS 'Dirección del documento.';

CREATE TABLE IF NOT EXISTS health_area_municipalities (
    health_area_id SMALLINT     NOT NULL,
    region_code    VARCHAR(20)  NOT NULL,
    partial        BOOLEAN      NOT NULL DEFAULT false,

    CONSTRAINT pk_health_area_municipalities PRIMARY KEY (health_area_id, region_code),
    CONSTRAINT fk_health_area_municipalities_area
        FOREIGN KEY (health_area_id) REFERENCES health_areas (id) ON DELETE CASCADE,
    CONSTRAINT ck_health_area_municipalities_clave CHECK (region_code ~ '^[0-9]{5}$')
);

CREATE INDEX IF NOT EXISTS ix_health_area_municipalities_region
    ON health_area_municipalities (region_code);

COMMENT ON TABLE health_area_municipalities IS
    'Municipios de cada jurisdicción sanitaria (D56). Un municipio repartido entre varias, como Monterrey, aparece en cada una con partial = true.';
COMMENT ON COLUMN health_area_municipalities.health_area_id IS 'Jurisdicción. Referencia a health_areas.id. [llave foranea]';
COMMENT ON COLUMN health_area_municipalities.region_code IS 'Clave INEGI del municipio (regions.code). Sin llave foránea: ver el encabezado de la 043.';
COMMENT ON COLUMN health_area_municipalities.partial IS 'true si solo una parte del municipio pertenece a la jurisdicción.';

CREATE TABLE IF NOT EXISTS census_population (
    region_code VARCHAR(20) NOT NULL,
    year        SMALLINT    NOT NULL,
    population  INTEGER     NOT NULL,
    source      TEXT        NOT NULL,

    CONSTRAINT pk_census_population PRIMARY KEY (region_code, year),
    CONSTRAINT ck_census_population_clave CHECK (region_code ~ '^[0-9]{2}([0-9]{3})?$'),
    CONSTRAINT ck_census_population_anio CHECK (year BETWEEN 1900 AND 2100),
    CONSTRAINT ck_census_population_poblacion CHECK (population > 0)
);

COMMENT ON TABLE census_population IS
    'Periodos de referencia de la población: el total de cada región en los censos y conteos de INEGI (D56). Solo lectura: lo carga esta migración.';
COMMENT ON COLUMN census_population.region_code IS 'Clave INEGI del estado o del municipio (regions.code). Sin llave foránea: ver el encabezado de la 043.';
COMMENT ON COLUMN census_population.year IS 'Año del censo o conteo.';
COMMENT ON COLUMN census_population.population IS 'Población total.';
COMMENT ON COLUMN census_population.source IS 'Tabulado de INEGI de donde sale.';

CREATE TABLE IF NOT EXISTS population_versions (
    id                BIGSERIAL    PRIMARY KEY,
    region_id         INTEGER      NOT NULL,
    version           INTEGER      NOT NULL,
    population        INTEGER      NOT NULL,
    population_60plus INTEGER,
    age_groups        JSONB,
    reference_year    SMALLINT     NOT NULL,
    source            TEXT         NOT NULL,
    reason            TEXT,
    created_by        BIGINT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_population_versions_region
        FOREIGN KEY (region_id)  REFERENCES regions (id) ON DELETE CASCADE,
    CONSTRAINT fk_population_versions_user
        FOREIGN KEY (created_by) REFERENCES users (id)   ON DELETE SET NULL,
    CONSTRAINT uq_population_versions UNIQUE (region_id, version),
    CONSTRAINT ck_population_versions_version CHECK (version >= 1),
    CONSTRAINT ck_population_versions_poblacion CHECK (
        population > 0 AND (population_60plus IS NULL OR population_60plus BETWEEN 0 AND population)),
    CONSTRAINT ck_population_versions_grupos CHECK (age_groups IS NULL OR jsonb_typeof(age_groups) = 'object')
);

COMMENT ON TABLE population_versions IS
    'Versiones de la población de cada región (D56). La 1 es la que había antes del primer ajuste (el Censo 2020); cada ajuste agrega la siguiente con el resultado. Las escribe poblacion; no se editan ni se borran (D52).';
COMMENT ON COLUMN population_versions.id IS 'Identificador.';
COMMENT ON COLUMN population_versions.region_id IS 'Región. Referencia a regions.id. [llave foranea]';
COMMENT ON COLUMN population_versions.version IS 'Número de versión dentro de la región, desde 1.';
COMMENT ON COLUMN population_versions.population IS 'Población total en esa versión.';
COMMENT ON COLUMN population_versions.population_60plus IS 'Población de 60 y más en esa versión.';
COMMENT ON COLUMN population_versions.age_groups IS 'Bandas de edad en esa versión: {grupo: personas}, con edad_no_especificada.';
COMMENT ON COLUMN population_versions.reference_year IS 'Año al que se refieren las cifras (periodo de referencia).';
COMMENT ON COLUMN population_versions.source IS 'De dónde salen: el censo, o el ajuste que las cambió.';
COMMENT ON COLUMN population_versions.reason IS 'Motivo del ajuste; NULL en la versión 1.';
COMMENT ON COLUMN population_versions.created_by IS 'Quien hizo el ajuste. Referencia a users.id. [llave foranea]';
COMMENT ON COLUMN population_versions.created_at IS 'Cuándo se guardó la versión.';

INSERT INTO health_areas (state_code, number, name, description, source, source_url) VALUES
    ('19', 1, 'Jurisdicción Sanitaria No. 1', 'Poniente del municipio de Monterrey', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 2, 'Jurisdicción Sanitaria No. 2', 'Norte y oriente del municipio de Monterrey y los municipios de Abasolo, el Carmen, Ciénega de Flores, General Mariano Escobedo, General Zuazua, Mina, Salinas Victoria, San Nicolás de los Garza e Hidalgo', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 3, 'Jurisdicción Sanitaria No. 3', 'Sur de Monterrey y los municipios de Villa de García, San Pedro Garza García y Santa Catarina', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 4, 'Jurisdicción Sanitaria No. 4', 'Municipios de Apodaca, Guadalupe y Benito Juárez', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 5, 'Jurisdicción Sanitaria No. 5', 'Municipios de Agualeguas, Anáhuac, Bustamante, General Treviño, Lampazos, Parás, Sabinas Hidalgo, Vallecillo y Villaldama', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 6, 'Jurisdicción Sanitaria No. 6', 'Municipios de Los Aldama, Cadereyta Jiménez, Cerralvo, China, Dr. Coss, Dr. González, General Bravo, Los Herrera, Higueras, Marín, Melchor Ocampo, Pesquería y Los Ramones', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 7, 'Jurisdicción Sanitaria No. 7', 'Municipios de Allende, General Terán, Hualahuises, Linares, Montemorelos, Los Rayones y Santiago', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf'),
    ('19', 8, 'Jurisdicción Sanitaria No. 8', 'Municipios de Aramberri, Dr. Arroyo, Galeana, General Zaragoza, Mier y Noriega e Iturbide', 'Reglamento Interior de "Servicios de Salud de Nuevo León" Organismo Público Descentralizado, artículo 27. Periódico Oficial del Estado núm. 130, 12 de octubre de 2004; última reforma P.O. 4 de marzo de 2009. Pendiente de confirmar con la Secretaría de Salud de Nuevo León que siga vigente. Monterrey se reparte entre las jurisdicciones 1, 2 y 3; con casos por municipio no se puede partir y va en compartidos.', 'http://www.ordenjuridico.gob.mx/Documentos/Estatal/Nuevo%20Leon/wo119338.pdf')
ON CONFLICT (state_code, number) DO NOTHING;

INSERT INTO health_area_municipalities (health_area_id, region_code, partial)
SELECT a.id, v.clave, v.parcial
FROM (VALUES
    (1, '19039', true),
    (2, '19001', false),
    (2, '19010', false),
    (2, '19012', false),
    (2, '19021', false),
    (2, '19025', false),
    (2, '19037', false),
    (2, '19039', true),
    (2, '19045', false),
    (2, '19046', false),
    (2, '19047', false),
    (3, '19018', false),
    (3, '19019', false),
    (3, '19039', true),
    (3, '19048', false),
    (4, '19006', false),
    (4, '19026', false),
    (4, '19031', false),
    (5, '19002', false),
    (5, '19005', false),
    (5, '19008', false),
    (5, '19023', false),
    (5, '19032', false),
    (5, '19040', false),
    (5, '19044', false),
    (5, '19050', false),
    (5, '19051', false),
    (6, '19003', false),
    (6, '19009', false),
    (6, '19011', false),
    (6, '19013', false),
    (6, '19015', false),
    (6, '19016', false),
    (6, '19020', false),
    (6, '19027', false),
    (6, '19028', false),
    (6, '19034', false),
    (6, '19035', false),
    (6, '19041', false),
    (6, '19042', false),
    (7, '19004', false),
    (7, '19022', false),
    (7, '19029', false),
    (7, '19033', false),
    (7, '19038', false),
    (7, '19043', false),
    (7, '19049', false),
    (8, '19007', false),
    (8, '19014', false),
    (8, '19017', false),
    (8, '19024', false),
    (8, '19030', false),
    (8, '19036', false)
) AS v(numero, clave, parcial)
JOIN health_areas a ON a.state_code = '19' AND a.number = v.numero
ON CONFLICT (health_area_id, region_code) DO NOTHING;

INSERT INTO census_population (region_code, year, population, source)
SELECT v.clave, v.anio, v.poblacion, 'INEGI. Censos y Conteos de Población y Vivienda, 1990-2020: tabulado «Población total por municipio, serie de años censales de 1990 a 2020» (consultado el 24/09/2026). El dato 2020 de Santiago, Vallecillo y Villaldama sale de los Principales resultados por localidad.'
FROM (VALUES
    ('19', 1990, 3098736),
    ('19001', 1990, 1373),
    ('19002', 1990, 5095),
    ('19003', 1990, 4140),
    ('19004', 1990, 22211),
    ('19005', 1990, 17316),
    ('19006', 1990, 115913),
    ('19007', 1990, 15295),
    ('19008', 1990, 2976),
    ('19009', 1990, 53582),
    ('19010', 1990, 4906),
    ('19011', 1990, 7653),
    ('19012', 1990, 6708),
    ('19013', 1990, 12404),
    ('19014', 1990, 36946),
    ('19015', 1990, 2961),
    ('19016', 1990, 3011),
    ('19017', 1990, 40972),
    ('19018', 1990, 13164),
    ('19019', 1990, 113040),
    ('19020', 1990, 6759),
    ('19021', 1990, 98147),
    ('19022', 1990, 16656),
    ('19023', 1990, 2182),
    ('19024', 1990, 5532),
    ('19025', 1990, 4647),
    ('19026', 1990, 535560),
    ('19027', 1990, 3363),
    ('19028', 1990, 1060),
    ('19029', 1990, 6222),
    ('19030', 1990, 3638),
    ('19031', 1990, 28014),
    ('19032', 1990, 5288),
    ('19033', 1990, 61569),
    ('19034', 1990, 3292),
    ('19035', 1990, 1641),
    ('19036', 1990, 7240),
    ('19037', 1990, 4564),
    ('19038', 1990, 49302),
    ('19039', 1990, 1069238),
    ('19040', 1990, 1021),
    ('19041', 1990, 8188),
    ('19042', 1990, 6538),
    ('19043', 1990, 3164),
    ('19044', 1990, 27550),
    ('19045', 1990, 9518),
    ('19046', 1990, 436603),
    ('19047', 1990, 11668),
    ('19048', 1990, 163848),
    ('19049', 1990, 30182),
    ('19050', 1990, 2723),
    ('19051', 1990, 4153),
    ('19', 1995, 3550114),
    ('19001', 1995, 1945),
    ('19002', 1995, 4492),
    ('19003', 1995, 2445),
    ('19004', 1995, 23053),
    ('19005', 1995, 18278),
    ('19006', 1995, 219153),
    ('19007', 1995, 15691),
    ('19008', 1995, 3308),
    ('19009', 1995, 62440),
    ('19010', 1995, 6168),
    ('19011', 1995, 8287),
    ('19012', 1995, 8586),
    ('19013', 1995, 12064),
    ('19014', 1995, 37363),
    ('19015', 1995, 2286),
    ('19016', 1995, 2912),
    ('19017', 1995, 42145),
    ('19018', 1995, 23981),
    ('19019', 1995, 120913),
    ('19020', 1995, 6030),
    ('19021', 1995, 176869),
    ('19022', 1995, 16609),
    ('19023', 1995, 1695),
    ('19024', 1995, 5874),
    ('19025', 1995, 5276),
    ('19026', 1995, 618933),
    ('19027', 1995, 2860),
    ('19028', 1995, 1218),
    ('19029', 1995, 6535),
    ('19030', 1995, 3522),
    ('19031', 1995, 50009),
    ('19032', 1995, 5294),
    ('19033', 1995, 66104),
    ('19034', 1995, 4014),
    ('19035', 1995, 1121),
    ('19036', 1995, 7721),
    ('19037', 1995, 4783),
    ('19038', 1995, 51714),
    ('19039', 1995, 1088143),
    ('19040', 1995, 1087),
    ('19041', 1995, 9359),
    ('19042', 1995, 5236),
    ('19043', 1995, 2791),
    ('19044', 1995, 31521),
    ('19045', 1995, 15925),
    ('19046', 1995, 487924),
    ('19047', 1995, 13552),
    ('19048', 1995, 202156),
    ('19049', 1995, 34187),
    ('19050', 1995, 2188),
    ('19051', 1995, 4354),
    ('19', 2000, 3834141),
    ('19001', 2000, 2514),
    ('19002', 2000, 4390),
    ('19003', 2000, 2464),
    ('19004', 2000, 27773),
    ('19005', 2000, 18524),
    ('19006', 2000, 283497),
    ('19007', 2000, 14840),
    ('19008', 2000, 3499),
    ('19009', 2000, 75059),
    ('19010', 2000, 6644),
    ('19011', 2000, 9343),
    ('19012', 2000, 11204),
    ('19013', 2000, 11540),
    ('19014', 2000, 33721),
    ('19015', 2000, 2246),
    ('19016', 2000, 3185),
    ('19017', 2000, 39519),
    ('19018', 2000, 28974),
    ('19019', 2000, 125978),
    ('19020', 2000, 5799),
    ('19021', 2000, 233457),
    ('19022', 2000, 15475),
    ('19023', 2000, 1699),
    ('19024', 2000, 5576),
    ('19025', 2000, 6033),
    ('19026', 2000, 670162),
    ('19027', 2000, 2795),
    ('19028', 2000, 1371),
    ('19029', 2000, 6413),
    ('19030', 2000, 3484),
    ('19031', 2000, 66497),
    ('19032', 2000, 5305),
    ('19033', 2000, 69205),
    ('19034', 2000, 4719),
    ('19035', 2000, 1215),
    ('19036', 2000, 7078),
    ('19037', 2000, 5049),
    ('19038', 2000, 52741),
    ('19039', 2000, 1110997),
    ('19040', 2000, 1226),
    ('19041', 2000, 11321),
    ('19042', 2000, 6237),
    ('19043', 2000, 2613),
    ('19044', 2000, 32329),
    ('19045', 2000, 19024),
    ('19046', 2000, 496878),
    ('19047', 2000, 14275),
    ('19048', 2000, 227026),
    ('19049', 2000, 36812),
    ('19050', 2000, 2169),
    ('19051', 2000, 4247),
    ('19', 2005, 4199292),
    ('19001', 2005, 2746),
    ('19002', 2005, 3537),
    ('19003', 2005, 1675),
    ('19004', 2005, 29568),
    ('19005', 2005, 17983),
    ('19006', 2005, 418784),
    ('19007', 2005, 14692),
    ('19008', 2005, 3326),
    ('19009', 2005, 73746),
    ('19010', 2005, 6996),
    ('19011', 2005, 8009),
    ('19012', 2005, 14268),
    ('19013', 2005, 10697),
    ('19014', 2005, 33269),
    ('19015', 2005, 1639),
    ('19016', 2005, 3092),
    ('19017', 2005, 38930),
    ('19018', 2005, 51658),
    ('19019', 2005, 122009),
    ('19020', 2005, 5385),
    ('19021', 2005, 299364),
    ('19022', 2005, 14022),
    ('19023', 2005, 1476),
    ('19024', 2005, 5733),
    ('19025', 2005, 6985),
    ('19026', 2005, 691931),
    ('19027', 2005, 1877),
    ('19028', 2005, 1427),
    ('19029', 2005, 6631),
    ('19030', 2005, 3533),
    ('19031', 2005, 144380),
    ('19032', 2005, 4428),
    ('19033', 2005, 71061),
    ('19034', 2005, 5398),
    ('19035', 2005, 1052),
    ('19036', 2005, 7047),
    ('19037', 2005, 5384),
    ('19038', 2005, 53854),
    ('19039', 2005, 1133814),
    ('19040', 2005, 950),
    ('19041', 2005, 12258),
    ('19042', 2005, 6227),
    ('19043', 2005, 2576),
    ('19044', 2005, 32040),
    ('19045', 2005, 27848),
    ('19046', 2005, 476761),
    ('19047', 2005, 15480),
    ('19048', 2005, 259896),
    ('19049', 2005, 37886),
    ('19050', 2005, 1859),
    ('19051', 2005, 4105),
    ('19', 2010, 4653458),
    ('19001', 2010, 2791),
    ('19002', 2010, 3443),
    ('19003', 2010, 1374),
    ('19004', 2010, 32593),
    ('19005', 2010, 18480),
    ('19006', 2010, 523370),
    ('19007', 2010, 15470),
    ('19008', 2010, 3773),
    ('19009', 2010, 86445),
    ('19010', 2010, 16092),
    ('19011', 2010, 7855),
    ('19012', 2010, 24526),
    ('19013', 2010, 10864),
    ('19014', 2010, 35445),
    ('19015', 2010, 1716),
    ('19016', 2010, 3345),
    ('19017', 2010, 39991),
    ('19018', 2010, 143668),
    ('19019', 2010, 122659),
    ('19020', 2010, 5527),
    ('19021', 2010, 357937),
    ('19022', 2010, 14437),
    ('19023', 2010, 1277),
    ('19024', 2010, 5942),
    ('19025', 2010, 55213),
    ('19026', 2010, 678006),
    ('19027', 2010, 2030),
    ('19028', 2010, 1594),
    ('19029', 2010, 6914),
    ('19030', 2010, 3558),
    ('19031', 2010, 256970),
    ('19032', 2010, 5349),
    ('19033', 2010, 78669),
    ('19034', 2010, 5488),
    ('19035', 2010, 862),
    ('19036', 2010, 7095),
    ('19037', 2010, 5447),
    ('19038', 2010, 59113),
    ('19039', 2010, 1135550),
    ('19040', 2010, 1034),
    ('19041', 2010, 20843),
    ('19042', 2010, 5359),
    ('19043', 2010, 2628),
    ('19044', 2010, 34671),
    ('19045', 2010, 32660),
    ('19046', 2010, 443273),
    ('19047', 2010, 16604),
    ('19048', 2010, 268955),
    ('19049', 2010, 40469),
    ('19050', 2010, 1971),
    ('19051', 2010, 4113),
    ('19', 2015, 5119504),
    ('19001', 2015, 2639),
    ('19002', 2015, 2439),
    ('19003', 2015, 1292),
    ('19004', 2015, 34353),
    ('19005', 2015, 18194),
    ('19006', 2015, 597207),
    ('19007', 2015, 16152),
    ('19008', 2015, 3977),
    ('19009', 2015, 95534),
    ('19010', 2015, 38306),
    ('19011', 2015, 7757),
    ('19012', 2015, 42715),
    ('19013', 2015, 10835),
    ('19014', 2015, 34110),
    ('19015', 2015, 1632),
    ('19016', 2015, 2861),
    ('19017', 2015, 41130),
    ('19018', 2015, 247370),
    ('19019', 2015, 123156),
    ('19020', 2015, 5479),
    ('19021', 2015, 425148),
    ('19022', 2015, 14795),
    ('19023', 2015, 1044),
    ('19024', 2015, 6011),
    ('19025', 2015, 67294),
    ('19026', 2015, 682880),
    ('19027', 2015, 1764),
    ('19028', 2015, 1511),
    ('19029', 2015, 6921),
    ('19030', 2015, 3571),
    ('19031', 2015, 333481),
    ('19032', 2015, 5238),
    ('19033', 2015, 79853),
    ('19034', 2015, 5630),
    ('19035', 2015, 955),
    ('19036', 2015, 6996),
    ('19037', 2015, 5326),
    ('19038', 2015, 60829),
    ('19039', 2015, 1109171),
    ('19040', 2015, 971),
    ('19041', 2015, 87168),
    ('19042', 2015, 4469),
    ('19043', 2015, 2640),
    ('19044', 2015, 35456),
    ('19045', 2015, 54192),
    ('19046', 2015, 430143),
    ('19047', 2015, 13836),
    ('19048', 2015, 296954),
    ('19049', 2015, 42407),
    ('19050', 2015, 1632),
    ('19051', 2015, 4080),
    ('19', 2020, 5784442),
    ('19001', 2020, 2974),
    ('19002', 2020, 3382),
    ('19003', 2020, 1407),
    ('19004', 2020, 35289),
    ('19005', 2020, 18030),
    ('19006', 2020, 656464),
    ('19007', 2020, 14992),
    ('19008', 2020, 3661),
    ('19009', 2020, 122337),
    ('19010', 2020, 104478),
    ('19011', 2020, 7340),
    ('19012', 2020, 68747),
    ('19013', 2020, 9930),
    ('19014', 2020, 36088),
    ('19015', 2020, 1360),
    ('19016', 2020, 3256),
    ('19017', 2020, 40903),
    ('19018', 2020, 397205),
    ('19019', 2020, 132169),
    ('19020', 2020, 5506),
    ('19021', 2020, 481213),
    ('19022', 2020, 14109),
    ('19023', 2020, 1808),
    ('19024', 2020, 6282),
    ('19025', 2020, 102149),
    ('19026', 2020, 643143),
    ('19027', 2020, 1959),
    ('19028', 2020, 1386),
    ('19029', 2020, 7026),
    ('19030', 2020, 3298),
    ('19031', 2020, 471523),
    ('19032', 2020, 5351),
    ('19033', 2020, 84666),
    ('19034', 2020, 5119),
    ('19035', 2020, 1483),
    ('19036', 2020, 7652),
    ('19037', 2020, 6048),
    ('19038', 2020, 67428),
    ('19039', 2020, 1142994),
    ('19040', 2020, 906),
    ('19041', 2020, 147624),
    ('19042', 2020, 5389),
    ('19043', 2020, 2377),
    ('19044', 2020, 34709),
    ('19045', 2020, 86766),
    ('19046', 2020, 412199),
    ('19047', 2020, 16086),
    ('19048', 2020, 306322),
    ('19049', 2020, 46784),
    ('19050', 2020, 1552),
    ('19051', 2020, 3573)
) AS v(clave, anio, poblacion)
ON CONFLICT (region_code, year) DO NOTHING;

GRANT SELECT ON health_areas, health_area_municipalities TO svc_regiones;
GRANT SELECT ON census_population TO svc_poblacion;
GRANT SELECT, INSERT ON population_versions TO svc_poblacion;
GRANT USAGE ON SEQUENCE population_versions_id_seq TO svc_poblacion;

INSERT INTO schema_migrations (version, description)
VALUES ('043', 'Jurisdicciones sanitarias, censos y conteos 1990-2020 y versiones de la población (D56)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
