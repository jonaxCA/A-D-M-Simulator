# La migración 043: jurisdicciones sanitarias, la serie de censos y conteos de población 1990-2020 y
# las versiones de la población de cada región (D58).
#
#   python datos/scripts/build_censos_y_jurisdicciones.py > datos/postgres/migraciones/043_jurisdicciones_y_censos.sql
#
# Las jurisdicciones salen de datos/geo/nl_jurisdicciones_sanitarias.json (build_jurisdicciones.py,
# el mismo que usa zonas) y los censos de datos/censo/nl_poblacion_municipios_1990_2020.tsv
# (INEGI). Las filas se ligan a la región por su clave INEGI y no por regions.id: en una
# instalación limpia el dump corre antes que la semilla de los 41 municipios que no trae la 010.
import json
import os
import sys

import build_regiones_sql as regiones

DATOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JURISDICCIONES = os.path.join(DATOS, "geo", "nl_jurisdicciones_sanitarias.json")
CATALOGO = os.path.join(DATOS, "geo", "nl_catalogo_oficial.json")
ESTADO = "19"
FUENTE_CENSO = ("INEGI. Censos y Conteos de Población y Vivienda, 1990-2020: tabulado «Población total por "
                "municipio, serie de años censales de 1990 a 2020» (consultado el 24/09/2026). El dato 2020 "
                "de Santiago, Vallecillo y Villaldama sale de los Principales resultados por localidad.")


def texto(valor):
    return "NULL" if valor is None else "'" + str(valor).replace("'", "''") + "'"


def censos():
    # {año: {clave INEGI: población}}, con el estado en ESTADO. Los municipios suman el estado.
    catalogo = json.load(open(CATALOGO, encoding="utf-8"))
    filas = regiones._filas_tsv(regiones.CENSO)
    por_nombre = {regiones.normaliza(v): k for k, v in catalogo.items()}
    claves = []
    for nombre in filas[0][2:]:
        clave = por_nombre.get(regiones.ALIAS.get(regiones.normaliza(nombre), regiones.normaliza(nombre)))
        if clave is None:
            raise SystemExit("'%s' no está en el catálogo oficial de INEGI" % nombre)
        claves.append(ESTADO + clave)
    if len(set(claves)) != len(catalogo):
        raise SystemExit("el tabulado trae %d municipios y el catálogo %d" % (len(set(claves)), len(catalogo)))
    salida = {}
    for fila in filas[1:]:
        anio, valores = int(fila[0]), [int(v.replace(",", "")) for v in fila[1:]]
        if sum(valores[1:]) != valores[0]:
            raise SystemExit("%d: los municipios no suman el total estatal" % anio)
        salida[anio] = dict(zip([ESTADO] + claves, valores))
    return salida


def jurisdicciones():
    datos = json.load(open(JURISDICCIONES, encoding="utf-8"))
    miembros = []
    for j in datos["jurisdicciones"]:
        miembros += [(j["numero"], clave, False) for clave in j["municipios"]]
    for clave, numeros in datos["compartidos"].items():
        miembros += [(numero, clave, True) for numero in numeros]
    return datos["fuente"], datos["jurisdicciones"], sorted(miembros)


