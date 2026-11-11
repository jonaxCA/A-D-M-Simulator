# Correcciones pendientes del primer parcial

> **Estado: Vigente** · 2026-11-07 · 

Cada sección alimenta una decisión de [`decisiones/`](decisiones/decisiones.md). Dice qué sigue abierto, qué hay que decidir y, si ya se decidió, qué cambiar.

## Ya resuelto

| Qué                                                       | Dónde                                                                             |
| ---                                                       | ---                                                                               |
| Chequeo de migraciones en verde (0 archivos con problema) | `datos/scripts/verifica_migraciones.py`                                           |
| Sin SQL en las rutas (0 coincidencias en `routes.py`)     | `frontend_web/app/routes.py`                                                      |
| Motor sin Flask ni base de datos                          | `procesamiento/motor/`                                                            |
| Secretos sin valores por defecto                          | `secreto_jwt()` en `backend_web/auth.py`; `backend_web/db.py`                     |
| Redirección abierta en el login                           | `destino_seguro()` en `routes.py`                                                 |
| Ruta `/stub`                                              | Eliminada                                                                         |
| Segundo catálogo (regiones)                               | `/regiones` en `routes.py`                                                        |
| Roles de base por servicio (`svc_*`)                      | Migraciones 026 a 030; `infra/docker-compose.yml`                                 |
| Compose de base y servicios                               | `infra/docker-compose.yml` (sus fallas están en `arquitectura/brechas_v3.md`, E1) |
| Rutas viejas en el checklist                              | Ya no aparecen en `docs/parciales/parcial-2/checklist.md`                         |

## D1 · Permisos y auditoría

Alimenta [D1](decisiones/D01-permisos-y-auditoria.md) y la divergencia de aprobación sin permiso.

**Hoy.** Las rutas se protegen con nombres de rol escritos en el código: 28 decoradores `roles_required` y `admin_required` en `routes.py`, y ninguno que lea permisos. La tabla `role_permissions` (migración 010) existe, pero nada la consulta. El JWT lleva roles, no permisos.

| Pantalla                                       | Quién entra hoy    | Quién debería (migración 010)                                             |
| ---                                            | ---                | ---                                                                       |
| Capturar caso (`/reportes/nuevo`)              | Cualquier sesión   | CAPTURISTA y ADMINISTRADOR (`cases.create`)                               |
| Dar de alta enfermedad (`/enfermedades/nueva`) | Cualquier sesión   | EPIDEMIOLOGO y ADMINISTRADOR (`catalogs.create`)                          |
| Auditoría (`/auditoria`)                       | Solo ADMINISTRADOR | ADMINISTRADOR y EPIDEMIOLOGO (`audit.read`)                               |
| Tableros, mapa, monitoreo y CSV                | Cualquier sesión   | ADMINISTRADOR, EPIDEMIOLOGO y ANALISTA (`reports.read`, `reports.export`) |

Hay dos matrices y no coinciden: la de `requerimentos/matriz-permisos.md` no da la auditoría al EPIDEMIOLOGO, y la de la migración 010 sí.

**Preguntas para el equipo**

1. ¿Quién captura casos desde la web: solo CAPTURISTA, o también EPIDEMIOLOGO y ANALISTA?:
	1. Solo capturista, porque lo hace desde la app movil. El epidemiologo usa la web y el analista la app desktop.
2. ¿Quién da de alta enfermedades: EPIDEMIOLOGO y ADMINISTRADOR, o cualquier usuario con sesión?:
	1. Solo epidemiologo y administrador.
3. ¿EPIDEMIOLOGO consulta la auditoría? Esta respuesta también decide quién ve la auditoría del flujo completo (paso 22 de la prueba de aceptación).:
	1. No, solo administrador.
4. ¿CAPTURISTA entra a la web, o solo a la app móvil? El plan original decía solo Android.:
	1. Solo a la app movil.

**Qué hacer**

