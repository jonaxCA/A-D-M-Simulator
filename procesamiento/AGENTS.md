# AGENTS.md — procesamiento

> **Estado: Vigente** · 2026-09-25 · Complementa el `AGENTS.md` de la raíz.

El formato de entrada del motor está en el docstring de `motor/parametros.py`.

- No renombres los campos de la salida (`resumen`, `serie`, …). Las columnas generadas de
  `simulation_results` (migración 014) leen esos nombres: un cambio no da error, deja
  columnas vacías.
- Si un cambio altera los números, sube `ENGINE_VERSION` en `motor/modelo.py`.
- Todo el azar sale de `np.random.default_rng(semilla)`.
- Toda simplificación nueva del modelo se agrega a la lista `simplificaciones` de la salida.
- Cada cambio agrega o ajusta pruebas en `tests/`.