def migracion():
    fuente, lista, miembros = jurisdicciones()
    serie = censos()
    cita = "%s. %s. %s" % (fuente["documento"], fuente["publicacion"], fuente["nota"])
    l = ["SET client_encoding = 'UTF8';",
         "-- =============================================================================",
         "-- 043_jurisdicciones_y_censos.sql",
         "-- Generado por datos/scripts/build_censos_y_jurisdicciones.py: no editar a mano.",
         "--",
         "-- Dominio: catálogos. Jurisdicciones sanitarias, periodos de referencia y",
         "-- versiones de la población (D58, D7 del checklist).",
         "--",
         "-- - health_areas y health_area_municipalities: las %d jurisdicciones sanitarias de" % len(lista),
         "--   Nuevo León y sus municipios (Reglamento Interior de Servicios de Salud de NL,",
         "--   art. 27; datos/geo/nl_jurisdicciones_sanitarias.json). Monterrey se reparte",
         "--   entre la 1, la 2 y la 3: va en las tres, marcado como parcial.",
         "-- - census_population: la población total de Nuevo León y de cada municipio en",
         "--   los censos y conteos de INEGI de %d a %d (%d años, %d filas)." % (
             min(serie), max(serie), len(serie), sum(len(v) for v in serie.values())),
         "-- - population_versions: cada ajuste de la población de una región (total, 60 y",
         "--   más y bandas de edad) es una versión, con su periodo de referencia, su fuente",
         "--   y su motivo. Las escribe poblacion en la misma transacción que el ajuste.",
         "-- - Los municipios se ligan por su clave INEGI (regions.code) y no por",
         "--   regions.id: en una instalación limpia el dump corre antes que la semilla de",
         "--   los 41 municipios que no trae la 010. Una prueba revisa que cada clave exista.",
         "-- - Idempotente (D7).",
         "-- =============================================================================",
         "",
         "BEGIN;",
         "",
         "CREATE TABLE IF NOT EXISTS health_areas (",
         "    id          SMALLSERIAL   PRIMARY KEY,",
         "    state_code  VARCHAR(2)    NOT NULL,",
         "    number      SMALLINT      NOT NULL,",
         "    name        VARCHAR(160)  NOT NULL,",
         "    description TEXT          NOT NULL,",
         "    source      TEXT          NOT NULL,",
         "    source_url  TEXT,",
         "",
         "    CONSTRAINT uq_health_areas_numero UNIQUE (state_code, number),",
         "    CONSTRAINT ck_health_areas_numero CHECK (number >= 1)",
         ");",
         "",
         "COMMENT ON TABLE health_areas IS",
         "    'Jurisdicciones sanitarias (áreas sanitarias) de cada estado, con su fuente (D58). Solo lectura: las carga esta migración.';",
         "COMMENT ON COLUMN health_areas.id IS 'Identificador.';",
         "COMMENT ON COLUMN health_areas.state_code IS 'Clave INEGI del estado (19, Nuevo León).';",
         "COMMENT ON COLUMN health_areas.number IS 'Número de la jurisdicción dentro del estado.';",
         "COMMENT ON COLUMN health_areas.name IS 'Nombre oficial.';",
         "COMMENT ON COLUMN health_areas.description IS 'Circunscripción tal como la escribe la fuente.';",
         "COMMENT ON COLUMN health_areas.source IS 'Documento de donde sale la división.';",
         "COMMENT ON COLUMN health_areas.source_url IS 'Dirección del documento.';",
         "",
         "CREATE TABLE IF NOT EXISTS health_area_municipalities (",
         "    health_area_id SMALLINT     NOT NULL,",
         "    region_code    VARCHAR(20)  NOT NULL,",
         "    partial        BOOLEAN      NOT NULL DEFAULT false,",
         "",
         "    CONSTRAINT pk_health_area_municipalities PRIMARY KEY (health_area_id, region_code),",
         "    CONSTRAINT fk_health_area_municipalities_area",
         "        FOREIGN KEY (health_area_id) REFERENCES health_areas (id) ON DELETE CASCADE,",
         "    CONSTRAINT ck_health_area_municipalities_clave CHECK (region_code ~ '^[0-9]{5}$')",
         ");",
         "",
         "CREATE INDEX IF NOT EXISTS ix_health_area_municipalities_region",
         "    ON health_area_municipalities (region_code);",
         "",
         "COMMENT ON TABLE health_area_municipalities IS",
         "    'Municipios de cada jurisdicción sanitaria (D58). Un municipio repartido entre varias, como Monterrey, aparece en cada una con partial = true.';",
         "COMMENT ON COLUMN health_area_municipalities.health_area_id IS 'Jurisdicción. Referencia a health_areas.id. [llave foranea]';",
         "COMMENT ON COLUMN health_area_municipalities.region_code IS 'Clave INEGI del municipio (regions.code). Sin llave foránea: ver el encabezado de la 043.';",
         "COMMENT ON COLUMN health_area_municipalities.partial IS 'true si solo una parte del municipio pertenece a la jurisdicción.';",
         "",
         "CREATE TABLE IF NOT EXISTS census_population (",
         "    region_code VARCHAR(20) NOT NULL,",
         "    year        SMALLINT    NOT NULL,",
         "    population  INTEGER     NOT NULL,",
         "    source      TEXT        NOT NULL,",
         "",
         "    CONSTRAINT pk_census_population PRIMARY KEY (region_code, year),",
         "    CONSTRAINT ck_census_population_clave CHECK (region_code ~ '^[0-9]{2}([0-9]{3})?$'),",
         "    CONSTRAINT ck_census_population_anio CHECK (year BETWEEN 1900 AND 2100),",
         "    CONSTRAINT ck_census_population_poblacion CHECK (population > 0)",
         ");",
         "",
         "COMMENT ON TABLE census_population IS",
         "    'Periodos de referencia de la población: el total de cada región en los censos y conteos de INEGI (D58). Solo lectura: lo carga esta migración.';",
         "COMMENT ON COLUMN census_population.region_code IS 'Clave INEGI del estado o del municipio (regions.code). Sin llave foránea: ver el encabezado de la 043.';",
         "COMMENT ON COLUMN census_population.year IS 'Año del censo o conteo.';",
         "COMMENT ON COLUMN census_population.population IS 'Población total.';",
         "COMMENT ON COLUMN census_population.source IS 'Tabulado de INEGI de donde sale.';",
         "",
         "CREATE TABLE IF NOT EXISTS population_versions (",
         "    id                BIGSERIAL    PRIMARY KEY,",
         "    region_id         INTEGER      NOT NULL,",
         "    version           INTEGER      NOT NULL,",
         "    population        INTEGER      NOT NULL,",
         "    population_60plus INTEGER,",
         "    age_groups        JSONB,",
         "    reference_year    SMALLINT     NOT NULL,",
         "    source            TEXT         NOT NULL,",
         "    reason            TEXT,",
         "    created_by        BIGINT,",
         "    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),",
         "",
         "    CONSTRAINT fk_population_versions_region",
         "        FOREIGN KEY (region_id)  REFERENCES regions (id) ON DELETE CASCADE,",
         "    CONSTRAINT fk_population_versions_user",
         "        FOREIGN KEY (created_by) REFERENCES users (id)   ON DELETE SET NULL,",
         "    CONSTRAINT uq_population_versions UNIQUE (region_id, version),",
         "    CONSTRAINT ck_population_versions_version CHECK (version >= 1),",
         "    CONSTRAINT ck_population_versions_poblacion CHECK (",
         "        population > 0 AND (population_60plus IS NULL OR population_60plus BETWEEN 0 AND population)),",
         "    CONSTRAINT ck_population_versions_grupos CHECK (age_groups IS NULL OR jsonb_typeof(age_groups) = 'object')",
         ");",
         "",
         "COMMENT ON TABLE population_versions IS",
         "    'Versiones de la población de cada región (D58). La 1 es la que había antes del primer ajuste (el Censo 2020); cada ajuste agrega la siguiente con el resultado. Las escribe poblacion; no se editan ni se borran (D52).';",
         "COMMENT ON COLUMN population_versions.id IS 'Identificador.';",
         "COMMENT ON COLUMN population_versions.region_id IS 'Región. Referencia a regions.id. [llave foranea]';",
         "COMMENT ON COLUMN population_versions.version IS 'Número de versión dentro de la región, desde 1.';",
         "COMMENT ON COLUMN population_versions.population IS 'Población total en esa versión.';",
         "COMMENT ON COLUMN population_versions.population_60plus IS 'Población de 60 y más en esa versión.';",
         "COMMENT ON COLUMN population_versions.age_groups IS 'Bandas de edad en esa versión: {grupo: personas}, con edad_no_especificada.';",
         "COMMENT ON COLUMN population_versions.reference_year IS 'Año al que se refieren las cifras (periodo de referencia).';",
         "COMMENT ON COLUMN population_versions.source IS 'De dónde salen: el censo, o el ajuste que las cambió.';",
         "COMMENT ON COLUMN population_versions.reason IS 'Motivo del ajuste; NULL en la versión 1.';",
         "COMMENT ON COLUMN population_versions.created_by IS 'Quien hizo el ajuste. Referencia a users.id. [llave foranea]';",
         "COMMENT ON COLUMN population_versions.created_at IS 'Cuándo se guardó la versión.';",
         ""]
    l.append("INSERT INTO health_areas (state_code, number, name, description, source, source_url) VALUES")
    l.append(",\n".join("    (%s, %d, %s, %s, %s, %s)" % (texto(ESTADO), j["numero"], texto(j["nombre"]),
                                                          texto(j["circunscripcion"]), texto(cita),
                                                          texto(fuente["url"])) for j in lista))
    l.append("ON CONFLICT (state_code, number) DO NOTHING;")
    l.append("")
    l.append("INSERT INTO health_area_municipalities (health_area_id, region_code, partial)")
    l.append("SELECT a.id, v.clave, v.parcial")
    l.append("FROM (VALUES")
    l.append(",\n".join("    (%d, %s, %s)" % (n, texto(c), "true" if p else "false") for n, c, p in miembros))
    l.append(") AS v(numero, clave, parcial)")
    l.append("JOIN health_areas a ON a.state_code = %s AND a.number = v.numero" % texto(ESTADO))
    l.append("ON CONFLICT (health_area_id, region_code) DO NOTHING;")
    l.append("")
    l.append("INSERT INTO census_population (region_code, year, population, source)")
    l.append("SELECT v.clave, v.anio, v.poblacion, %s" % texto(FUENTE_CENSO))
    l.append("FROM (VALUES")
    l.append(",\n".join("    (%s, %d, %d)" % (texto(c), anio, n)
                         for anio in sorted(serie) for c, n in sorted(serie[anio].items())))
    l.append(") AS v(clave, anio, poblacion)")
    l.append("ON CONFLICT (region_code, year) DO NOTHING;")
    l += ["",
          "GRANT SELECT ON health_areas, health_area_municipalities TO svc_regiones;",
          "GRANT SELECT ON census_population TO svc_poblacion;",
          "GRANT SELECT, INSERT ON population_versions TO svc_poblacion;",
          "GRANT USAGE ON SEQUENCE population_versions_id_seq TO svc_poblacion;",
          "",
          "INSERT INTO schema_migrations (version, description)",
          "VALUES ('043', 'Jurisdicciones sanitarias, censos y conteos 1990-2020 y versiones de la población (D58)')",
          "ON CONFLICT (version) DO NOTHING;",
          "",
          "COMMIT;"]
    return "\n".join(l) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n", encoding="utf-8")
    sys.stdout.write(migracion())