1. Contestar las preguntas y registrar las respuestas en D1.
2. Agregar `scenarios.approve` (aprobar o rechazar versiones), que hoy no existe; solo hay `cases.approve`. Dárselo a EPIDEMIOLOGO y ADMINISTRADOR. Aprobar autoriza simular; publicar (`scenarios.publish`) muestra el escenario en el sitio público. Son dos permisos distintos.
3. Cualquier cambio de la matriz va en una migración nueva con el siguiente número libre (hoy, el 031). Nunca se edita la 010. Al crear permisos, darlos explícitamente a ADMINISTRADOR: la 010 le dio solo los que existían entonces.
4. En `backend_web/auth.py`, al iniciar sesión, leer los permisos de todos los roles del usuario y guardarlos en el JWT como claim `perms`.
5. En `frontend_web/app/permisos.py`, crear `requiere_permiso(codigo)`. Debe responder 403 (`abort(403)`), no redirigir al dashboard: si el capturista no puede ver el dashboard, la redirección hace un ciclo. Cada rechazo se registra con `log_audit` como `PERMISSION_DENIED`.
6. Cambiar el candado de cada ruta:

| Ruta                                   | Permiso                                    |
| ---                                    | ---                                        |
| `/dashboard`, `/mapa`, `/monitoreo`    | `reports.read`                             |
| `/export/*.csv`                        | `reports.export`                           |
| `/reportes/nuevo`                      | `cases.create`                             |
| `/enfermedades`                        | `catalogs.read`                            |
| `/enfermedades/nueva`                  | `catalogs.create`                          |
| `/enfermedades/<id>/editar`, `/estado` | `catalogs.update`                          |
| `/usuarios/*`                          | `users.read`, `create`, `update`, `delete` |
| `/auditoria`                           | `audit.read`                               |

7. Exponer `puede()` a las plantillas para ocultar opciones del menú. Ocultar no es control de acceso: el candado real es el decorador.
8. Agregar una cuenta de prueba de CAPTURISTA en `datos/postgres/semillas/demo_datos_nl.sql`. Hoy no existe, así que ese rol no se puede probar.

**Cómo saber que quedó.** `grep -n "roles_required\|admin_required" frontend_web/app/routes.py` no regresa nada. Con las cuatro cuentas se recorren todas las pantallas y cada una hace lo que dice la matriz. Cada rechazo aparece en Auditoría como `PERMISSION_DENIED`.

## D2 · Papel del SEIR

Alimenta [D2](decisiones/D02-papel-del-seir.md) (corrección 2). Depende de D22, que ya aceptó el modelo basado en agentes (ABM).

**Hoy.** `procesamiento/motor/` es un SEIR-HDV estocástico de siete cajas por grupo de edad, sin agentes. Se identifica como `python-ref-0.1` (`ENGINE_VERSION` en `motor/modelo.py`). Es reproducible por semilla, incluye sus simplificaciones y se niega a correr si falta un parámetro con fuente.

Con D22 aceptada, la pregunta ya no es si hay ABM, sino qué papel tiene el SEIR:

|                            | Opción A: el SEIR es el control                       | Opción B: el SEIR es el respaldo                                |
| ---                        | ---                                                   | ---                                                             |
| Motores al final           | Tres: SEIR, ABM en Python y ABM en FLAME GPU          | Dos: SEIR y ABM en FLAME GPU                                    |
| Si FLAME GPU falla         | Queda un ABM funcionando                              | Solo queda el SEIR; se pierden las intervenciones por contactos |
| Efecto en la investigación | El SEIR sirve de control para medir qué aporta el ABM | El aporte depende de que la GPU funcione                        |

Recomendación: **A**. Es la del plan original y da al SEIR un papel útil: sin un control no hay forma de medir qué aporta el ABM en nuestros propios escenarios.

**Qué hacer, si se elige A**

1. Cambiar `ENGINE_VERSION` a `seir-ref-0.1` en `procesamiento/motor/modelo.py`.
2. Migración nueva con el siguiente número libre. El CHECK de `simulation_batches.engine` (migración 014) solo acepta `python-ref`, `numba` y `cuda`. Propuesta de nombres: `python-ref` → `seir-ref`, `numba` → `abm-ref`, `cuda` → `abm-gpu`. El orden dentro de la migración: soltar el CHECK, convertir los valores, poner el CHECK nuevo y cambiar el DEFAULT.
3. Formalizar el formato de entrada y salida del motor como contrato en `docs/contratos/`. Es el acuerdo que deben respetar los tres motores.
4. Construir el ABM en `procesamiento/` como paquete aparte: recibe el mismo diccionario y regresa la misma estructura.

Si se elige B, solo aplica el paso 3, y hay que actualizar la sección 6.2 de la arquitectura v3.

