# D50 - Calibración de `seir-ref` contra una serie pública agregada, en el servicio `calibracion`

Fecha: 2026-11-22 · Estado: Aceptada · Reemplaza D24 · Enmienda D39 (supuestos de una predicción) y D46 (la ruta de calibración pasa a `calibracion`) · Reabre RF-C16, RF-E17, RF-F13, RF-F14 y RNF-L28 · Cambia RNF-I01, RNF-I04 y RNF-I15

## Contexto
- La retroalimentación pide calibrar y validar contra observaciones. Pide «ajustar parámetros a datos históricos, registrar métodos de calibración, funciones de pérdida, versiones y métricas de ajuste» (`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`, l. 129 y 131, como sugerencia de servicio). Para el escritorio pide «ajustar parámetros con series históricas y comparar los resultados de ajuste» (l. 189). Cita a los CDC: la utilidad de un modelo depende de su validación contra observaciones (l. 139).
- El equipo hizo obligatoria la calibración y dejó la fuente de datos por investigar (checklist l. 27). D24 la había dejado fuera porque no había serie ni fuente, y está reabierta.
- Hoy los modelos están *verificados*, no validados: tamaño final, casos límite, sensibilidad y reproducibilidad (ficha §13 a §15). Toda corrida es `exploratoria` (D39; `procesamiento/estado_validacion.json` tiene `calibrado: []` en las tres versiones).
- **Conflicto de datos:**
  - RNF-I01 dice que el proyecto «no opera con datos reales», y RNF-I15, que los datos de la demostración son sintéticos.
  - El contexto §2.9 propone una ola histórica con datos abiertos (no es vinculante).
  - D39 exige una serie observada para subir de `exploratoria`, y datos no usados al calibrar para `validada`.
  - El comentario de `cases` en la 008 (l. 175) dice que los casos «alimentan la recalibración», y esos casos son sintéticos (RNF-I15).
- **D39 bloquea cualquier predicción tal como está:**
  - Una corrida con un parámetro `supuesto` nunca pasa de exploratoria (`procesamiento/categoria.py`, l. 29 a 35).
  - `capas_contacto` siempre llega como supuesto, porque `procesamiento/entrada_motor.py` no lo pasa y el motor pone `CAPAS_CONTACTO_SUPUESTO` (`procesamiento/motor/parametros.py`, l. 54 y 345 a 349).
  - En COVID son supuesto `infeccioso_dias` y `dias_hospitalizacion` (migración 017, l. 79 a 94) y `letalidad_por_edad` (020).
- **Costo por motor** (ficha §12): una corrida de `seir-ref` tarda 0.02 s con cualquier población; `abm-ref` tarda 13.6 s con un millón de agentes, y `abm-gpu`, 1.2 s.
- `seir-ref` corre un R0 ~10 % mayor que el nominal con D = 5 (ficha §11). Con la misma fórmula y el D = 9 de COVID, es ~6 % mayor.
- D46 dejó en `pareto` una ruta que solo lee el estado de calibración. Dice que, si calibrar exige datos o ejecuciones largas, debe pasar a un servicio propio.
- En una revisión de 84 estudios de calibración de modelos basados en individuos, solo el 17 % justificó su método, el 37 % reportó validación y cerca de un tercio estimó la incertidumbre de los parámetros (Hazelbag et al. 2020). D50 cubre las tres cosas.

## Opciones consideradas
- **Datos:** A) una serie pública agregada (casos de COVID-19 en Nuevo León de los datos abiertos de la DGE); B) solo una serie sintética que genera el motor; C) los casos de `cases`.
- **Método:** A) ABC por rechazo sobre hipercubo latino; B) Nelder-Mead; C) rejilla; D) ABC-SMC, MCMC o filtros de partículas.
- **Función de pérdida:** A) error cuadrático en conteos semanales; B) error cuadrático en log(1 + conteo) semanal; C) verosimilitud de Poisson o binomial negativa.
- **Calibración contra validación:** A) se retienen las últimas semanas de la misma serie; B) se valida con otra región; C) se valida con la misma serie con que se calibró.
- **Dónde corre:** A) un comando fuera de línea; B) un servicio nuevo asíncrono; C) un trabajo asíncrono dentro de `pareto`.
- **Supuestos frente a D39:** A) se admite la configuración con que se calibró; B) D39 se queda como está.
- **Modelos:** A) solo `seir-ref`; B) también `abm-gpu`; C) los tres.
- **Permisos:** A) un permiso nuevo, `calibrations.run`; B) reusar `simulations.run`.
- **La serie en la base:** A) una migración generada por un script; B) esperar el importador de D6.

