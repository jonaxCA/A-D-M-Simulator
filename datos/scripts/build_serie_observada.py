# La serie observada con la que se calibra y se valida seir-ref (D50).
#
#   python datos/scripts/build_serie_observada.py agrega <COVID19MEXICO2020.zip>
#       Cuenta, del cierre anual 2020 de los datos abiertos de COVID-19 de la DGE, los casos
#       confirmados de Nuevo Leon por semana epidemiologica de inicio de sintomas y escribe
#       datos/observados/covid19_nl_2020_semanal.csv. El zip no entra al repositorio: trae un
#       registro por persona (RNF-I05) y solo se procesa en local.
#
#   python datos/scripts/build_serie_observada.py > datos/postgres/migraciones/061_serie_observada.sql
#       Genera la 061 a partir de ese CSV, con los puntos de la ventana.
#
# La ventana (D50: de la primera semana con casos a la anterior a la segunda ola) se fija por
# regla y no a ojo: empieza en la primera semana con casos; el pico de la primera ola es la
# primera semana seguida de tres descensos; termina en el valle, la semana con menos casos
# despues del pico entre las semanas completas de 2020. Si el valle cae en las ultimas cuatro
# semanas del archivo, el script se detiene: seria el corte del archivo y no la ola.
import csv
import datetime as dt
import hashlib
import io
import sys
import zipfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSV = RAIZ / "datos" / "observados" / "covid19_nl_2020_semanal.csv"

URL = "https://datosabiertos.salud.gob.mx/gobmx/salud/datos_abiertos/historicos/2020/COVID19MEXICO2020.zip"
FUENTE = ("Secretaría de Salud, Dirección General de Epidemiología. Datos Abiertos de COVID-19, "
          "cierre anual 2020 (COVID19MEXICO2020.zip)")
LICENCIA = "Datos abiertos, Decreto DOF del 20-02-2015, art. 5, fr. III: libre uso, citando la fuente"
NOMBRE = "Casos confirmados de COVID-19 en Nuevo León por semana de inicio de síntomas, primera ola de 2020"
CODIGO = "COVID19_NL_2020_SINTOMAS"
ENTIDAD = "19"
CONFIRMADO = {"1", "2", "3"}
ANIO = 2020


def domingo(fecha):
    return fecha - dt.timedelta(days=(fecha.weekday() + 1) % 7)


def semanas_completas(conteo):
    # De la primera semana con casos a la ultima que cabe entera en el anio.
    primera = min(conteo)
    ultima = domingo(dt.date(ANIO, 12, 31))
    if ultima + dt.timedelta(days=6) > dt.date(ANIO, 12, 31):
        ultima -= dt.timedelta(days=7)
    semanas, s = [], primera
    while s <= ultima:
        semanas.append((s, conteo.get(s, 0)))
        s += dt.timedelta(days=7)
    return semanas


def ventana(semanas):
    valores = [v for _, v in semanas]
    inicio = next(i for i, v in enumerate(valores) if v > 0)
    pico = next(i for i in range(inicio, len(valores) - 3)
                if valores[i] > valores[i + 1] > valores[i + 2] > valores[i + 3])
    valle = min(range(pico + 1, len(valores)), key=lambda i: (valores[i], i))
    if valle >= len(valores) - 4:
        sys.exit("El valle cae en las últimas semanas del archivo (%s): revisa el corte." % semanas[valle][0])
    return semanas[inicio:valle + 1], semanas[pico][0]


