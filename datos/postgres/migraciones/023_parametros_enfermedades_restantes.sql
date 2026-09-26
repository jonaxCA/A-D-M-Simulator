-- =============================================================================
-- 023_parametros_enfermedades_restantes.sql
-- Dominio: catalogos.
--
-- Cierra el ultimo pendiente de la checklist de enfermedades: captura R0, tasa
-- de hospitalizacion, dias de hospitalizacion y letalidad -- con su fuente o
-- con la marca explicita de supuesto -- para las cuatro enfermedades que 017 y
-- 020 no tocaron: DENGUE_DEMO, ZIKA_DEMO, MALARIA_DEMO y PATOGENO_X. Con esto
-- las 6 enfermedades del catalogo quedan con sus seis parametros y son
-- simulables (ver backend_web/queries.py: estado_parametros()).
--
-- OJO CON DENGUE, ZIKA Y MALARIA: SON DE VECTOR, EL MOTOR ES DE PERSONA A
-- PERSONA. El motor (procesamiento/motor/parametros.py) es un SEIR con capas
-- de contacto entre personas; dengue, zika y malaria se transmiten por
-- mosquito, no de persona a persona. Un R0 de vector bien citado igual produce
-- una simulacion segura y equivocada: CIERRE_ESCUELAS o REDUCCION_AFORO no
-- actuan sobre la transmision real de estas tres enfermedades como el modelo
-- supone. Este archivo captura los parametros para que la pantalla las
-- marque simulables (que es lo que pedia la checklist), pero la decision de
-- si tiene sentido correrlas con este motor -- o esperar a un modelo con
-- vector -- sigue abierta; por eso r0 va marcado como supuesto del equipo en
-- las tres, con la conversion explicada.
--
-- QUE TRAE FUENTE Y QUE ES SUPUESTO (cada cifra se verifico en el texto de su
-- fuente antes de capturarla; ninguna esta calibrada para Nuevo Leon):
--
--   DENGUE_DEMO
--     - dias_hospitalizacion: Khalil et al. 2014 (Pakistan), valor directo.
--     - r0: promedio de zona tropical de Liu et al. 2020 (revision de dengue,
--       zika y chikungunya juntos, no solo dengue) usado como proxy.
--     - tasa_hospitalizacion y letalidad: la fuente los publica por caso
--       notificado (mayoria sintomatico); el equipo los convierte a "por
--       infeccion" con el 25% de infecciones sintomaticas que reporta el CDC.
--       La conversion es del equipo, no de la fuente.
--
--   ZIKA_DEMO
--     - r0: punto elegido dentro del rango mayoritario (1.5-4) de la revision
--       de McCain et al. 2026.
--     - dias_hospitalizacion: extremo bajo del rango de estancia de los casos
--       con sindrome de Guillain-Barre de Halani et al. 2021, porque ese
--       sindrome es solo una fraccion de las hospitalizaciones por zika.
--     - tasa_hospitalizacion y letalidad: Halani et al. 2021 los publica por
--       caso confirmado; el equipo los convierte a "por infeccion" con el 50%
--       de infecciones sintomaticas que estima Mitchell et al. 2019 para
--       Puerto Rico. La conversion es del equipo.
--
--   MALARIA_DEMO
--     - dias_hospitalizacion: Ocen et al. 2023 (Uganda, malaria grave), valor
--       directo.
--     - r0: Smith et al. 2007 reporta un rango enorme (de ~1 a mas de 3,000)
--       para poblaciones africanas holoendemicas. Nuevo Leon no es zona
--       endemica; el equipo elige el extremo bajo del rango como el mas
--       plausible para una transmision marginal o importada. No corresponde a
--       ninguna medicion especifica.
--     - tasa_hospitalizacion: Mace et al. 2022 (vigilancia de EEUU 2018)
--       publica, por separado, la hospitalizacion de malaria no complicada
--       (988/1572, 62.8%) y de malaria grave con estado conocido (235/250,
--       94.0%), pero no una cifra combinada. El equipo calcula un PROMEDIO
--       PONDERADO POR CASO (no un promedio de los dos porcentajes, que no
--       tendria sentido con denominadores tan distintos): suma los
--       hospitalizados y los casos con estado conocido de las dos
--       subpoblaciones -- (988+235)/(1572+250) = 67.12% -- para obtener una
--       tasa por caso DIAGNOSTICADO. A diferencia de dengue/zika, no se
--       convierte "por infeccion": la vigilancia de EEUU es de malaria
--       importada por viajeros, casi siempre sintomatica y diagnosticada, sin
--       la fraccion grande de infecciones subclinicas que si hay que corregir
--       en dengue/zika. El calculo combinado es del equipo, no del articulo.
--     - letalidad: punto elegido (el extremo alto, por tratarse de poblacion
--       sin inmunidad previa) dentro del rango 0.01%-0.40% que la OMS aplica a
--       los casos de P. falciparum fuera de Africa.
--
--   PATOGENO_X
--     Es un escenario hipotetico -- el concepto "Disease X" del plan de I+D de
--     la OMS para un patogeno desconocido con potencial epidemico
--     (who.int/teams/blueprint/who-r-and-d-blueprint-for-epidemics). No hay
--     literatura que citar porque no es un patogeno real: los seis parametros
--     van como supuesto del equipo por diseno, no por falta de trabajo. Se
--     definio como un escenario de gravedad intermedia-alta (mas transmisible
--     y letal que la influenza estacional, menos letal que el SARS-CoV-2
--     ancestral) para pruebas de preparacion hospitalaria.
--
-- POR QUE DENGUE_DEMO, ZIKA_DEMO Y MALARIA_DEMO SE QUEDAN SIN EFECTO EN UNA
-- INSTALACION NUEVA. Esas tres filas no las crea una migracion: las crea
-- datos/postgres/semillas/demo_datos_nl.sql, que corre DESPUES de
-- dump_completo.sql (ver docs/INSTALACION.md, Paso 2). En una instalacion
-- nueva, cuando este archivo corre dentro del dump, esas filas todavia no
-- existen y el UPDATE de cada una no actualiza ninguna fila -- es el mismo
-- caso que documenta datos/scripts/verifica_migraciones.py para una migracion
-- que depende de una semilla. Por eso demo_datos_nl.sql tambien se actualizo
-- para traer estos mismos parametros en el INSERT: una instalacion nueva
-- queda completa con la semilla, y una base que ya tenia esas tres
-- enfermedades (de una instalacion anterior) queda completa con este UPDATE.
--
-- SE RESPETA LO QUE YA HAYA: el operador || fusiona, asi que las claves que no
-- se mencionan (incubacion_dias, infeccioso_dias, prob_asintomatico,
-- transmisibilidad_base) quedan intactas. Y solo actua si la enfermedad
-- todavia no tiene r0, para no pisar parametros que alguien haya capturado o
-- corregido desde la pantalla.
-- =============================================================================

