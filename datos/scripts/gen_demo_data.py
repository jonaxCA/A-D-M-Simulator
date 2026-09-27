"""
Genera demo_datos_nl.sql: datos SINTETICOS para la demo local de las 4 pantallas
(dashboard publico, login, dashboard autenticado, mapa de Nuevo Leon).

No es parte de la migracion oficial (001-010). Es justo lo que 010_datos_iniciales.sql
dice que va "en un archivo aparte de datos de demostracion". Se puede volver a correr:
al inicio trunca las tablas que llena, asi que es seguro repetirlo sobre la misma base.

Requiere haber corrido antes datos/postgres/dump_completo.sql.

Uso (desde la raiz del proyecto):
  python3 datos/scripts/gen_demo_data.py > datos/postgres/semillas/demo_datos_nl.sql
  psql -d simulador_epidemico -v ON_ERROR_STOP=1 -f datos/postgres/semillas/demo_datos_nl.sql

Ojo: cada corrida genera un hash bcrypt nuevo para la usuaria de demostracion,
asi que regenerar el archivo cambia esa linea aunque los datos sean los mismos.
"""
import random
import datetime
import bcrypt

random.seed(42)

TODAY = datetime.date(2026, 9, 3)  # fecha "de hoy" para la demo, fija y reproducible
DAYS_BACK = 45

# code, poblacion, lat, lon (centroides ya cargados por 010_datos_iniciales.sql),
# multiplicador fijo de intensidad (heterogeneidad entre municipios: sin esto, la
# incidencia por 100k sale casi identica en los 10 y el mapa no muestra variedad).
NL_MUNICIPIOS = [
    ("19039", 1142994, 25.6866, -100.3161, 1.3),  # Monterrey
    ("19019", 132169,  25.6579, -100.4022, 0.5),  # San Pedro Garza Garcia
    ("19026", 643143,  25.6768, -100.2597, 1.6),  # Guadalupe
    ("19006", 656464,  25.7819, -100.1886, 1.4),  # Apodaca
    ("19021", 481157,  25.7954, -100.3181, 1.7),  # General Escobedo
    ("19048", 306322,  25.6731, -100.4583, 0.8),  # Santa Catarina
    ("19046", 412199,  25.7417, -100.3028, 1.1),  # San Nicolas de los Garza
    ("19031", 466465,  25.6466, -100.0961, 0.9),  # Juarez
    ("19018", 412199,  25.8133, -100.5856, 0.6),  # Garcia
    ("19049", 45988,   25.4247, -100.1472, 0.3),  # Santiago
]

# code, peso_base (casos por 100k por dia, ventana estable), tendencia (multiplicador
# de la ultima semana sobre la base -- >1 sube, <1 baja, =1 estable)
DISEASES = [
    ("INFLUENZA_ESTACIONAL", 0.55, 2.30),
    ("DENGUE_DEMO",           0.22, 1.55),
    ("SARS_COV_2_ANCESTRAL",  0.40, 0.60),
    ("ZIKA_DEMO",             0.06, 1.00),
    ("MALARIA_DEMO",          0.12, 1.60),
    # PATOGENO_X queda sin casos: es el "escenario de preparacion" del catalogo original.
]

SEV_CHOICES = [("asintomatico", 0.30), ("leve", 0.55), ("grave", 0.13), ("fallecido", 0.02)]
RESULT_CHOICES = [("positivo", 0.75), ("pendiente", 0.15), ("negativo", 0.10)]