## Decisión
Datos A, método A, pérdida B, separación A, servicio B, supuestos A, modelos A, permisos A y serie A.

**Datos: qué serie se admite.**
- **Se admite** una serie *pública y agregada* que cumpla todo esto:
  - la publica una autoridad bajo una licencia de libre uso;
  - son conteos por periodo y región, sin registros por persona;
  - tiene un corte fijo, identificado por su fecha y su SHA-256.
- **No se admite** nada por persona. El archivo de registros de la DGE se procesa en local con un script de `datos/scripts/`, y solo entra el agregado: ni el archivo crudo ni sus registros llegan al repo ni a la base (RNF-I05).
- **`cases` nunca calibra:** en la demostración son sintéticos (RNF-I15). Por eso la opción C queda descartada.
- **La serie:** casos confirmados de COVID-19 en Nuevo León por fecha de inicio de síntomas, agregados por semana, de la ola de 2020.
  - Sale de los datos abiertos de la Dirección General de Epidemiología: la base de casos, que se publica desde abril de 2020, con su diccionario y sus cierres anuales (DGE).
  - Los campos son `ENTIDAD_RES`, `FECHA_SINTOMAS` y `CLASIFICACION_FINAL`. Se citan de copias de 2020 y 2021 del diccionario; se confirman con el diccionario vigente.
  - Se publican conforme al decreto de datos abiertos del DOF del 20 de febrero de 2015 (DGE, aviso de históricos). Los términos de Libre Uso MX piden citar la fuente; la redacción vigente se confirma en datos.gob.mx (ítem de la l. 225).
  - Es el brote para el que está el catálogo: `SARS_COV_2_ANCESTRAL`, «parámetros iniciales de literatura para la primera ola. Pendiente de calibración» (010, l. 110 a 115).
  - La población entera era susceptible y no había vacunas, que es lo que supone el SEIR.
- **La ventana** va de la primera semana con casos a la semana anterior al inicio de la segunda ola. Las fechas exactas, el corte y la huella los fija el ítem de la l. 225 del checklist, y se anotan en la ficha y en la migración 061.
- **La opción B se usa solo como prueba.** Una serie sintética, con parámetros conocidos y ruido de observación, revisa que el algoritmo los recupere (`procesamiento/tests/test_calibracion.py`). Una serie así no es observada, así que no sube ninguna categoría.
- **Requisitos.** Se enmiendan RNF-I01 y RNF-I04: el proyecto no opera con datos *de pacientes*. RNF-I15 agrega: «la única excepción son series públicas agregadas con licencia, solo para calibrar y validar (D50)».

**Qué se calibra.** Tres parámetros; el resto queda fijo con su fuente o su marca.
- `r0`, de 1.0 a 5.0. El rango contiene el IC 2.39–3.44 de Billah et al. 2020 (017) con holgura. Es el R0 *nominal* de `seir-ref-0.1`, así que absorbe el sesgo de la §11.
- `ρ`, la fracción de contagios que se reporta, de 0.01 a 1.0. No hay fuente local del subregistro, así que se usa casi todo el rango.
- `φ`, la reducción de contactos de la Jornada Nacional de Sana Distancia, de 0 a 1.
- Los tres rangos son supuestos del análisis (regla 8), como los valores de la sensibilidad de D46.