BEGIN;

-- Dengue
UPDATE diseases
SET    default_params = default_params || '{
            "dias_hospitalizacion": {
                    "fuente": "Khalil MAM et al. 2014, BMC Res Notes 7:473. Estancia hospitalaria media de 532 pacientes con dengue confirmado, Hospital Aga Khan, Pakistan: 3.46 (DE 3.45) dias, mediana 3 (RIC 2-4). doi:10.1186/1756-0500-7-473",
                    "supuesto": false,
                    "valor": 3.46
            },
            "letalidad": {
                    "fuente": "DERIVADO POR EL EQUIPO: Haider et al. 2025, Int J Infect Dis, p.107940, reporta 9508 muertes de dengue en 2024 sobre los casos notificados globalmente: letalidad de 0.07% por caso notificado (no por infeccion). El CDC (cdc.gov/dengue/hcp/clinical-signs/) indica que 1 de cada 4 infecciones de dengue es sintomatica. El equipo convierte a letalidad por infeccion: 0.0007 x 0.25 = 0.000175. Ninguna de las dos fuentes publica esta conversion. doi:10.1016/j.ijid.2025.107940",
                    "supuesto": true,
                    "valor": 0.000175
            },
            "r0": {
                    "fuente": "SUPUESTO DEL EQUIPO: Liu et al. 2020, Environ Res 182:109114, revision sistematica de 65 estudios de R0 de dengue, zika y chikungunya. El R0 promedio en zona climatica tropical fue 3.44 (temperada 2.03, subtropical 10.29); el articulo no separa el promedio por enfermedad dentro de cada zona, asi que este valor es un proxy, no una estimacion de dengue en particular. Ademas el dengue se transmite por vector (Aedes aegypti) y este motor es un SEIR de persona a persona: usar aqui un R0 de vector es una simplificacion del equipo. doi:10.1016/j.envres.2020.109114",
                    "supuesto": true,
                    "valor": 3.44
            },
            "tasa_hospitalizacion": {
                    "fuente": "DERIVADO POR EL EQUIPO: Rodriguez DM et al. 2024, MMWR 73(49):1112-1117, reporta 38.6% de hospitalizacion entre 39094 casos de dengue notificados en Puerto Rico, 2010-2024 (por caso notificado, no por infeccion). El CDC (cdc.gov/dengue/hcp/clinical-signs/) indica que 1 de cada 4 infecciones de dengue es sintomatica. El equipo convierte a tasa por infeccion: 0.386 x 0.25 = 0.0965. Ninguna de las dos fuentes publica esta conversion. doi:10.15585/mmwr.mm7349a1",
                    "supuesto": true,
                    "valor": 0.0965
            }
    }'::jsonb
