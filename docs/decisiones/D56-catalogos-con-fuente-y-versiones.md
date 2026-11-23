# D56 - Catálogos con fuente y versiones: definiciones de caso, incertidumbre, jurisdicciones, población y efectividad

Fecha: 2026-11-23 · Estado: Aceptada · Atiende RF-B13 a RF-B17 · Amplía D5 y D52 · Aplica D37 y la regla 8 de `AGENTS.md`

## Contexto
La retroalimentación pide completar los cinco servicios de catálogos (D7 del checklist;
[`revision_d7.md`](../parciales/parcial-3/revision_d7.md)):
- **`enfermedades`:** «definiciones de caso versionadas, características epidemiológicas,
  clasificación, estado y fuentes de referencia».
- **`parametros`:** «unidades, límites, fuentes, incertidumbre, versionamiento y validaciones
  epidemiológicas».
- **`regiones`:** «países, estados, municipios, áreas sanitarias, geometrías, jerarquías
  geográficas, búsqueda territorial y datos para mapas».
- **`poblacion`:** «versiones, periodos de referencia, distribución demográfica, validación y
  consistencia poblacional».
- **`tipos-intervencion`:** «parámetros permitidos, costos y supuestos de efectividad».

Lo que faltaba en cada uno:
- No había definiciones de caso.
- Los parámetros se sobrescribían, sin intervalo de incertidumbre.
- Las jurisdicciones sanitarias solo estaban en un archivo que lee `zonas`.
- La población se sobrescribía y solo tenía el año 2020, aunque `datos/censo/` trae la serie de
  INEGI de 1990 a 2020.
- La efectividad se capturaba en cada intervención, sin valor de referencia, fuente ni marca de
  supuesto.

## Opciones consideradas
- **Regiones:**
  - A) las jurisdicciones en la base, más la jerarquía y la búsqueda; la geometría se queda en
    `zonas` y el país queda fuera;
  - B) lo mismo, más una fila de país;
  - C) leer el mismo archivo que `zonas`, sin tablas.
- **Población:** A) versiones y la serie de censos 1990-2020; B) solo versiones.
- **Definiciones de caso:** A) sembrar las oficiales de la DGE; B) solo la tabla y las rutas.
- **Valores de efectividad e intervalos:** A) investigar fuentes; B) todo como supuesto.

## Decisión
Las cuatro A, decididas con el líder el 2026-11-23. Van en la 042 y en la 043, que genera
`datos/scripts/build_censos_y_jurisdicciones.py`.

**Definiciones de caso (`case_definitions`, 042):**
- Cada enfermedad tiene versiones de su definición operacional de caso: una lista de criterios
  (clasificación y texto) con su fuente.
- Un borrador se edita. Al publicarlo pasa a vigente y la vigente anterior a retirada. Lo
  publicado no cambia, y hay una sola vigente por enfermedad.
- Las escriben EPIDEMIOLOGO y ADMINISTRADOR. Leer es público, como el catálogo.
- La 042 trae, con el texto literal y sus páginas:
  - **COVID-19 e influenza:** el lineamiento de enfermedad respiratoria viral de la DGE, de
    septiembre de 2023, pp. 30-31.
  - **Influenza, versión 1, ya retirada:** las definiciones operacionales de la DGE de marzo de
    2021, p. 31.
  - **Dengue, paludismo y zika:** el mismo documento de 2021, pp. 60-62 y 66-67.
  - **PATOGENO_X:** es hipotético y no tiene definición.
- La **clasificación** (vía de transmisión y CIE-10) entra en `diseases`, con su fuente: la DGE
  y, para COVID-19, los códigos de emergencia de la OMS.

**Parámetros (`disease_parameter_versions`, 042):**
- Un parámetro puede llevar su **intervalo**: `min` y `max`, que contienen el valor y caben en
  los límites del motor, y su tipo, `IC95`, `RIC` o `rango`. `/parameters/status` lo muestra. El
  motor no lo usa: sirve para leer el resultado y como punto de partida de la calibración (D50).
- Cada cambio guarda la **versión** completa, con su motivo y en la misma transacción.
- La versión 1 son los parámetros de antes del historial. La 2 de COVID-19 e influenza agrega los
  intervalos que ya traían sus fuentes citadas: R0 IC 2.39-3.44, letalidad 0.3-0.9 %,
  incubación 4.5-5.8 días, estancia 4-21 días, R0 de influenza RIC 1.19-1.37 y periodo
  infeccioso 4.31-5.29 días. No se agregó ningún número que no estuviera ya en el texto de la
  fuente.
- Los rangos de los parámetros pasan de `epidemia_comun/validaciones.py` a
  `parametros/reglas.py`. `parametros` deja de importar `backend_web` (E8).

**Regiones (`health_areas` y `health_area_municipalities`, 043):**
- Entran las 8 jurisdicciones sanitarias de NL, del Reglamento Interior de Servicios de Salud
  de NL, art. 27, el mismo archivo que usa `zonas`. Monterrey va en la 1, la 2 y la 3, marcado
  como parcial.
- `regiones` agrega los hijos de una región, las jurisdicciones (todas, una, o las de un
  municipio) y una **búsqueda territorial** sin importar acentos: estado, municipios por nombre o
  clave, y jurisdicciones.
- La geometría y los mapas siguen en `zonas`.
- El **país** queda fuera: el sistema es de Nuevo León, y una fila de México cambiaría los CHECK
  de `regions`.