**Configuración fija con que se calibra:**
- Los parámetros de COVID del catálogo (017 y 020), con sus supuestos.
- La población de Nuevo León por grupo de edad del Censo 2020 (021): factor 1 (D6).
- `capas_contacto`, el supuesto del motor.
- `infectados_iniciales` = max(1, round(c₀ / ρ)), donde c₀ son los casos de la primera semana de la ventana. Es supuesto del método.
- El paquete de la Jornada, con los tipos de intervención que ya existen:
  - `CIERRE_ESCUELAS` desde el 23-03-2020, con reducción y cumplimiento de 1. Fuente: Acuerdo SEP 02/03/20, DOF del 16-03-2020, ampliado al 30-05-2020.
  - `CIERRE_TRABAJO` desde el 30-03-2020, con reducción φ. Fuente: acuerdo de Salud, DOF del 21-04-2020, que suspende las actividades no esenciales del 30 de marzo al 30 de mayo.
  - `REDUCCION_AFORO` desde el 23-03-2020, con reducción φ.
  - Las tres van sin fin. Es supuesto: el cambio de conducta persiste durante la ventana.

**Modelo de observación.**
- `nuevos_casos` son contagios (S → E; `procesamiento/motor/modelo.py`, l. 190), y la serie va por inicio de síntomas.
- El caso simulado de la semana *w* es *s_w* = ρ · (los contagios de la semana *w*, desplazados 5 días). Los 5 días son la mediana de incubación de Lauer et al. 2020 (017).
- ρ y el desplazamiento viven en `procesamiento/calibracion/`, nunca en el motor.

**Método: ABC por rechazo** (Toni et al. 2009 lo presentan como base del ABC-SMC).
- 5 000 combinaciones de (r0, ρ, φ) por hipercubo latino (McKay et al. 1979), con una semilla del muestreo que queda registrada.
- Cada combinación corre con las semillas 1 a 3, las mismas para todas (como en D8), y su distancia es la pérdida media.
- Se aceptan las 50 de menor distancia (1 %). De cada parámetro se reportan la mediana y el intervalo p5–p95 de las aceptadas: es la incertidumbre que D39 pide.
- Las 50 aceptadas, con sus 3 semillas, dan 150 trayectorias: la banda predictiva.
- Muestras, semillas y cuantil son elecciones del método, y se pueden pedir dentro de topes (hasta 10 000 muestras).
- Costo: unas 15 000 corridas de `seir-ref`, del orden de minutos según la §12. Usa solo NumPy (`procesamiento/requerimientos.txt`).
- Se descartan:
  - Nelder-Mead: da un solo punto, sin intervalo, y la pérdida de un modelo estocástico es ruidosa; además pide SciPy.
  - La rejilla: crece demasiado con tres parámetros.
  - ABC-SMC, MCMC y filtros de partículas: son más eficientes, pero no caben en el parcial.

**Función de pérdida:** L = Σ_w (log(1 + o_w) − log(1 + s_w))², sobre las semanas de la ventana de calibración.
- El logaritmo pesa igual el crecimiento y el pico. Sin él, las semanas del pico deciden todo el ajuste.
- La semana quita el efecto del día de la semana en el reporte.

**Métricas de ajuste:** se calculan por separado en la ventana de calibración y en la de validación, con *s_w* igual a la mediana de la banda predictiva.
- **RMSE** = √(media de (o_w − s_w)²) y **R²** = 1 − Σ(o_w − s_w)² / Σ(o_w − ō)², en conteos. Son las que pide RF-F14.
- **Cobertura:** la fracción de semanas con *o_w* dentro de la banda p5–p95. Se evalúa la calibración de la banda aparte de su ancho y su sesgo, como en Funk et al. 2019.

**Calibración contra validación:**
- Las primeras ⅔ de las semanas calibran; el último ⅓ nunca entra a la pérdida y valida. Es lo que D39 llama «datos que no se usaron para calibrar».
- Se descarta otra región (B) porque D39 valida por enfermedad *y* región. La opción C no valida nada.
- La tolerancia para `validada` se escribe en la ficha **antes** de correr la validación. Propuesta: cobertura de al menos 80 % en las semanas de validación. La banda es un intervalo del 90 %; el margen es criterio del equipo y va marcado como supuesto.