**Cómo saber que quedó.** Desde `procesamiento/`, `python -m motor` imprime `seir-ref-0.1`; la migración corre sin errores sobre la base de demostración; la decisión queda escrita en D2.

## D3 · Unidad de costo y frontera de Pareto

Alimenta [D3](decisiones/D03-unidad-de-costo.md) (corrección 4).

Dos términos: una *persona-día* es un día de actividad de una persona (100 mil niños sin escuela durante 10 días suman un millón de personas-día). Una opción está *dominada* si otra cuesta igual o menos y tiene igual o menos daño, siendo mejor en al menos uno. La *frontera de Pareto* son las opciones no dominadas; entre ellas, elegir es una decisión humana.

**Hoy**

- La frontera (`procesamiento/motor/pareto.py`) vive dentro del motor. La importan `backend_web/simulaciones.py` y los servicios `pareto` y `comparacion`, desde `procesamiento.motor`.
- El costo se calcula en pesos. La migración 014 agregó `unit_cost` y `cost_unit` a `intervention_types`.
- El contexto (sección 2.8) pide personas-día más costo directo; el modelo de datos dice que no hay columnas monetarias. Las dos fuentes se contradicen.

|                  | Personas-día                                              | Pesos                                            |
| ---              | ---                                                       | ---                                              |
| Qué mide         | Actividad que la población dejó de hacer                  | Gasto estimado de cada intervención              |
| Datos que faltan | Ninguno                                                   | Precio por habitante-día y por dosis, con fuente |
| Vacunación       | Como indicador aparte (dosis), o sin costo en la frontera | Sumada al resto                                  |
| Riesgo           | La frontera no refleja el costo de vacunar                | Cifras sin buena fuente debilitan el resultado   |

Recomendación: la **opción C** de D3 (ambas por separado). La frontera usa personas-día y el costo directo en pesos aparece aparte en la tabla comparativa.

**Qué hacer**

1. Escribir la unidad en la arquitectura v3 y en `cost_unit` de cada tipo de intervención.
2. Mover `_desempaca`, `_es_numero` y `_estado_traza` de `motor/parametros.py` a `procesamiento/trazabilidad.py`, sin guion bajo: Pareto las necesita desde fuera del motor.
3. Mover `pareto.py` a `procesamiento/analitica/`. Solo puede importar nombres públicos del motor (`resolver`, `huella_escenario`, `INTERVENCIONES_CAPA`, `EscenarioInvalido`) y el módulo de trazabilidad.
4. Quitar `comparar`, `costo_escenario` y `frontera_pareto` de `motor/__init__.py`, y actualizar los imports de `backend_web/simulaciones.py` y de los servicios `pareto` y `comparacion`.

**Cómo saber que quedó.** Ningún import de `procesamiento/analitica/` trae un nombre con guion bajo; `python -m pytest procesamiento/tests` pasa; la unidad está escrita en la arquitectura v3.

## D4 · Web contra escritorio

Alimenta [D4](decisiones/D04-web-contra-escritorio.md). Depende de D1.

La rúbrica exige que la app de escritorio atienda un proceso distinto al de la web y no sea una copia. Hoy la web hace casi todo el trabajo con escenarios. Propuesta de reparto:

| Tarea                                                               | Web               | Escritorio                                   |
| ---                                                                 | ---               | ---                                          |
| Crear un escenario sencillo y enviarlo a revisión                   | No                | Sí                                           |
| Aprobar o rechazar versiones                                        | Sí                | No                                           |
| Edición detallada del XML (población, calendario de intervenciones) | No                | Sí                                           |
| Lanzar una corrida                                                  | No                | Sí                                           |
| Lanzar lotes de decenas de réplicas                                 | No                | Sí                                           |
| Comparar y ver la frontera                                          | Vista de consulta | Comparador completo, exportación e impresión |

Esto debe quedar escrito en la arquitectura v3 antes de construir las pantallas de escenarios.

## D5 · Versión inmutable

Alimenta [D5](decisiones/D05-foto-de-la-version.md), que ya está aceptada, y la corrección 5.

**Ya resuelto.** La migración 023 guarda la población por grupo de edad en la versión, y la 024 congela los parámetros de la enfermedad (`disease_params`) al enviarla. La 014 impide simular versiones que no estén aprobadas (`fn_version_aprobada`). La foto de la entrada del motor que proponía la versión anterior de este documento ya no hace falta: `disease_params` cumple ese papel.