WHERE  code = 'DENGUE_DEMO'
  AND  NOT (default_params ? 'r0');

-- Zika
UPDATE diseases
SET    default_params = default_params || '{
            "dias_hospitalizacion": {
                    "fuente": "SUPUESTO DEL EQUIPO sobre Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516: en casos confirmados de zika con sindrome de Guillain-Barre la estancia hospitalaria mediana fue de 8 a 31 dias. Ese sindrome es solo una fraccion de las hospitalizaciones por zika (el mismo articulo reporta 11% de hospitalizacion general, ver tasa_hospitalizacion), asi que el equipo usa el extremo bajo del rango (8 dias) como mas representativo del conjunto, no el promedio del rango de Guillain-Barre. doi:10.1371/journal.pntd.0009516",
                    "supuesto": true,
                    "valor": 8.0
            },
            "letalidad": {
                    "fuente": "DERIVADO POR EL EQUIPO: Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516, reporta letalidad de 0.1% entre los casos confirmados de zika de su revision (mayoria sintomatica), no por infeccion. Mitchell PK et al. 2019, Am J Epidemiol 188(1):206-213, estima que 50% de las infecciones de zika en Puerto Rico fueron sintomaticas (27% en Yap, 44% en Polinesia Francesa). El equipo convierte con el dato de Puerto Rico: 0.001 x 0.50 = 0.0005. Ninguna de las dos fuentes publica esta conversion. doi:10.1371/journal.pntd.0009516 y doi:10.1093/aje/kwy189",
                    "supuesto": true,
                    "valor": 0.0005
            },
            "r0": {
                    "fuente": "SUPUESTO DEL EQUIPO: McCain K et al. 2026, Nature Health 1(3):355-367, revision sistematica y metaanalisis de epidemiologia de zika. De 77 estimaciones de R0 extraidas, la mayoria (63/77) cayo entre 1.5 y 4 (rango completo 1.12-7.4); el equipo elige un punto dentro de ese rango mayoritario. Ademas el zika se transmite por vector (Aedes) y este motor es un SEIR de persona a persona: usar aqui un R0 de vector es una simplificacion del equipo. doi:10.1038/s44360-025-00051-4",
                    "supuesto": true,
                    "valor": 2.5
            },
            "tasa_hospitalizacion": {
                    "fuente": "DERIVADO POR EL EQUIPO: Halani S et al. 2021, PLoS Negl Trop Dis 15(7):e0009516, reporta 347 de 3167 casos confirmados de zika hospitalizados (11%; los propios autores advierten que la cifra puede estar inflada por incluir series de casos ya hospitalizados). Es una tasa por caso confirmado (mayoria sintomatica), no por infeccion. Mitchell PK et al. 2019, Am J Epidemiol 188(1):206-213, estima 50% de infecciones sintomaticas en Puerto Rico. El equipo convierte: 0.11 x 0.50 = 0.055. Ninguna de las dos fuentes publica esta conversion. doi:10.1371/journal.pntd.0009516 y doi:10.1093/aje/kwy189",
                    "supuesto": true,
                    "valor": 0.055
            }
    }'::jsonb
WHERE  code = 'ZIKA_DEMO'
  AND  NOT (default_params ? 'r0');