**Versiones y reproducibilidad.** Cada calibración guarda lo necesario para repetirla bit a bit (ficha §15):
- `method` = `abc-rechazo` y `method_version` = `calibracion-0.1`;
- `engine_version`, el conjunto de datos con su versión y su huella;
- los rangos, la semilla del muestreo, las semillas de las corridas, el cuantil y las dos ventanas.
- Una calibración solo vale para su `engine_version`: si se corrige el R0 efectivo (§11), sube la versión y se calibra otra vez.

**Dónde corre: el servicio `calibracion`** (n.º 30 del catálogo, puerto 5246, el siguiente del dominio de simulación, perfil `simulacion`).
- La lógica es una función pura en `procesamiento/calibracion/` (regla 2): recibe la serie y la configuración y regresa diccionarios. La importa el servicio, como `simulador` y `validacion` importan `procesamiento` (excepción de D37).
- `calibracion` (la API) registra la calibración como `encolado` y la mete en `queue:calibraciones` de Redis.
- `calibracion-trabajador`, la misma imagen con otro modo como las variantes de `simulador`, la corre y guarda el resultado de una vez al terminar, con su avance en Redis.
- La base manda sobre Redis (D19). Al arrancar, el trabajador reencola sus `ejecutando` hasta 3 intentos (D38). Con las mismas semillas el resultado es el mismo, así que nada se duplica.
- Estados de la regla 7: `encolado`, `ejecutando`, `completado`, `fallido` y `cancelado`.
- Solo `seir-ref` por ahora. Otro motor da 422.
- Se descarta la opción A porque no deja lanzar ni monitorear desde el escritorio (RF-E17 y retroalimentación l. 189), y la C por D46.

**Rutas** (D11), en XML por defecto con su XSD (D9, D15), para el escritorio, que solo habla XML (`frontend_desktop/AGENTS.md`):

| Ruta | Qué hace | Permiso |
|---|---|---|
| `POST /api/v1/calibrations` | Encola una calibración (enfermedad, región, conjunto de datos, motor, muestras); regresa 202 | `calibrations.run` |
| `GET /api/v1/calibrations`, `GET /api/v1/calibrations/{id}` | Lista y detalle: estado, avance, configuración, parámetros con intervalo, pérdida, métricas y versiones | `simulations.read` |
| `POST /api/v1/calibrations/{id}/cancel` | `encolado` o `ejecutando` → `cancelado` | `calibrations.run` |
| `GET /api/v1/calibrations/{id}/fit` | Por semana: observado, mediana y p5–p95 simulados, y la ventana a la que pertenece; RMSE, R² y cobertura (RF-F13, RF-F14) | `simulations.read` |
| `GET /api/v1/calibrations/{id}/scenario` | La configuración calibrada como entrada de una versión. El escritorio la crea, y pasa por revisión y aprobación (D4, D5) | `simulations.read` |
| `GET /api/v1/calibrations/evaluate` | Síncrona: un juego de (r0, ρ, φ) con las semillas 1 a 5, sin escribir nada (como la sensibilidad de D46). Es «ajustar y comparar» del escritorio | `simulations.read` |
| `GET /api/v1/calibrations/state` | Lo que hoy da `GET /api/v1/pareto/calibration`: el estado de cada `engine_version` | `simulations.read` |

- Pueden consultar los roles que hoy consultan `pareto`, incluidos INVESTIGADOR y AUTORIDAD_SANITARIA (D42), con el alcance por región de D43. CAPTURISTA recibe 403.
- Lanzar y cancelar se registran con `log_audit()` (regla 4) y tienen el límite de consumo de las corridas (D31).
- **Nadie declara un modelo calibrado desde una ruta.** Subir a `calibrado` o `validado` en `estado_validacion.json` sigue siendo un PR revisado, con la calibración y su evidencia en la ficha (D39).

**Permisos.**
- `calibrations.run` es nuevo, para EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR. Calibrar es una decisión científica, y el EPIDEMIOLOGO no tiene `simulations.run` (010).
- La consulta usa `simulations.read`.

**Migraciones** (reservadas para el bloque 0):
- **061:** `observed_datasets` y `observed_points`.
  - `observed_datasets` guarda la enfermedad, la región, la métrica, el periodo, la fuente, la licencia, la URL, la fecha del corte, el SHA-256 y la versión.
  - `observed_points` guarda el conjunto, el inicio del periodo y el valor.
  - Lleva los datos de la serie. Los genera un script de `datos/scripts/` desde el CSV agregado de `datos/observados/`, como el censo (015 y 021; D7).
  - Cuando exista el importador de D6 (RF-B08), escribe en las mismas tablas.