def weighted_choice(pairs):
    r = random.random()
    acc = 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def gen_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def main():
    out = []
    out.append("-- =============================================================================")
    out.append("-- demo_datos_nl.sql  (NO es parte de la migracion oficial 001-010)")
    out.append("-- Datos SINTETICOS para la demo local: dashboard publico, login, dashboard")
    out.append("-- autenticado y mapa epidemiologico -- alcance Nuevo Leon unicamente.")
    out.append(f"-- Generado por gen_demo_data.py, seed fija (42), 'hoy' simulado = {TODAY.isoformat()}.")
    out.append("-- Seguro de volver a correr: trunca antes de insertar.")
    out.append("--")
    out.append("-- Requiere: dump_completo.sql ya aplicado (schema + catalogos + admin).")
    out.append("-- =============================================================================")
    out.append("")
    out.append("BEGIN;")
    out.append("")

    out.append("-- Reinicio limpio de las tablas que toca esta demo. No toca users/roles reales")
    out.append("-- salvo por el INSERT del usuario de demo mas abajo (ON CONFLICT DO NOTHING).")
    out.append("TRUNCATE case_attachments, cases, scenario_interventions, simulation_runs,")
    out.append("         simulation_batches, scenario_versions, scenarios RESTART IDENTITY CASCADE;")
    out.append("")

    out.append("-- ---------------------------------------------------------------------------")
    out.append("-- Enfermedades adicionales, solo para variedad visual en 'Resumen de Situacion'.")
    out.append("-- Parametros de literatura general, NO calibrados -- mismo criterio que 010.")
    out.append("-- ---------------------------------------------------------------------------")
    # r0 / dias_hospitalizacion / tasa_hospitalizacion / letalidad con fuente o
    # supuesto explicito: mismos valores y texto que la migracion
    # 025_parametros_enfermedades_restantes.sql. Van tambien aqui porque el dump
    # (que trae esa migracion) corre ANTES que esta semilla -- ver el header de
    # esa migracion. Sin esto, una instalacion nueva crea estas tres
    # enfermedades sin poder simularse hasta que alguien vuelva a correr el
    # dump sobre una base que ya tenga la semilla aplicada.
    out.append("""INSERT INTO diseases (code, name, description, default_params) VALUES
    ('DENGUE_DEMO', 'Dengue',
     'Arbovirus transmitido por Aedes aegypti. Parametros de referencia, no calibrados.',
     '{"incubacion_dias": {"dist": "lognormal", "media": 5.5, "desv": 1.5},
       "infeccioso_dias": {"dist": "lognormal", "media": 5.0, "desv": 1.0},
       "prob_asintomatico": 0.60, "transmisibilidad_base": 0.015,
       "dias_hospitalizacion": {"valor": 3.46, "supuesto": false,
           "fuente": "Khalil MAM et al. 2014, BMC Res Notes 7:473. Estancia hospitalaria media de 532 pacientes con dengue confirmado, Hospital Aga Khan, Pakistan: 3.46 (DE 3.45) dias, mediana 3 (RIC 2-4). doi:10.1186/1756-0500-7-473"},
       "letalidad": {"valor": 0.000175, "supuesto": true,
           "fuente": "DERIVADO POR EL EQUIPO: Haider et al. 2025, Int J Infect Dis, p.107940, reporta 9508 muertes de dengue en 2024 sobre los casos notificados globalmente: letalidad de 0.07% por caso notificado (no por infeccion). El CDC (cdc.gov/dengue/hcp/clinical-signs/) indica que 1 de cada 4 infecciones de dengue es sintomatica. El equipo convierte a letalidad por infeccion: 0.0007 x 0.25 = 0.000175. Ninguna de las dos fuentes publica esta conversion. doi:10.1016/j.ijid.2025.107940"},
       "r0": {"valor": 3.44, "supuesto": true,
           "fuente": "SUPUESTO DEL EQUIPO: Liu et al. 2020, Environ Res 182:109114, revision sistematica de 65 estudios de R0 de dengue, zika y chikungunya. El R0 promedio en zona climatica tropical fue 3.44 (temperada 2.03, subtropical 10.29); el articulo no separa el promedio por enfermedad dentro de cada zona, asi que este valor es un proxy, no una estimacion de dengue en particular. Ademas el dengue se transmite por vector (Aedes aegypti) y este motor es un SEIR de persona a persona: usar aqui un R0 de vector es una simplificacion del equipo. doi:10.1016/j.envres.2020.109114"},
       "tasa_hospitalizacion": {"valor": 0.0965, "supuesto": true,
           "fuente": "DERIVADO POR EL EQUIPO: Rodriguez DM et al. 2024, MMWR 73(49):1112-1117, reporta 38.6% de hospitalizacion entre 39094 casos de dengue notificados en Puerto Rico, 2010-2024 (por caso notificado, no por infeccion). El CDC (cdc.gov/dengue/hcp/clinical-signs/) indica que 1 de cada 4 infecciones de dengue es sintomatica. El equipo convierte a tasa por infeccion: 0.386 x 0.25 = 0.0965. Ninguna de las dos fuentes publica esta conversion. doi:10.15585/mmwr.mm7349a1"}
      }'::jsonb),
    ('ZIKA_DEMO', 'Zika',
     'Arbovirus transmitido por Aedes. Parametros de referencia, no calibrados.',
     '{"incubacion_dias": {"dist": "lognormal", "media": 6.0, "desv": 2.0},
       "infeccioso_dias": {"dist": "lognormal", "media": 5.0, "desv": 1.5},
       "prob_asintomatico": 0.80, "transmisibilidad_base": 0.010,
       "dias_hospitalizacion": {"valor": 8.0, "supuesto": true,
           "fuente": "SUPUESTO DEL EQUIPO sobre Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516: en casos confirmados de zika con sindrome de Guillain-Barre la estancia hospitalaria mediana fue de 8 a 31 dias. Ese sindrome es solo una fraccion de las hospitalizaciones por zika (el mismo articulo reporta 11% de hospitalizacion general, ver tasa_hospitalizacion), asi que el equipo usa el extremo bajo del rango (8 dias) como mas representativo del conjunto, no el promedio del rango de Guillain-Barre. doi:10.1371/journal.pntd.0009516"},
       "letalidad": {"valor": 0.0005, "supuesto": true,
           "fuente": "DERIVADO POR EL EQUIPO: Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516, reporta letalidad de 0.1% entre los casos confirmados de zika de su revision (mayoria sintomatica), no por infeccion. Mitchell PK et al. 2019, Am J Epidemiol 188(1):206-213, estima que 50% de las infecciones de zika en Puerto Rico fueron sintomaticas (27% en Yap, 44% en Polinesia Francesa). El equipo convierte con el dato de Puerto Rico: 0.001 x 0.50 = 0.0005. Ninguna de las dos fuentes publica esta conversion. doi:10.1371/journal.pntd.0009516 y doi:10.1093/aje/kwy189"},
       "r0": {"valor": 2.5, "supuesto": true,
           "fuente": "SUPUESTO DEL EQUIPO: McCain K et al. 2026, Nature Health 1(3):355-367, revision sistematica y metaanalisis de epidemiologia de zika. De 77 estimaciones de R0 extraidas, la mayoria (63/77) cayo entre 1.5 y 4 (rango completo 1.12-7.4); el equipo elige un punto dentro de ese rango mayoritario. Ademas el zika se transmite por vector (Aedes) y este motor es un SEIR de persona a persona: usar aqui un R0 de vector es una simplificacion del equipo. doi:10.1038/s44360-025-00051-4"},
       "tasa_hospitalizacion": {"valor": 0.055, "supuesto": true,
           "fuente": "DERIVADO POR EL EQUIPO: Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516, reporta 347 de 3167 casos confirmados de zika hospitalizados (11%; los propios autores advierten que la cifra puede estar inflada por incluir series de casos ya hospitalizados). Es una tasa por caso confirmado (mayoria sintomatica), no por infeccion. Mitchell PK et al. 2019, Am J Epidemiol 188(1):206-213, estima 50% de infecciones sintomaticas en Puerto Rico. El equipo convierte: 0.11 x 0.50 = 0.055. Ninguna de las dos fuentes publica esta conversion. doi:10.1371/journal.pntd.0009516 y doi:10.1093/aje/kwy189"}
      }'::jsonb),
    ('MALARIA_DEMO', 'Malaria',
     'Transmitida por Anopheles. Parametros de referencia, no calibrados.',
     '{"incubacion_dias": {"dist": "lognormal", "media": 12.0, "desv": 3.0},
       "infeccioso_dias": {"dist": "lognormal", "media": 14.0, "desv": 4.0},
       "prob_asintomatico": 0.20, "transmisibilidad_base": 0.008,
       "dias_hospitalizacion": {"valor": 2.0, "supuesto": false,
           "fuente": "Ocen E et al. 2023, Malar J 22:325. Mediana de estancia hospitalaria de 2 dias (RIC 2-4) en pacientes con malaria grave, hospital de distrito de Apac, Uganda. doi:10.1186/s12936-023-04761-6"},
       "letalidad": {"valor": 0.004, "supuesto": true,
           "fuente": "SUPUESTO DEL EQUIPO en un punto del rango de la OMS: la pagina de metadatos del indicador de mortalidad por malaria del Global Health Observatory (who.int/data/gho/indicator-metadata-registry/imr-details/16) indica que se aplica \\"a case fatality rate of between 0.01% and 0.40%\\" a los casos estimados de P. falciparum fuera de Africa y en paises africanos de baja transmision, la categoria en la que caeria Nuevo Leon. El equipo elige el extremo alto del rango (0.40%) por tratarse de poblacion sin inmunidad previa."},
       "r0": {"valor": 1.5, "supuesto": true,
           "fuente": "SUPUESTO DEL EQUIPO: Smith DL et al. 2007, PLoS Biology 5(3):e42, reporta 121 estimaciones de R0 de P. falciparum en poblaciones africanas que van, en sus palabras, \\"from around one to more than 3,000\\" (hasta casi 11,000 con ajustes adicionales). Nuevo Leon no es zona endemica y no tiene la densidad ni competencia vectorial de Anopheles de un escenario africano holoendemico: el equipo elige un valor cercano al extremo bajo del rango publicado (1.5) como el mas conservador y plausible para una transmision marginal o importada. No corresponde a ninguna medicion especifica. doi:10.1371/journal.pbio.0050042"},
       "tasa_hospitalizacion": {"valor": 0.6712, "supuesto": true,
           "fuente": "DERIVADO POR EL EQUIPO: Mace KE et al. 2022, MMWR Surveill Summ 71(8):1-29 (vigilancia de malaria en Estados Unidos, 2018) reporta por separado que de 1572 pacientes con malaria no complicada, 988 (62.8%) fueron hospitalizados, y que de 251 casos de malaria grave, 250 (99.6%) tuvieron estado de hospitalizacion conocido y de esos 235 (94.0%) lo fueron. El articulo no publica una cifra combinada. El equipo calcula un PROMEDIO PONDERADO POR CASO (no un promedio de los dos porcentajes, que mezclaria denominadores muy distintos sin sentido): suma los hospitalizados y los casos con estado conocido de ambas subpoblaciones -- (988+235)/(1572+250) = 1223/1822 = 0.67124, redondeado 0.6712 -- verificado contra el texto original del articulo (cdc.gov/mmwr/volumes/71/ss/ss7108a1.htm). Es una tasa por caso DIAGNOSTICADO de la vigilancia de EEUU (malaria importada por viajeros, casi siempre sintomatica): a diferencia de dengue/zika aqui no se convierte por infeccion, porque no hay evidencia en la fuente de una fraccion grande de infecciones subclinicas sin diagnosticar que corregir. El calculo combinado es del equipo, no del articulo, y no esta calibrado para Nuevo Leon."}
      }'::jsonb)
ON CONFLICT (code) DO NOTHING;
""")

    demo_password = "Epidemia2026!"
    admin_password = "Admin2026!"
    hash_epidemiologa = gen_password_hash(demo_password)
    hash_analista = gen_password_hash(demo_password)
    hash_admin = gen_password_hash(admin_password)
    out.append("-- ---------------------------------------------------------------------------")
    out.append("-- Usuarios de demostracion para el recorrido. Passwords reales (bcrypt).")
    out.append("-- Son dos personas distintas a proposito: el flujo de aprobacion exige que")
    out.append("-- quien construye el escenario no sea quien lo autoriza (ver migracion 013).")
    out.append("--   analista:      alex.cavazos   (rol ANALISTA)")
    out.append("--   epidemiologa:  diana.flores   (rol EPIDEMIOLOGO)")
    out.append(f"--   password de ambos:  {demo_password}   (documentada tambien en README.md)")
    out.append("-- Mas abajo se le pone contrasena tambien a 'admin', que 010 crea con un")
    out.append("-- marcador invalido a proposito.")
    out.append("-- SOLO para el entorno local -- no usar este patron en un ambiente real.")
    out.append("-- ---------------------------------------------------------------------------")
    out.append(f"""INSERT INTO users (username, email, password_hash, full_name, is_active)
VALUES ('diana.flores', 'diana.flores@salud.nl.gob.mx', '{hash_epidemiologa}',
        'Diana Flores', TRUE),
       ('alex.cavazos', 'alex.cavazos@salud.nl.gob.mx', '{hash_analista}',
        'Alex Cavazos', TRUE)
ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u CROSS JOIN roles r
WHERE u.username = 'diana.flores' AND r.code = 'EPIDEMIOLOGO'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u CROSS JOIN roles r
WHERE u.username = 'alex.cavazos' AND r.code = 'ANALISTA'
ON CONFLICT DO NOTHING;

-- Cuenta de administracion. 010_datos_iniciales.sql la crea con el marcador
-- invalido REEMPLAZAR_ANTES_DE_DESPLEGAR justamente para que el esquema nunca
-- viaje con una contrasena por defecto que funcione. Aqui se le pone una real
-- porque esto son datos de demostracion: quien instale solo las migraciones,
-- sin este archivo, sigue sin poder entrar con esa cuenta.
--   usuario:   admin
--   password:  {admin_password}
UPDATE users SET password_hash = '{hash_admin}' WHERE username = 'admin';

-- Red de seguridad: 010 ya le asigna el rol; esto solo cubre una base donde se
-- haya perdido la asignacion.
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u CROSS JOIN roles r
WHERE u.username = 'admin' AND r.code = 'ADMINISTRADOR'
ON CONFLICT DO NOTHING;
""")

    out.append("-- ---------------------------------------------------------------------------")
    out.append("-- Un escenario publicado con su version aprobada. Sin corridas: las crea quien")
    out.append("-- ejecute la simulacion desde la pantalla.")
    out.append("-- ---------------------------------------------------------------------------")
    out.append("""INSERT INTO scenarios (name, description, disease_id, region_id, owner_id, status, is_public)
SELECT 'Ola Influenza ZMM - otono 2026',
       'Escenario de demostracion: proyeccion de la temporada de influenza en el area metropolitana.',
       d.id, r.id, u.id, 'publicado', TRUE
FROM diseases d, regions r, users u
WHERE d.code = 'INFLUENZA_ESTACIONAL' AND r.code = '19' AND u.username = 'alex.cavazos';

-- La version la construye el analista y la aprueba la epidemiologa: dos
-- personas distintas, como exige ck_scenario_versions_no_autoaprobacion (013).
-- Queda aprobada para poder simularla desde la pantalla: fn_version_aprobada
-- (014) rechaza simular cualquier otra cosa.
INSERT INTO scenario_versions (scenario_id, version_number, is_current, population_size,
                               horizon_days, initial_infected, notes, created_by,
                               status, submitted_at, reviewed_by, reviewed_at, review_comment)
SELECT s.id, 1, TRUE, 500000, 180, 100, 'Version inicial para el entorno local.', autor.id,
       'aprobado', now() - interval '3 days', revisor.id, now() - interval '2 days',
       'Parametros consistentes con la temporada anterior.'
FROM scenarios s, users autor, users revisor
WHERE s.name = 'Ola Influenza ZMM - otono 2026'
  AND autor.username = 'alex.cavazos'
  AND revisor.username = 'diana.flores';
""")

    out.append("-- ---------------------------------------------------------------------------")
    out.append(f"-- Casos sinteticos, Nuevo Leon, ultimos {DAYS_BACK} dias. Un renglon de VALUES por caso.")
    out.append("-- disease_id/region_id se resuelven por codigo (no por id numerico) para que")
    out.append("-- este script no dependa del orden exacto en que se insertaron los catalogos.")
    out.append("-- ---------------------------------------------------------------------------")

    case_rows = []
    for mun_code, poblacion, lat, lon, mun_mult in NL_MUNICIPIOS:
        for dis_code, peso_base, tendencia in DISEASES:
            for day_offset in range(DAYS_BACK, -1, -1):
                report_date = TODAY - datetime.timedelta(days=day_offset)
                # semana actual (0-6) vs semana previa (7-13) a tasa base: comparacion
                # limpia, sin rampa, para que el % semanal que ve el dashboard sea
                # directamente el de la tendencia definida arriba.
                factor = tendencia if day_offset <= 6 else 1.0
                lam = (poblacion / 100000.0) * peso_base * factor * mun_mult
                n_casos = int(random.gauss(lam, max(lam * 0.22, 0.4)) + 0.5)
                n_casos = max(0, n_casos)
                for _ in range(n_casos):
                    age = max(0, min(95, int(random.gauss(34, 20))))
                    sex = random.choice(["M", "F"])
                    onset_lag = random.randint(0, 4)
                    onset_date = report_date - datetime.timedelta(days=onset_lag)
                    jlat = lat + random.uniform(-0.05, 0.05)
                    jlon = lon + random.uniform(-0.05, 0.05)
                    severity = weighted_choice(SEV_CHOICES)
                    result = weighted_choice(RESULT_CHOICES)
                    status = "validado" if random.random() < 0.85 else "pendiente"
                    case_rows.append(
                        f"('{dis_code}','{mun_code}',{age},'{sex}','{onset_date.isoformat()}',"
                        f"'{report_date.isoformat()}',{jlat:.6f},{jlon:.6f},'{result}','{severity}','{status}')"
                    )

    out.append(f"-- total de casos generados: {len(case_rows)}")
    out.append("INSERT INTO cases (local_uuid, reported_by, disease_id, region_id, age, sex, "
                "onset_date, report_date, latitude, longitude, test_result, severity, status, created_at)")
    out.append("SELECT gen_random_uuid(), u.id, d.id, r.id, t.age, t.sex, t.onset_date::date, "
                "t.report_date::date, t.lat, t.lon, t.test_result, t.severity, t.status, "
                "t.report_date::timestamptz + time '08:00'")
    out.append("FROM (VALUES")
    out.append(",\n".join("    " + row for row in case_rows))
    out.append(") AS t(disease_code, region_code, age, sex, onset_date, report_date, lat, lon, test_result, severity, status)")
    out.append("JOIN diseases d ON d.code = t.disease_code")
    out.append("JOIN regions  r ON r.code  = t.region_code")
    out.append("CROSS JOIN (SELECT id FROM users WHERE username = 'diana.flores') u;")
    out.append("")
    out.append("COMMIT;")

    print("\n".join(out))


if __name__ == "__main__":
    main()
