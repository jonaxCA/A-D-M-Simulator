# AGENTS.md — procesamiento

> **Estado: Vigente** · 2026-09-25 · Complementa el `AGENTS.md` de la raíz.

El formato de entrada del motor está en el docstring de `motor/parametros.py`. Lo que entra y
sale de cualquier motor (`seir-ref`, `abm-ref`, `abm-gpu`) está en `contrato.py` y en
`docs/contratos/motor/README.md`; `tests/test_contrato_motor.py` revisa que cada motor lo cumpla.

- `abm/` es `abm-ref`, el modelo basado en agentes (D22). Valida la entrada con el `resolver`
  del motor y repite sus transiciones; solo cambia el contagio, por hogar, salón, centro de
  trabajo y comunidad. Sus supuestos (tamaños de los grupos) van en la trazabilidad de la
  salida, y `tests/test_abm.py` revisa que con un solo grupo por capa dé lo mismo que el SEIR.
- La comparación por costo e impacto (Pareto) vive en `analitica/`, fuera de los motores. Solo
  importa nombres públicos de `procesamiento.motor` y la lectura de valores con fuente de
  `trazabilidad.py`; nunca un nombre con guion bajo.

- Se importa siempre como `procesamiento.motor`, también en `tests/` y en los
  microservicios. `import motor` carga una segunda copia con otras clases de excepción;
  `backend_web/tests/test_integridad.py` lo revisa.
- Todo se corre desde la raíz: `python -m pytest procesamiento/tests` y
  `python -m procesamiento.motor`.

- No renombres los campos de la salida (`resumen`, `serie`, …). Las columnas generadas de
  `simulation_results` (migración 014) leen esos nombres: un cambio no da error, deja
  columnas vacías.
- Si un cambio altera los números, sube `ENGINE_VERSION` en `motor/modelo.py`.
- Todo el azar sale de `np.random.default_rng(semilla)`.
- Toda simplificación nueva del modelo se agrega a la lista `simplificaciones` de la salida.
- Cada cambio agrega o ajusta pruebas en `tests/`.