-- Malaria
UPDATE diseases
SET    default_params = default_params || '{
            "dias_hospitalizacion": {
                    "fuente": "Ocen E et al. 2023, Malar J 22:325. Mediana de estancia hospitalaria de 2 dias (RIC 2-4) en pacientes con malaria grave, hospital de distrito de Apac, Uganda. doi:10.1186/s12936-023-04761-6",
                    "supuesto": false,
                    "valor": 2.0
            },
            "letalidad": {
                    "fuente": "SUPUESTO DEL EQUIPO en un punto del rango de la OMS: la pagina de metadatos del indicador de mortalidad por malaria del Global Health Observatory (who.int/data/gho/indicator-metadata-registry/imr-details/16) indica que se aplica \"a case fatality rate of between 0.01% and 0.40%\" a los casos estimados de P. falciparum fuera de Africa y en paises africanos de baja transmision, la categoria en la que caeria Nuevo Leon. El equipo elige el extremo alto del rango (0.40%) por tratarse de poblacion sin inmunidad previa.",
                    "supuesto": true,
                    "valor": 0.004
            },
            "r0": {
                    "fuente": "SUPUESTO DEL EQUIPO: Smith DL et al. 2007, PLoS Biology 5(3):e42, reporta 121 estimaciones de R0 de P. falciparum en poblaciones africanas que van, en sus palabras, \"from around one to more than 3,000\" (hasta casi 11,000 con ajustes adicionales). Nuevo Leon no es zona endemica y no tiene la densidad ni competencia vectorial de Anopheles de un escenario africano holoendemico: el equipo elige un valor cercano al extremo bajo del rango publicado (1.5) como el mas conservador y plausible para una transmision marginal o importada. No corresponde a ninguna medicion especifica. doi:10.1371/journal.pbio.0050042",
                    "supuesto": true,
                    "valor": 1.5
            },
            "tasa_hospitalizacion": {
                    "fuente": "DERIVADO POR EL EQUIPO: Mace KE et al. 2022, MMWR Surveill Summ 71(8):1-29 (vigilancia de malaria en Estados Unidos, 2018) reporta por separado que de 1572 pacientes con malaria no complicada, 988 (62.8%) fueron hospitalizados, y que de 251 casos de malaria grave, 250 (99.6%) tuvieron estado de hospitalizacion conocido y de esos 235 (94.0%) lo fueron. El articulo no publica una cifra combinada. El equipo calcula un PROMEDIO PONDERADO POR CASO (no un promedio de los dos porcentajes, que mezclaria denominadores muy distintos sin sentido): suma los hospitalizados y los casos con estado conocido de ambas subpoblaciones -- (988+235)/(1572+250) = 1223/1822 = 0.67124, redondeado 0.6712 -- verificado contra el texto original del articulo (cdc.gov/mmwr/volumes/71/ss/ss7108a1.htm). Es una tasa por caso DIAGNOSTICADO de la vigilancia de EEUU (malaria importada por viajeros, casi siempre sintomatica): a diferencia de dengue/zika aqui no se convierte por infeccion, porque no hay evidencia en la fuente de una fraccion grande de infecciones subclinicas sin diagnosticar que corregir. El calculo combinado es del equipo, no del articulo, y no esta calibrado para Nuevo Leon.",
                    "supuesto": true,
                    "valor": 0.6712
            }
    }'::jsonb
WHERE  code = 'MALARIA_DEMO'
  AND  NOT (default_params ? 'r0');

-- Patogeno X (hipotetico)
UPDATE diseases
SET    default_params = default_params || '{
            "dias_hospitalizacion": {
                    "fuente": "SUPUESTO DEL EQUIPO: Patogeno X es el escenario hipotetico de preparacion de la OMS (\"Disease X\", who.int/teams/blueprint/who-r-and-d-blueprint-for-epidemics) para un patogeno desconocido con potencial epidemico. No es un patogeno real y no hay literatura que citar. El equipo define un escenario de gravedad intermedia-alta para pruebas de preparacion hospitalaria.",
                    "supuesto": true,
                    "valor": 10.0
            },
            "incubacion_dias": {
                    "fuente": "SUPUESTO DEL EQUIPO: ver nota de Patogeno X en dias_hospitalizacion. Valor de referencia, no una medicion.",
                    "supuesto": true,
                    "valor": 5.0
            },
            "infeccioso_dias": {
                    "fuente": "SUPUESTO DEL EQUIPO: ver nota de Patogeno X en dias_hospitalizacion. Valor de referencia, no una medicion.",
                    "supuesto": true,
                    "valor": 6.0
            },
            "letalidad": {
                    "fuente": "SUPUESTO DEL EQUIPO: ver nota de Patogeno X en dias_hospitalizacion. Escenario definido como mas letal que la influenza estacional y menos letal que el SARS-CoV-2 ancestral del catalogo (migracion 017), para representar una amenaza emergente de gravedad intermedia-alta.",
                    "supuesto": true,
                    "valor": 0.02
            },
            "r0": {
                    "fuente": "SUPUESTO DEL EQUIPO: ver nota de Patogeno X en dias_hospitalizacion. Escenario definido como mas transmisible que la influenza estacional del catalogo (migracion 017).",
                    "supuesto": true,
                    "valor": 2.0
            },
            "tasa_hospitalizacion": {
                    "fuente": "SUPUESTO DEL EQUIPO: ver nota de Patogeno X en dias_hospitalizacion. Valor de referencia, no una medicion.",
                    "supuesto": true,
                    "valor": 0.08
            }
    }'::jsonb
WHERE  code = 'PATOGENO_X'
  AND  NOT (default_params ? 'r0');

INSERT INTO schema_migrations (version, description)
VALUES ('023', 'Catalogos: parametros de dengue, zika, malaria y patogeno X con su fuente o supuesto explicito')
ON CONFLICT (version) DO NOTHING;

COMMIT;