- **062:** `calibrations`, con la configuración, el estado, `attempts`, el avance, el resultado en JSONB, el error, quién la pidió y las fechas.
  - Agrega el permiso `calibrations.run` y sus asignaciones, el rol `svc_calibracion` (D18) y el tipo de bitácora.
- **063:** un `COMMENT ON TABLE cases` nuevo: «Casos capturados en campo desde la app móvil. En la demostración son sintéticos (RNF-I15) y no se usan para calibrar (D50).» La 008 no se edita (D7).

**Categoría: se enmienda D39 (supuestos A).**
- Cada entrada de `calibrado` en `estado_validacion.json` agrega `calibracion` (el id) y `huella_configuracion`. La huella es el SHA-256 de lo que la calibración dejó fijo o estimó: los parámetros de la enfermedad, `capas_contacto`, la población y los infectados iniciales.
- Una corrida es `prediccion` si su `engine_version`, su enfermedad y su región están calibradas y su configuración tiene esa huella. Los supuestos *dentro* de esa configuración se admiten, porque el ajuste se evaluó con ellos, y `motivo` los lista. Cualquier otro supuesto la deja `exploratoria`.
- Las intervenciones pueden cambiar: son el escenario que se estudia. `motivo` dice que las que no están en la calibración son hipotéticas.
- «Empieza en el estado observado» (D39) se cumple así: la versión arranca el día 0 de la ventana con los infectados iniciales que salen de la serie. Empezar a mitad de un brote pediría un estado inicial completo en el contrato del motor, y queda fuera.
- La banda de una corrida (D8, `/band`) solo tiene el ruido entre semillas. La incertidumbre de los parámetros está en `/fit` de la calibración, y la pantalla lo dice.

**Modelos: solo `seir-ref`.** Calibrar con 15 000 corridas tardaría unas 57 h en `abm-ref` con un millón de agentes, o unas 5 h en `abm-gpu` en la PC con GPU (§12 y D23). `abm-ref` y `abm-gpu` siguen exploratorios.

**Fuera:**
- Calibrar los ABM y el ABC-SMC.
- Recalibrar con datos de campo (contexto §2.9, último párrafo): choca con RNF-I15.
- Mostrar la serie real en la web (RF-G14): la calibración vive en el escritorio (D4).
- RN-25 sigue fuera, pero cambia su motivo: un caso nunca es histórico, porque la serie histórica no está en `cases`.

## Consecuencias
- La calibración es obligatoria y verificable: el método está justificado, tiene validación aparte e incertidumbre de parámetros.
- Una corrida puede llegar a `prediccion` sin dar fuente a todos los supuestos de COVID, pero solo con la configuración calibrada.
- **Implica cambios en otros lados:**
  - D24 pasa a «Reemplazada por D50».
  - D39 cambia la regla de supuestos y el formato de `estado_validacion.json` (`procesamiento/categoria.py` y `procesamiento/tests/test_categoria.py`).
  - D46: `pareto` conserva `/pareto/calibration` hasta que el escritorio use `/calibrations/state`, y entonces se retira.
- **Requisitos:**
  - Se reabren RF-C16 (cargar la serie; aquí por migración), RF-E17 (barrido: `POST /calibrations`), RF-F13 (encimar: `/fit`), RF-F14 (RMSE y R²) y RNF-L28.
  - Se reescriben RNF-I01, RNF-I04 y RNF-I15.
- **Documentos que se actualizan:**
  - AGENTS.md de la raíz: l. 33 y la viñeta del motor (checklist l. 242).
  - El catálogo (fila 30; los «29 servicios» pasan a 30, aquí y en `microservicios/AGENTS.md`).
  - La ficha (§1, §11, §16, §17 y una sección nueva de calibración con su tolerancia) y `brechas_v3.md` (A6).
  - `arquitectura_v3.md` (l. 39, 197 y 376), el README de migraciones (061 a 063) y el checklist (l. 213, 218, 225, 229, 316 y 499).
