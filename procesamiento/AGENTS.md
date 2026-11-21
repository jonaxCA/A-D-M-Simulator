# AGENTS.md — procesamiento

> **Estado: Vigente** · 2026-09-25 · Complementa el `AGENTS.md` de la raíz.

El formato de entrada del motor está en el docstring de `motor/parametros.py`. Lo que entra y
sale de cualquier motor (`seir-ref`, `abm-ref`, `abm-gpu`) está en `contrato.py` y en
`docs/contratos/motor/README.md`; `tests/test_contrato_motor.py` revisa que cada motor lo cumpla.

- `motores.py` es el registro de los motores implementados: el simulador, `corridas` y
  `resultados` lo usan para saber qué motor correr, qué versión registrar y qué
  simplificaciones mostrar. Un motor nuevo se agrega ahí.
- `abm/` es `abm-ref`, el modelo basado en agentes (D22). Valida la entrada con el `resolver`
  del motor y repite sus transiciones; solo cambia el contagio, por hogar, salón, centro de
  trabajo y comunidad. Sus supuestos (tamaños de los grupos) van en la trazabilidad de la
  salida, y `tests/test_abm.py` revisa que con un solo grupo por capa dé lo mismo que el SEIR.
- `abm_gpu/` es `abm-gpu`, el mismo modelo en FLAME GPU 2 (D23). Arma la población con el
  código de `abm/` y corre los días en la GPU (`agentes.cu`). Solo corre con `pyflamegpu` y una
  GPU de NVIDIA (`abm_gpu/README.md`); sin ellos sus pruebas se saltan. Un cambio a las
  fórmulas de `abm/` se hace también en `abm_gpu/agentes.cu`, y `tests/test_abm_gpu.py`
  revisa que sigan dando lo mismo.
- `entrada_motor.py` traduce una versión de escenario (filas de la base) a la entrada del motor y
  decide si es simulable (parámetros con fuente o supuesto, versión aprobada). Es la regla que
  comparten `simulador` y `pareto` sin importar `backend_web` (E8, D37); no toca la base: cada
  servicio lee sus filas.
- `analitica/escala.py` calcula el factor de escala de D6 (habitantes del censo / agentes) y
  lleva los conteos del resumen a habitantes. El motor nunca lo ve.
- La comparación por costo e impacto (Pareto) vive en `analitica/`, fuera de los motores. Solo
  importa nombres públicos de `procesamiento.motor` y la lectura de valores con fuente de
  `trazabilidad.py`; nunca un nombre con guion bajo.

- Se importa siempre como `procesamiento.motor`, también en `tests/` y en los
  microservicios. `import motor` carga una segunda copia con otras clases de excepción;
  `backend_web/tests/test_integridad.py` lo revisa.
- Todo se corre desde la raíz: `python -m pytest procesamiento/tests` y
  `python -m procesamiento.motor`.
- `mediciones.py` saca las tablas de tiempos y de validación de la ficha del simulador
  (`docs/arquitectura/ficha_simulador.md`): `python -m procesamiento.mediciones tiempos` y
  `... validacion`. Si un cambio mueve los números del ABM, se vuelven a correr y se
  actualiza la ficha.

- No renombres los campos de la salida (`resumen`, `serie`, …). Las columnas generadas de
  `simulation_runs` (migración 038) leen los del resumen, y `series_corridas` en MongoDB guarda
  los de la serie (`CAMPOS_SERIE`): un cambio no da error, deja columnas o campos vacíos.
- Si un cambio altera los números, sube `ENGINE_VERSION` en `motor/modelo.py`.
- Todo el azar sale de `np.random.default_rng(semilla)`.
- Toda simplificación nueva del modelo se agrega a la lista `simplificaciones` de la salida.
- Cada cambio agrega o ajusta pruebas en `tests/`.
