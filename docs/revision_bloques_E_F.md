# Revisión de los bloques E y F

> Rama `bloque-e-f`, commit `6d2cadb` · 2026-09-26

## Cómo se revisó

- Lectura de `procesamiento/motor/`, `backend_web/simulaciones.py`, las consultas de corridas
  en `backend_web/queries.py`, las rutas y plantillas de simulaciones y las migraciones 014,
  017, 020, 023, 024 y 025.
- Resultados:
  - Pruebas del motor: 66 OK.
  - `backend_web/tests`: 119 OK (1 omitida).
  - `frontend_web/tests`: 39 OK.
  - `python -m motor` corre, y `verifica_migraciones.py` no marca diferencias.
- Las pruebas de integración se corrieron en una base temporal instalada desde cero (001–025).
  En esa base se reprodujeron los hallazgos 1, 2 y 5. Cómo repetirlo: ver
  [Instrucciones para un agente](#instrucciones-para-un-agente).

## Bloque E — Motor

| #   | Casilla                                          | Veredicto |
|-----|--------------------------------------------------|-----------|
| E1  | Módulo aislado sin Flask                         | ✅ Solo usa `numpy` y la biblioteca estándar |
| E2  | Compartimentos S, E, I, R, H, D (+V)             | ✅ |
| E3  | Estocástico con semilla                          | ✅ Tiene prueba |
| E4  | `ENGINE_VERSION = "python-ref-0.1"`              | ✅ |
| E5  | Los 6 tipos de intervención                      | ✅ Los parámetros coinciden con el `param_schema` de la 010 |
| E6  | Vacunación por edad, cobertura y dosis diarias   | ✅ Tiene prueba |
| E7  | Simplificaciones en la salida                    | ✅ Pero no se guardan ni se muestran (hallazgo 4) |
| E8  | Pruebas unitarias                                | ✅ El caso «sin vs con intervención» lo cubren las pruebas de cierre escolar y de vacunación |
| E9  | Indicadores resumen                              | ✅ |
| E10 | `python -m motor` con el Censo 2020              | ✅ Suma 5,766,310 y el grupo 60+ da 654,050. El docstring está desactualizado: habla del tope de 5 M y de la ruta `data/censo/` |
| E11 | COVID-19 e influenza                             | ✅ Los seis parámetros tienen fuente o supuesto |
| E12 | Dengue, zika y malaria                           | ⚠️ **Parcial** (hallazgo 3) |
| E13 | Supuesto de transmisión directa en `SIMPLIFICACIONES` | ✅ Tiene prueba |
| E14 | Patógeno X                                       | ✅ Los seis parámetros van como supuesto |

## Bloque F — Ejecución, estados y resultados

| #       | Casilla                                              | Veredicto |
|---------|------------------------------------------------------|-----------|
| F1–F2   | 014: `python-ref`, 1 réplica, `requested_by` con relleno | ✅ |
| F3      | Cada corrida guarda sus datos                        | ✅ En la base. ⚠️ La trazabilidad no se muestra: `get_run()` no la trae y la plantilla tampoco la pinta |
| F4      | `SIM-00042` / `ESC-003`                              | ✅ |
| F5      | Ejecutar solo versiones aprobadas                    | ✅ Lo revisan la plantilla, `crear_corrida()`, el trigger y `construir_escenario_desde_version()`. `roles_required` revisa el rol, no el estado |
| F6–F10  | Estados, hilo, *polling* y forzar error (solo ADMIN) | ✅ Pruebas de integración OK |
| F11–F13 | `simulation_results`, indicadores y curvas en Highcharts | ✅ |
| F14     | Reproducibilidad con la misma semilla                | ✅ Pruebas OK (compara la huella y el resumen) |
| F15     | Auditoría de encolado, ejecutando, completado y fallido | ✅ |

## Hallazgos

1. **(Alta) La corrida no simula la versión que se revisó.** El bloque D valida con
   `queries.escenario_para_motor()`, pero F arma la entrada con
   `simulaciones.construir_escenario_desde_version()`, que es otra traducción.
   `get_version_simulacion()` ni siquiera lee `population_by_age`, `population_age_unknown`,
   `age_unknown_policy` ni `disease_params`. Por eso:
   - Siempre reparte `population_size` con las bandas **actuales** de `region_age_groups`.
     - Una versión sin estratificar se corre estratificada y le aplica `letalidad_por_edad`.
       Ese es el caso del escenario de demostración.
     - Con la política `excluir`, reparte también a quien no declaró edad, sin aviso ni marca
       de supuesto.
   - Usa los parámetros **vivos** del catálogo, no los congelados por la 024. Esa parte depende
     de la decisión abierta D5.
   - *Reproducido:* en García con `excluir`, el revisor aprobó N = 397,071 y R0 = 1.28. Tras
     cambiar el R0 del catálogo, la corrida simuló **N = 397,205 y R0 = 9.9**.
   - *Sugerencia:* que F construya la entrada con `get_escenario_detalle()` +
     `escenario_para_motor()` + `intervenciones_para_motor()`, las mismas funciones que usa
     `revisa_version()`.

2. **(Media) Permiso de lectura.** `/simulaciones`, `/simulaciones/corridas/<id>` y `/estado`
   solo llevan `@login_required`. `CAPTURISTA` no tiene `simulations.read` (010) y aun así ve
   escenarios, corridas y resultados, y el menú le muestra la opción (regla 3).
   - *Reproducido:* con un capturista, las tres rutas responden 200.
   - El POST de ejecutar sí se niega, y deja `PERMISSION_DENIED` en la bitácora.
   - Falta una prueba de lectura con un rol que no deba entrar.

3. **(Media) Dengue, zika y malaria no tienen los seis parámetros con fuente.** La 025 captura
   4 de 6. `incubacion_dias` e `infeccioso_dias` se quedan en el formato `dist` de la semilla,
   sin fuente ni supuesto, y `estado_parametros()` los marca `sin_fuente` (regla 8). La prueba
   de la 025 solo revisa las claves que la migración agrega. Además, «el equipo decidió
   simularlas» no aparece en `docs/decisiones.md`, y el encabezado de la 025 dice que la
   decisión «sigue abierta».

4. **(Media) Falta el aviso en las pantallas de resultados.** Ni `simulaciones.html` ni
   `simulacion_detalle.html` muestran `AVISO_SIMULACION` (regla 9; la casilla está en H).
   Tampoco se guardan ni se muestran los `avisos` y las `simplificaciones` del motor: no hay
   columna para ellos en `simulation_results`.

5. **(Baja) Corridas de demostración que nunca terminan.** La semilla deja 100 corridas
   `numba`: 45 en `encolado`, 25 en `ejecutando` y 30 en `completado` sin resultado. Llenan
   «Corridas recientes»; su detalle consulta el estado para siempre o sale sin indicadores, y
   eso puede confundir el paso 15 de la prueba de aceptación.

6. **(Baja) Textos desactualizados.**
   - El encabezado de `routes.py` y el docstring de `listar_versiones_escenario()` dicen que el
     bloque D no se construye.
   - El docstring de `motor/__main__.py` está desactualizado (E10).
   - La pantalla usa las etiquetas PENDIENTE/COMPLETADA/ERROR, que la nota temporal de
     `AGENTS.md` pide reemplazar por los estados de la regla 7. Hay que decidir cuáles se quedan.

## Correcciones (rama `feat/bloque-e-f/correcciones`)

| Hallazgo | Estado | Cambio |
|----------|--------|--------|
| 1 | ✅ | `construir_escenario_desde_version()` usa `queries.escenario_de_version()`, la misma traducción que `revisa_version()`. Reproducido de nuevo: con el R0 del catálogo en 9.9, la corrida simula N = 397,071 y R0 = 1.28 |
| 2 | ✅ | Las tres rutas de lectura piden los roles con `simulations.read` (010) y el menú oculta la opción. Prueba: `test_capturista_no_ve_simulaciones` |
| 3 | ⚠️ Bloqueado | `estado_parametros()` ya no marca simulable una enfermedad con parámetros sin fuente, y la corrida lo vuelve a revisar. Dengue, zika y malaria no se simulan hasta que el equipo capture la fuente de `incubacion_dias` e `infeccioso_dias`. E12 quedó desmarcada en el checklist |
| 4 | ⚠️ Parcial | `AVISO_SIMULACION` en la lista y el detalle. El detalle muestra también los parámetros usados (F3) y las simplificaciones del motor actual. Los `avisos` de cada corrida siguen sin guardarse: se decidió no crear la migración 026 |
| 5 | ✅ | La semilla y `gen_demo_data.py` ya no crean corridas `numba`. La tarjeta SIMULACIONES del tablero arranca en 0 |
| 6 | ✅ | Textos actualizados. La pantalla muestra los estados de la base: ENCOLADO, EJECUTANDO, COMPLETADO, FALLIDO, CANCELADO |

Sigue abierto:
- `/escenarios` todavía deja entrar a cualquier usuario autenticado. Es una decisión del bloque D.
- La prueba del hallazgo 2 deja en la base un usuario inactivo, `prueba.capturista`.

## Instrucciones para un agente

Todo se corre desde la raíz del repositorio.

### Entorno

- PostgreSQL 15 en `localhost:5432`. `psql -h localhost -U postgres` entra sin contraseña
  (`~/.pgpass`). `epidemia_app` no puede crear bases.
- El sistema no tiene Flask. Crea el entorno virtual:
  `python3 -m venv .venv && .venv/bin/pip install -r frontend_web/requerimientos.txt`.
  Instala también el backend y `numpy`.
- Las pruebas toman `DATABASE_URL` de `.env`, pero una variable exportada tiene prioridad. No
  imprimas `.env`: trae contraseñas. También necesitan `JWT_SECRET_KEY`; cualquier valor sirve.

### Correr las pruebas

```bash
export JWT_SECRET_KEY=test-secret
(cd procesamiento && ../.venv/bin/python -m unittest discover -s tests -t .)   # motor, sin base
.venv/bin/python -m unittest discover -s backend_web/tests -t .
.venv/bin/python -m unittest discover -s frontend_web/tests -t .
```

Para no tocar la base de la persona:
1. Como `postgres`, crea una base temporal (`CREATE DATABASE ...`).
2. Cárgala con los pasos 2 y 3 de `docs/INSTALACION.md`.
3. Exporta `DATABASE_URL` cambiando solo el nombre de la base.
4. Corre las pruebas y borra la base al terminar.

### Reproducir los hallazgos 1 y 2

- Usa una base con 001–025 y el cliente de pruebas de Flask:
  `create_app()` de `frontend_web.app`, con `app.testing = True`.
- Las contraseñas de demostración están en `frontend_web/tests/test_simulaciones_rutas.py`.

1. **Hallazgo 1**
   1. Como `alex.cavazos`, `POST /escenarios/nuevo` con estos campos:
      `name`, `disease_id` (id de `INFLUENZA_ESTACIONAL`), `region_id` (id del código `19018`), `estratificar=1`,
      `age_unknown_policy=excluir`, `initial_infected=10` y `horizon_days=60`.
      - La respuesta redirige a `/escenarios`; busca el id por nombre.
   2. Luego `POST /escenarios/<id>/enviar`.
   3. Como `diana.flores`, `POST /escenarios/<id>/revisar` con `decision=aprobar` y un
      `comentario`.
   4. Cambia `default_params->'r0'->'valor'` de influenza en `diseases`.
   5. Como `alex.cavazos`, `POST /simulaciones/<version_id>/ejecutar` con una `seed`.
      Espera `terminal` en `/simulaciones/corridas/<run_id>/estado`.
   6. **Corregido ⇔** la suma de `resumen.desglose_por_grupo[].poblacion` es 397,071 y el
      `r0` de `trazabilidad` es el congelado en `scenario_versions.disease_params`.
2. **Hallazgo 2**
   1. Crea un usuario con rol `CAPTURISTA`:
      - una fila en `users` y otra en `user_roles`;
      - la contraseña se genera con `backend_web.auth.hash_password`.
   2. Pide `GET /simulaciones`, `/simulaciones/corridas/<id>` y `/simulaciones/corridas/<id>/estado`.
   3. **Corregido ⇔** las tres se niegan y dejan `PERMISSION_DENIED`, igual que el POST de
      ejecutar. En `6d2cadb` respondían 200.
