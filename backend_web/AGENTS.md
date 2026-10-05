# AGENTS.md — backend_web

> **Estado: Vigente** · 2026-09-25 · Complementa el `AGENTS.md` de la raíz.

- Para escribir datos, sigue el patrón de `crear_caso` y `crear_enfermedad` en `queries.py`:
  validar, escribir y regresar `(id, error)` con el error en español.
- `query()` nunca hace commit. Para escribir usa `get_conn()` y `conn.commit()`;
  un `INSERT ... RETURNING` hecho con `query()` se pierde sin dar error.
- Parámetros siempre con `%s`. Nunca armes SQL con f-strings ni concatenando datos.
- `db.py` abre una conexión por consulta: usa una sola consulta con `GROUP BY` en lugar de una
  por elemento.

## Escenarios, simulaciones y comparación

- Lo nuevo va en módulos propios (`escenarios.py`, `simulaciones.py`), no en `queries.py`.
- Regresa datos crudos (números, fechas, códigos); el formato para pantalla va en `frontend_web`.
- El puente con el motor vive aquí: leer la versión aprobada, armar la entrada, llamar a
  `from procesamiento.motor import simular` y guardar en `simulation_runs` y `simulation_results`.
- Si importas el motor, agrega `-r ../procesamiento/requerimientos.txt` a `requerimientos.txt`;
  si no, NumPy no se instala en las máquinas de los demás.

## Auditoría

- `backend_web` no importa Flask (lo vigila `test_integridad`). Quién hace la operación y desde
  dónde llega en un `Contexto` (`backend_web/contexto.py`): las rutas lo arman con
  `contexto_de_peticion()` y lo que corre sin petición, como el hilo de una corrida, usa
  `Contexto.sin_peticion(user_id)`. Toda función nueva que audite lo recibe como `contexto=`.
- El CHECK de `audit_log` (migración 003) solo acepta `LOGIN`, `LOGOUT`, `LOGIN_FAILED`,
  `CREATE`, `UPDATE`, `DELETE`, `PUBLISH`, `RUN`, `CANCEL`, `EXPORT`, `SYNC` y
  `PERMISSION_DENIED`. No existen `APPROVE`, `REJECT` ni `SUBMIT`: para aprobar o rechazar
  versiones, pregunta cuál usar.