def agrega(ruta_zip):
    huella = hashlib.sha256(Path(ruta_zip).read_bytes()).hexdigest()
    conteo, cortes = Counter(), set()
    with zipfile.ZipFile(ruta_zip) as z, z.open(z.namelist()[0]) as f:
        filas = csv.reader(io.TextIOWrapper(f, encoding="utf-8", newline=""))
        cabecera = next(filas)
        # En julio de 2024 la DGE renombró CLASIFICACION_FINAL a CLASIFICACION_FINAL_COVID.
        clasificacion = "CLASIFICACION_FINAL" if "CLASIFICACION_FINAL" in cabecera else "CLASIFICACION_FINAL_COVID"
        i_corte, i_entidad, i_sintomas, i_clase = (cabecera.index(c) for c in (
            "FECHA_ACTUALIZACION", "ENTIDAD_RES", "FECHA_SINTOMAS", clasificacion))
        for fila in filas:
            cortes.add(fila[i_corte])
            if fila[i_entidad] == ENTIDAD and fila[i_clase] in CONFIRMADO:
                fecha = dt.date.fromisoformat(fila[i_sintomas])
                if fecha.year == ANIO:
                    conteo[domingo(fecha)] += 1
    semanas = semanas_completas(conteo)
    puntos, pico = ventana(semanas)
    encabezado = [
        NOMBRE + ".",
        "",
        "fuente: " + FUENTE,
        "url: " + URL,
        "licencia: " + LICENCIA,
        "corte: " + max(cortes),
        "sha256: " + huella,
        "consultado: " + dt.date.today().isoformat(),
        "filtro: ENTIDAD_RES = 19 y %s 1, 2 o 3 (confirmado); semana de domingo a sábado por FECHA_SINTOMAS"
        % clasificacion,
        "pico: " + pico.isoformat(),
        "ventana: %s a %s (%d semanas)" % (puntos[0][0], puntos[-1][0], len(puntos)),
        "",
        "Van todas las semanas completas de 2020; la 061 carga solo las de la ventana. La del",
        "2020-12-27 queda fuera porque termina en 2021. El cierre 2021 no trae casos de Nuevo León",
        "con inicio de síntomas en 2020 (revisado el 2026-11-22). Lo genera",
        "datos/scripts/build_serie_observada.py: no se edita a mano.",
    ]
    with open(CSV, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(("# " + l).rstrip() + "\n" for l in encabezado)
        f.write("periodo_inicio,valor\n")
        f.writelines("%s,%d\n" % (s, v) for s, v in semanas)
    print("Escrito %s: %d semanas, ventana %s a %s." % (CSV.relative_to(RAIZ), len(semanas), puntos[0][0], puntos[-1][0]))


def lee_csv():
    meta, semanas = {}, []
    for linea in CSV.read_text(encoding="utf-8").splitlines():
        if linea.startswith("#"):
            clave, _, valor = linea[1:].strip().partition(": ")
            if valor:
                meta[clave] = valor
        elif linea and linea != "periodo_inicio,valor":
            inicio, valor = linea.split(",")
            semanas.append((dt.date.fromisoformat(inicio), int(valor)))
    return meta, semanas


def texto(valor):
    return "'" + valor.replace("'", "''") + "'"


def migracion():
    meta, semanas = lee_csv()
    puntos, _ = ventana(semanas)
    valores = ",\n".join("    ('%s', %d)" % p for p in puntos)
    return f"""SET client_encoding = 'UTF8';
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
-- - La serie de D50: {CODIGO} version 1, los casos confirmados de
--   Nuevo Leon por semana de inicio de sintomas, de {puntos[0][0]} a {puntos[-1][0]}
--   ({len(puntos)} semanas, {sum(v for _, v in puntos)} casos). Sale de
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
    CONSTRAINT ck_observed_datasets_codigo CHECK (code ~ '^[A-Z0-9_]{{3,60}}$'),
    CONSTRAINT ck_observed_datasets_version CHECK (version >= 1),
    CONSTRAINT ck_observed_datasets_metrica CHECK (metric IN
        ('casos_confirmados', 'hospitalizaciones', 'defunciones')),
    CONSTRAINT ck_observed_datasets_periodo CHECK (period IN ('semana', 'dia')),
    CONSTRAINT ck_observed_datasets_huella CHECK (sha256 ~ '^[0-9a-f]{{64}}$'),
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
SELECT {texto(CODIGO)}, 1,
       {texto(NOMBRE)},
       d.id, r.id, 'casos_confirmados', 'semana',
       {texto(meta["fuente"])},
       {texto(meta["licencia"])},
       {texto(meta["url"])},
       DATE '{meta["corte"]}', '{meta["sha256"]}'
FROM diseases d, regions r
WHERE d.code = 'SARS_COV_2_ANCESTRAL' AND r.code = '19'
ON CONFLICT (code, version) DO NOTHING;

INSERT INTO observed_points (dataset_id, period_start, value)
SELECT o.id, v.inicio::date, v.valor
FROM observed_datasets o
CROSS JOIN (VALUES
{valores}
) AS v (inicio, valor)
WHERE o.code = {texto(CODIGO)} AND o.version = 1
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version, description)
VALUES ('061', 'Series observadas: observed_datasets, observed_points, datasets.upload, svc_importacion y la serie de D50')
ON CONFLICT (version) DO NOTHING;

COMMIT;
"""


def main():
    if sys.argv[1:2] == ["agrega"] and len(sys.argv) == 3:
        agrega(sys.argv[2])
    elif len(sys.argv) == 1:
        # LF y UTF-8 tambien en Windows, donde la salida redirigida saldria en cp1252.
        sys.stdout.reconfigure(newline="\n", encoding="utf-8")
        sys.stdout.write(migracion())
    else:
        sys.exit("Uso: build_serie_observada.py [agrega <COVID19MEXICO2020.zip>]")


if __name__ == "__main__":
    main()