- **Trabajo nuevo:**
  - Bloque E (E7): el algoritmo en `procesamiento/calibracion/` con su prueba sintética, la migración 062, el servicio, su contrato en `docs/contratos/calibracion/` (OpenAPI, XSD y ejemplos) y su contenedor en `infra/docker-compose.yml`.
  - Bloque A (A4): el módulo de calibración del escritorio.
  - Bloque D (D6): bajar la serie y su script, las migraciones 061 y 063, y el importador de series.
  - Al aceptarse, esto era del bloque 0; el 2026-11-22 pasó a E y D.
- **Riesgos:**
  - r0 y φ se confunden entre sí. El intervalo de las aceptadas lo muestra, y por eso la banda usa las combinaciones aceptadas, no los márgenes.
  - El paquete de la Jornada es una simplificación. Si la cobertura de validación no llega a la tolerancia, el modelo queda `prediccion`, no `validada`, y así se presenta.
- Si el equipo corrige el R0 efectivo (§11), conviene hacerlo antes de la calibración final, porque cambia `engine_version`.

Depende de: D22, D37, D39, D46

## Fuentes
**Del repositorio:**
- `docs/parciales/parcial-3/RETROALIMENTACION_SEGUNDO_PARCIAL.txt` (l. 5, 129, 131, 139 y 189).
- `docs/parciales/parcial-3/checklist.md` (l. 27, 100, 213, 218, 225, 229, 242, 316, 499 y 589).
- D4, D5, D6, D7, D8, D18, D19, D22, D23, D24, D31, D37, D38, D39, D42, D43 y D46.
- `docs/arquitectura/ficha_simulador.md` (§11 a §17) y `procesamiento/estado_validacion.json`.
- `procesamiento/categoria.py`, `procesamiento/entrada_motor.py`, `procesamiento/motor/parametros.py`, `procesamiento/motor/modelo.py` y `procesamiento/requerimientos.txt`.
- Migraciones 008 (l. 175), 010 (l. 110 a 115), 017, 020 y 021.
- Requisitos: RNF-I01, I04, I05 e I15; RNF-L25 y L28; RF-C16, RF-E17, RF-F12 a F14 y RF-G14; RN-25.
- `microservicios/pareto/rutas.py` y `docs/contratos/pareto/`.

**Externas:**
- DGE, Datos Abiertos: https://www.gob.mx/salud/documentos/datos-abiertos-152127
- DGE, aviso de datos abiertos históricos (decreto del DOF del 20-02-2015): https://www.gob.mx/cms/uploads/attachment/file/914274/datos_abiertos_historicos_2024.pdf
- Libre Uso MX (fuente secundaria; se confirma en datos.gob.mx): https://wiki.openstreetmap.org/wiki/ES:LIBRE_USO_MX
- Acuerdo SEP 02/03/20, DOF del 16-03-2020: https://www.dof.gob.mx/nota_detalle.php?codigo=5589479&fecha=16/03/2020. Ampliación al 30-05-2020: https://www.gob.mx/cms/uploads/attachment/file/550263/ACUERDO_SEP_ampl_a_suspensi_n_al_30_de_mayo.pdf
- Acuerdo de Salud, DOF del 21-04-2020 (actividades no esenciales del 30-03 al 30-05): https://www.gob.mx/cms/uploads/attachment/file/548829/01_ACUERDO_por_el_que_se_modifica_el_similar_por_el_que_se_establecen_acciones_extraordinari.pdf
- Toni T. et al. 2009, J R Soc Interface 6(31):187-202. doi:10.1098/rsif.2008.0172
- McKay M.D., Beckman R.J., Conover W.J. 1979, Technometrics 21(2):239-245.
- Hazelbag C.M. et al. 2020, PLoS Comput Biol 16(5):e1007893. doi:10.1371/journal.pcbi.1007893
- Funk S. et al. 2019, PLoS Comput Biol 15(2):e1006785. doi:10.1371/journal.pcbi.1006785
- Billah et al. 2020 y Lauer et al. 2020, como los cita la migración 017.