**Falta.** Nada en la base impide cambiar el contenido de una versión ya enviada: `population_size`, `horizon_days`, `initial_infected` ni las intervenciones. No hay trigger que lo evite. El monolito corre con `epidemia_app`, que tiene SELECT, INSERT, UPDATE y DELETE sobre todas las tablas (`docs/INSTALACION.md`).

**Qué hacer.** Una migración nueva con dos triggers:

- `BEFORE UPDATE` en `scenario_versions`: rechazar cambios a `population_size`, `horizon_days`, `initial_infected`, `scenario_id`, `version_number` y `created_by` cuando `status` ya no es `borrador`.
- `BEFORE INSERT, UPDATE OR DELETE` en `scenario_interventions`: rechazar cuando la versión ya no está en `borrador`.

La regla que debe quedar escrita: *editable en borrador, congelada al enviarse*. Los campos del flujo (`status`, `reviewed_by`, `reviewed_at`, `review_comment`, `notes`) siguen cambiando.

Efecto a probar: borrar un escenario con versiones enviadas debería fallar por la cascada. Es lo deseable, porque un escenario con historia se archiva y no se borra.

**Cómo saber que quedó.** Con `psql`, cambiar `population_size` de una versión aprobada falla; agregar una intervención a esa versión falla; cambiar `review_comment` de una versión en revisión funciona.

## D6 · Población del escenario

Alimenta [D6](decisiones/D06-poblacion-del-escenario.md). Depende de D22.

**Hoy.** `scenario_versions.population_size` acepta entre 1,000 y 20 millones (migración 023). El checklist la trata como habitantes, pero el ABM simula agentes. No son lo mismo: Nuevo León tiene 5,784,442 habitantes (Censo 2020) y Monterrey, 1,142,994. Un ABM de unos 100 mil agentes no puede tener un agente por cada habitante de Monterrey.

**Propuesta: la opción C de D6 (factor de escala).**

- `population_size` cuenta agentes simulados.
- Los habitantes representados vienen de `regions.population`, solo lectura.
- Factor = habitantes / agentes. Con 100 mil agentes para Monterrey, cada agente representa unas 11.4 personas, y los casos y muertes se multiplican por ese factor al mostrarlos.

**Qué hacer.** Decidir antes de construir la pantalla de crear escenario. Si cambia el esquema, la migración usa el siguiente número libre.

## D7 · Política de migraciones

Alimenta [D7](decisiones/D07-politica-de-migraciones.md) y la divergencia de migraciones.

**Hoy.** `verifica_migraciones.py` pasa. Pero los datos se han corregido de distintas maneras: la 012 corrige claves INEGI, la 015 aplica las cifras del censo y la 019 es una corrección manual de población. No hay una regla escrita.

**Propuesta para el README de migraciones.** No es la opción A ni la B de D7; conviene agregarla como una tercera:

- **Datos** (valores de un `INSERT`): se pueden corregir en la fuente solo si se corrigen juntos el archivo de `migraciones/` y el bloque del dump, hay una migración correctiva idempotente y el chequeo pasa.
- **Esquema** (tablas, columnas, restricciones, triggers, funciones): nunca se edita un archivo aplicado. Siempre un número nuevo.

## D8 · Réplicas de una comparación

Alimenta [D8](decisiones/D08-replicas-de-una-comparacion.md) y la divergencia de réplicas.

**Hoy.** La migración 014 bajó el mínimo de réplicas de 30 a 1 (`ck_simulation_batches_replicas`, entre 1 y 200), con el argumento de que el motor es reproducible por semilla. Pero reproducible no es representativo: otra semilla da otro resultado, igual de válido.

Cifras de 30 semillas (de la 1 a la 30) de la versión anterior de este documento. No se volvieron a correr.

| Escenario           | Con la semilla del ejemplo (982314) | Promedio con 30 semillas | Rango    |
| ---                 | ---                                 | ---                      | ---      |
| A: sin intervención | 100                                 | 114.8                    | 96 a 137 |
| B: cierre escolar   | 67                                  | 82.1                     | 62 a 98  |
| C: vacunación 60+   | 71                                  | 72.7                     | 48 a 91  |
| D: cierre + vacuna  | 51                                  | 50.6                     | 35 a 70  |