**Población (`census_population` y `population_versions`, 043):**
- La **serie de censos y conteos de INEGI** de 1990 a 2020: 7 años por 52 regiones.
- Cada ajuste de la población total o de las bandas guarda la **versión** siguiente de la región
  y, si cambió, la del estado, con fuente, periodo de referencia (2020) y motivo. La versión 1, con
  las cifras de antes, se guarda en el primer ajuste.
- Para que la versión quede en la misma transacción que el ajuste, la corrección pasa de
  `backend_web` a `poblacion/datos.py`, con las mismas reglas y mensajes. `poblacion` deja de
  importar `backend_web` (E8); la web ya corregía por el servicio.

**Efectividad (`intervention_effectiveness`, 042):**
- Cada tipo documenta su supuesto de efectividad, general o por enfermedad: valor de referencia,
  rango, fuente y marca de supuesto.
- Los cambian EPIDEMIOLOGO y ADMINISTRADOR (`PUT .../effectiveness`).
- No cambian lo que se simula: cada intervención sigue llevando su propio valor.
- La 042 trae siete:

| Tipo y parámetro | Valor (rango) | Fuente | Supuesto |
|---|---|---|---|
| Cubrebocas, eficacia | 0.85 (0.66-0.93) | Chu et al. 2020, Lancet: aOR 0.15 (0.07-0.34), sobre todo en salud | sí: 1 - aOR, en la comunidad es menor |
| Vacunación contra SARS-CoV-2, eficacia | 0.95 (0.903-0.976) | Polack et al. 2020, NEJM | no |
| Vacunación contra influenza, eficacia | 0.59 (0.51-0.67) | Osterholm et al. 2012, Lancet Infect Dis | no |
| Prueba y aislamiento para SARS-CoV-2, detección | 0.14 (0.10-0.18) | Li et al. 2020, Science: fracción de infecciones reportadas en China | sí |
| Cierre de trabajos, reducción | 0.51 (0.30-0.72) | Movilidad de Google en NL, lugares de trabajo, abril de 2020 | sí: visitas como contactos |
| Reducción de aforo, reducción | 0.30 (0.18-0.54) | Movilidad de Google en NL, comercio y recreación, agosto a octubre de 2020 | sí |
| Cierre de escuelas, reducción | 1.0 | Por definición: un cierre total quita la capa escuela | sí |

**Lo de una enfermedad se va con ella.** Las definiciones, las versiones de parámetros y los
supuestos por enfermedad se borran en cascada con su enfermedad. El sistema solo la da de baja
lógica, así que esto solo ocurre en las pruebas. Lo demás no se borra (D52).

## Consecuencias
- RF-B13 a RF-B17 quedan hechos del lado del servidor.
  - **A** (escritorio) puede mostrar las definiciones de caso, los intervalos y las versiones de
    los parámetros, los supuestos de efectividad al configurar una intervención y la población por
    periodo.
  - **B** (móvil) puede leer la definición de caso vigente.
- `poblacion` y `tipos-intervencion` parten de `epidemia/base-vigilancia`. `parametros` ya no
  importa `backend_web`, pero sigue en `epidemia/base` porque usa los límites del motor.
- **Para F:** `zonas` puede leer las jurisdicciones de la base en lugar del archivo. Los datos son
  los mismos, del mismo script.
- **Pendiente:** confirmar con la Secretaría de Salud de NL que la división en jurisdicciones siga
  vigente; ya lo decía el archivo de `zonas`.
- **Fuera:** los sexos de la población (el censo trae solo los de 60 y más), las unidades y la
  plausibilidad entre parámetros en `validacion`, y la compatibilidad entre versiones del XML de
  `escenarios-xml` (`revision_d7.md`).

Depende de: D5, D37, D50, D52

## Fuentes
- Secretaría de Salud, DGE. Lineamiento estandarizado para la vigilancia epidemiológica y por
  laboratorio de la enfermedad respiratoria viral, septiembre de 2023:
  https://www.gob.mx/cms/uploads/attachment/file/636504/Lineamiento_Estandarizado_Para_La_Vigilancia_Epidemiol_gica_Y_Por_Laboratorio_De_La_Enfermedad_Respiratoria_Viral_-_Septiembre_2023.pdf
- Secretaría de Salud, DGE. Definiciones operacionales de enfermedades sujetas a vigilancia
  convencional, marzo de 2021:
  https://epidemiologia.salud.gob.mx/gobmx/salud/documentos/manuales/DefinicionesOperacionales_Padecimientos_Sujetos_a_VE.pdf
- OMS, códigos CIE-10 de emergencia para COVID-19:
  https://www.who.int/standards/classifications/frequently-asked-questions/covid-19-emergency-icd-codes
- Chu et al. 2020, doi:10.1016/S0140-6736(20)31142-9; Polack et al. 2020, doi:10.1056/NEJMoa2034577;
  Osterholm et al. 2012, doi:10.1016/S1473-3099(11)70295-X; Li et al. 2020, doi:10.1126/science.abb3221.
- Google, Informes de Movilidad Comunitaria COVID-19 (archivo de 2020 de México):
  https://www.google.com/covid19/mobility/
- INEGI, Censos y Conteos de Población y Vivienda 1990-2020 (`datos/censo/`), y el Reglamento
  Interior de Servicios de Salud de NL, art. 27 (`datos/geo/nl_jurisdicciones_sanitarias.json`).