Con la semilla del ejemplo, B tiene menos muertes que C y aparece en la frontera. Con 30 semillas, B tiene más muertes que C en 24 de 30 casos y queda dominado en 25 de las 30 fronteras.

**Propuesta**

1. Toda comparación usa lotes de N = 30 réplicas, el valor que fija el modelo de datos.
2. Las mismas semillas (de la 1 a la N) en todos los escenarios comparados, para que las diferencias se deban a las intervenciones.
3. La tabla y la gráfica muestran la mediana y una banda (del percentil 5 al 95), no un solo número.
4. La frontera se calcula sobre las medianas. Cuando las bandas de dos escenarios se enciman, la pantalla lo indica.
5. La corrida suelta con semilla fija solo sirve para demostrar reproducibilidad; no es una comparación.

Costo: las 120 corridas (30 por 4 escenarios) tardan cerca de un segundo con el SEIR.

## D20 · Partir `queries.py`

Alimenta [D20](decisiones/D20-web-directa-a-postgres.md) (corrección 3).

**Hoy.** `backend_web/queries.py` tiene 3,815 líneas y mezcla SQL, reglas de validación y textos de pantalla. Las rutas no tienen SQL, así que la capa de repositorio existe de hecho, pero no hay `repos/` ni `servicios.py`.

**Propuesta.** Aunque D20 deje la web conectada directo a PostgreSQL, separar el archivo la deja más fácil de leer:

- `backend_web/repos/`: solo SQL, un archivo por dominio.
- `backend_web/reglas/`: validación, sin SQL.
- `frontend_web/app/formato.py`: meses, etiquetas y textos de pantalla.
- `frontend_web/app/servicios.py`: la fachada, lo único que importan las rutas. Si D20 elige la opción B, aquí es donde cambia la llamada por HTTP.

Orden de PRs: usuarios y auditoría, catálogo, casos y al final analítica. Conviene hacerlo después de D1, porque ambas tocan `routes.py`. Solo se mueven funciones; si algo necesita arreglo, va en otro PR.

**Cómo saber que quedó.** `queries.py` ya no existe, y `routes.py` solo importa `servicios` y `formato`.

## Preparaciones pendientes

- **Cola de simulaciones.** *Resuelto con D4 (2026-11-11): la web ya no lanza corridas; las lanza el escritorio por `corridas` y las ejecuta el simulador desde la cola.* El monolito corría cada corrida en un hilo (`routes.py`, línea 1117). Si el servidor se reinicia, la corrida queda a medias; `recupera_corridas_interrumpidas()` en `backend_web/simulaciones.py` atiende ese caso. Los servicios ya tienen cola (`microservicios/comun/epidemia_comun/cola.py`). Falta decidir si el monolito usa la tabla `simulation_runs` como cola o la de los servicios.
- **`simulation_results` como tabla puente.** Sigue en la migración 014. Su plan de salida a MongoDB depende de D28 (qué datos van a MongoDB).
- **`jti` en la sesión web.** Los servicios ya lo tienen (`epidemia_comun/sesiones.py`); `backend_web/auth.py` no. Solo hace falta si la web mantiene sesiones propias (ver D19).

## Pendientes menores

- **Chequeo automático (CI).** No existe `.github/`. Crear `.github/workflows/verificaciones.yml` que instale `procesamiento/requerimientos.txt`, corra `verifica_migraciones.py` y `python -m pytest procesamiento/tests` en cada push y PR. Después, proteger `main` para que no se pueda integrar si falla.
- **Pool de conexiones y consulta del mapa.** `backend_web/db.py` abre y cierra una conexión por consulta (`get_conn` llama a `_conecta()` en cada llamada), aunque su comentario habla de "un solo pool". `routes.py`, líneas 200 y 222, llama a `get_tendencia_zona` una vez por municipio (51 llamadas). Usar `psycopg2.pool` y una consulta agrupada por municipio.
- **API versionada y salud.** `/api/mapa` (`routes.py`, línea 213) no tiene versión, y la web no tiene endpoints de salud.
- **Renombrar "Monitoreo" (opcional).** El motivo original era evitar la confusión con el servicio de monitoreo de la arquitectura v1. Ese servicio ahora se llama `estado-servicios` (D13), así que el choque ya no existe.
- **Documentación.** `datos/postgres/migraciones/README.md` (línea 60) todavía dice `./Datos/...` con mayúscula. `.gitignore` (línea 26) dice que el esquema vive en `db/`.
