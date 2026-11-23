# EPIDEMIA — Catálogo de microservicios

Son **29 microservicios** pequeños, cada uno con una sola tarea, más una **consola** web para
probarlos. Los usan las apps de escritorio (XML) y móvil (JSON) y el sistema web, que desde D36
los consume por HTTP, módulo por módulo, sin credenciales de PostgreSQL, MongoDB ni Redis.

Parten de los siete servicios de `arquitectura_v1.md`, divididos en tareas específicas. Guardan
sus datos en PostgreSQL (un rol por servicio, D18), Redis (solo lo temporal, D19), MongoDB (las
series de las corridas y el historial de salud, D28) y un bucket de Cloud Storage (los archivos,
D30), y entran por nginx con HTTPS (D25, D26). Cuánto vive cada dato: el inventario de
[`matrices_v3.md`](matrices_v3.md) (§2, D52).

## Reglas comunes

- **Una tarea por servicio.** Si la descripción necesita un "y además", probablemente son
  dos servicios.
- **JSON y XML en todos.** Responden XML por defecto y JSON con `?format=json`, como en
  clase, o con la cabecera `Accept: application/json`; si los dos chocan, manda `?format`.
  Aceptan cuerpos en los dos formatos según el `Content-Type`. Cuando un servicio llama a
  otro, también puede pedir cualquiera de los dos.
- **Un dueño por tabla.** Solo un servicio escribe en cada tabla o columna. Los demás la
  leen, y su rol de PostgreSQL no tiene permiso para escribirla. Las excepciones están
  anotadas abajo. `microservicios/comun/tests/test_catalogo_escribe_bd.py` revisa la columna
  *Escribe* contra los permisos de cada rol en la base de pruebas.
- **`audit_log` es de todos, pero solo para insertar.** Cada escritura se audita en la misma
  transacción, con `log_audit(..., cur=cur)`, como hoy. Un 403 también queda anotado, como
  `PERMISSION_DENIED`, desde `requiere_token` (D36, migración 046). La consulta de la
  bitácora es de `roles` (D37).
- **Un contenedor por servicio.** Todos parten de una imagen base (`infra/docker/`), escuchan en
  el puerto 8000 dentro de su contenedor y publican un puerto propio hacia fuera, según la tabla.
- **Cada regla con su servicio (E8, D37).** Los servicios de E y F, y `evidencias` (D2), ya no
  importan `backend_web`: sus imágenes parten de `base-identidad`, `base-simulacion` y
  `base-vigilancia`, y sus reglas viven en su carpeta ([`duenos_de_reglas.md`](duenos_de_reglas.md)).
  Los de catálogos y escenarios (`enfermedades`, `parametros`, `regiones`, `poblacion`,
  `tipos-intervencion`, `escenarios`, `intervenciones`, `aprobacion`, `validacion` y
  `escenarios-xml`) todavía lo importan desde `epidemia/base` (D7 del checklist).
  `procesamiento/` (el motor) solo va en las imágenes que lo usan: `base-simulacion` y
  `epidemia/base`.

## Esquema de puertos

| Dominio    | Puertos   |
|------------|-----------|
| Identidad  | 5201–5204 |
| Catálogos  | 5211–5215 |
| Vigilancia | 5221–5225 |
| Escenarios | 5231–5235 |
| Simulación | 5241–5245 |
| Analítica  | 5251–5253 |
| Plataforma | 5260–5262 |

Fuera de este esquema quedan el monolito (5000), PostgreSQL (5432), Redis (6379 en la red
de Docker; en tu máquina, `127.0.0.1:6380`, para no chocar con Memurai), MongoDB (27017 en la
red de Docker; en tu máquina, `127.0.0.1:27018`) y el emulador del bucket (`127.0.0.1:4443`,
solo en local).

---

## Identidad y acceso

| # | Servicio   | Hace una cosa                                    | Rutas principales                                                                                                                       | Escribe                                    | Lee                                                | Llama a                                               | Puerto |
|---|------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------------------------------------------------|-------------------------------------------------------|--------|
| 1 | `auth`     | Inicia sesión (con MFA para los perfiles críticos, D40) y emite el *access* y el *refresh* | `POST /api/v1/auth/login`, `POST /api/v1/auth/mfa/verify`, `/mfa/enroll` y `/mfa/confirm`, `DELETE /api/v1/auth/mfa/{user_id}` (ADMINISTRADOR) | `users` (intentos fallidos, último acceso), `user_mfa`, `mfa_backup_codes` | `users`, `roles`, `user_roles` | Redis (guarda el reto de MFA); `sesiones`, para revisar el dispositivo y abrir la sesión | 5201   |
| 2 | `sesiones` | Renueva, cierra y revoca sesiones; limita las concurrentes y autoriza dispositivos (D41) | `POST /api/v1/sessions/refresh`, `POST /api/v1/sessions/logout`, `GET /api/v1/sessions/current`, `DELETE /api/v1/sessions/user/{id}`, `POST /api/v1/sessions/internal/open` y `POST /api/v1/sessions/devices/check` (internas), `GET /api/v1/sessions/devices`, `POST /api/v1/sessions/devices/{id}/authorize` y `/revoke` | `session_devices` | — | Redis | 5202   |
| 3 | `usuarios` | Administra cuentas y da a cada una su perfil     | `GET /api/v1/users/me` (cualquier rol), `GET/POST /api/v1/users`, `GET /api/v1/users/summary`, `GET/PUT /api/v1/users/{id}`, `POST /api/v1/users/{id}/activate` y `/deactivate`, `DELETE /api/v1/users/{id}`, `GET/POST /api/v1/institutions`, `PUT /api/v1/institutions/{id}` (D42) | `users`, `institutions`                    | `user_roles`, `regions` (`id`, `name`) y las tablas que hacen de dependencia | `sesiones`, para cerrar las de una cuenta desactivada | 5203   |
| 4 | `roles`    | Consulta roles y permisos, los asigna, consulta la bitácora y guarda el alcance de cada cuenta | `GET /api/v1/roles`, `GET /api/v1/roles/{id}/permissions`, `PUT /api/v1/roles/assignments/{user_id}`, `GET /api/v1/audit`, `GET /api/v1/audit/summary`, `GET /api/v1/audit/filters`, `GET /api/v1/audit/history/{tipo}/{id}`, `GET /api/v1/scopes/me`, `GET/PUT /api/v1/scopes/{user_id}` (D43), `GET /api/v1/permissions/me` y `POST /api/v1/audit/denied` (cualquier rol: los permisos propios y el 403 de una pantalla de la web, RF-A05) | `user_roles`, `user_scopes`, `audit_log` (solo `PERMISSION_DENIED`)                | `roles`, `permissions`, `role_permissions`, `audit_log`, `users` (`id`, `full_name`), `regions`, `institutions`, `scenarios`, `scenario_versions`, `scenario_interventions` (solo la región, para el alcance del historial, D43; 055) | `sesiones`, para cerrar sesiones al quitar un rol     | 5204   |

## Catálogos

| # | Servicio             | Hace una cosa                                                       | Rutas principales                                                                                 | Escribe                                                                    | Lee                            | Llama a | Puerto |
|---|----------------------|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|--------------------------------|---------|--------|
| 5 | `enfermedades`       | Alta, edición y baja lógica de enfermedades                         | `GET/POST /api/v1/diseases`, `GET /api/v1/diseases/stats`, `GET/PUT /api/v1/diseases/{id}`, `POST .../activate` y `/deactivate` | `diseases` (el alta, con sus parámetros iniciales; después, todo menos `default_params`) | `cases` y `regions` (para la actividad y las detectadas en NL) | —       | 5211   |
| 6 | `parametros`         | Parámetros epidemiológicos, cada uno con fuente o marca de supuesto | `GET/PUT /api/v1/diseases/{id}/parameters`, `GET /api/v1/diseases/{id}/parameters/status`         | `diseases.default_params`                                                  | `diseases`                     | —       | 5212   |
| 7 | `regiones`           | Nuevo León y sus 51 municipios, solo lectura                        | `GET /api/v1/regions`, `GET /api/v1/regions/state`, `GET /api/v1/regions/{id}`                     | —                                                                          | `regions`, `region_age_groups`, `audit_log` (la última corrección del 60+), `users` (`full_name`) | —       | 5213   |
| 8 | `poblacion`          | Población y bandas de edad, con sus correcciones                    | `GET/PUT /api/v1/regions/{id}/population`, `GET/PUT /api/v1/regions/{id}/age-groups`              | `regions.population` y `regions.population_60plus`, `region_age_groups` (`population`), `region_population_adjustments` | `regions`                      | —       | 5214   |
| 9 | `tipos-intervencion` | Tipos de intervención con el esquema de sus parámetros              | `GET /api/v1/intervention-types`, `GET /api/v1/intervention-types/{code}`                         | —                                                                          | `intervention_types`           | —       | 5215   |

## Vigilancia

| #  | Servicio         | Hace una cosa                                                 | Rutas principales                                                                                                        | Escribe                                                 | Lee                                                              | Llama a                                                        | Puerto |
|----|------------------|---------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------|--------|
| 10 | `casos`          | Registra, consulta y corrige casos y cambia su estado (D47); formularios por enfermedad (D48) | `POST /api/v1/cases`, `POST /api/v1/cases/batch`, `GET /api/v1/cases`, `GET /api/v1/cases/{id}`, `PATCH /api/v1/cases/{id}`, `POST /api/v1/cases/{id}/status`, `GET /api/v1/cases/{id}/history`, `GET /api/v1/cases/incomplete`, `GET /api/v1/forms`, `GET /api/v1/forms/current`, `GET /api/v1/forms/{id}`, `POST /api/v1/forms`, `PUT /api/v1/forms/{id}`, `POST /api/v1/forms/{id}/publish` | `cases`, `case_history`, `case_forms` (D48)             | `diseases`, `regions`, `devices` (`id`, `user_id`, `is_revoked`) | `notificaciones` al descartar o marcar duplicado (`CASE_REJECTED`, best-effort) | 5221   |
| 11 | `sincronizacion` | Recibe lotes de casos capturados sin conexión en la app móvil | `POST /api/v1/sync/cases`, `GET /api/v1/sync/batches/{id}`                                                               | — (los casos los escribe `casos`)                       | —                                                                | `casos`: el lote en una llamada (`/cases/batch`) y una por corrección (`PATCH /cases/{id}` con If-Match, D47), en JSON; reenvía el token de la persona; `notificaciones` una vez por lote con casos nuevos (best-effort) | 5222   |
| 27 | `dispositivos`   | Registra, consulta y revoca los dispositivos de las apps      | `POST /api/v1/devices`, `GET /api/v1/devices`, `GET /api/v1/devices/{id}`, `POST /api/v1/devices/{id}/revoke`            | `devices` (alta, versión, última conexión y revocación) | —                                                                | —                                                              | 5223   |
| 28 | `evidencias`     | Los archivos en el bucket (D30): fotos y PDF de los casos y el reporte de una comparación (D35) | `POST/GET /api/v1/cases/{id}/attachments`, `GET/DELETE /api/v1/attachments/{id}`, `GET /api/v1/attachments/{id}/url`, `GET /api/v1/attachments/{id}/content`, `POST/GET /api/v1/reports`, `GET/DELETE /api/v1/reports/{id}`, `GET /api/v1/reports/{id}/url` | `case_attachments`, `comparison_reports` (039); los archivos, en el bucket | `cases` (`id`, `reported_by`), `simulation_runs` (`id`) | — (el bucket de Cloud Storage; en local, el emulador del compose) | 5224   |
| 29 | `vacunas`        | Lotes de vacuna leídos por QR, las dosis que se les aplican y las campañas (D49) | `POST/GET /api/v1/vaccine-lots`, `GET /api/v1/vaccine-lots/{id}`, `POST /api/v1/vaccine-lots/{id}/doses`, `GET/POST /api/v1/campaigns`, `GET/PUT /api/v1/campaigns/{id}`, `POST /api/v1/campaigns/{id}/cancel` | `vaccine_lots` (alta y `doses_used`), `campaigns`       | `diseases`, `regions` (`id`, `name`, `level`, `parent_region_id`, `code`) | `notificaciones` al crear o cancelar una campaña (`CAMPAIGN`, best-effort) | 5225   |

- `sincronizacion` usa Redis para que el mismo lote enviado dos veces no duplique casos
  (`sync:lote:<id>`, 7 días). Regresa el resultado de cada caso: creado (201 de `casos`),
  duplicado (200 con `duplicado: true`) o rechazado con su error. Un candado por lote
  (`sync:lote:<id>:candado`, 300 s) evita que dos peticiones lo procesen a la vez; no escribe
  tablas, solo deja un `SYNC` por lote en la bitácora.
- `dispositivos` registra el teléfono o la PC de quien inició sesión (el `device_uid` lo genera
  la app) y lo revoca. Cada quien maneja los suyos; ADMINISTRADOR, los de todos. Revocar es
  para siempre. `last_seen_at` se actualiza cuando la app vuelve a registrarse, no en cada caso.
- `casos` lee `devices` para no aceptar un caso de un dispositivo que no existe o es de otra
  cuenta (422) o que está revocado (409), aunque el token siga vigente. Los casos que llegan
  por `sincronizacion` pasan por la misma revisión: salen rechazados en el resultado del lote,
  con `codigo` `CONFLICTO`, que los distingue de un caso con datos malos (`DATOS_INVALIDOS`).
- `evidencias` es el servicio de los archivos (D30, D35). Guarda en el bucket fotos (JPEG, PNG,
  WebP) y PDF de hasta 20 MB; la base guarda ruta, tipo, tamaño y huella SHA-256. El tipo sale del
  contenido y, si el cliente manda `X-Content-SHA256`, la huella tiene que coincidir. Las fotos las
  sube quien reportó el caso (D1: el ADMINISTRADOR no captura) y las ven los cuatro roles que leen
  casos; el reporte (PDF) de una comparación lo suben ANALISTA y ADMINISTRADOR (`reports.upload`)
  desde el escritorio o la web, identificado por sus corridas, y lo ven los roles con
  `reports.read`. Solo ADMINISTRADOR borra. Todo es privado: se abre con una URL firmada que vence
  en 15 minutos o se descarga con token. El mismo archivo subido dos veces no se duplica, así que la
  app puede reintentar; con el bucket caído la subida da 503 y no queda registro. Es el único que usa
  Cloud Storage (regla 12 de `microservicios/AGENTS.md`).
- `vacunas` registra los lotes que la app lee por QR o código de barras (`lot_code` es único)
  y les descuenta las dosis aplicadas con un `UPDATE` condicionado: nunca más de las que quedan
  ni a un lote caducado (en hora de Monterrey). Registran y aplican CAPTURISTA y ADMINISTRADOR;
  consultan los cuatro roles. Ligar un caso a su lote (`cases.vaccine_lot_id`) es de `casos` y
  todavía no se hace.

## Escenarios

| #  | Servicio         | Hace una cosa                                                       | Rutas principales                                                                                                                               | Escribe                                                      | Lee                                                        | Llama a                                                                         | Puerto |
|----|------------------|---------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|------------------------------------------------------------|---------------------------------------------------------------------------------|--------|
| 12 | `escenarios`     | Alta, versiones nuevas, historial y duplicado                       | `GET/POST /api/v1/scenarios`, `GET /api/v1/scenarios/versions`, `GET /api/v1/scenarios/{id}`, `GET/POST /api/v1/scenarios/{id}/versions`, `POST /api/v1/scenarios/{id}/duplicate` | `scenarios`, `scenario_versions`, `scenario_interventions` (solo al duplicar o versionar: copia las de la versión origen) | `diseases`, `regions`, `region_age_groups`, `intervention_types`, `users` (`id`, `full_name`) | `validacion` (JSON, antes de guardar) | 5231   |
| 13 | `intervenciones` | Intervenciones de una versión en borrador                           | `GET/POST /api/v1/versions/{id}/interventions`, `DELETE .../{iid}`, `POST .../{iid}/move`, `PUT .../{iid}/cost`, `PUT .../{iid}/person-days`, `PUT /api/v1/intervention-types/{id}/cost`, `PUT /api/v1/intervention-types/{id}/person-days` | `scenario_interventions`; `intervention_types` (solo `unit_cost`, `cost_source`, `cost_is_assumption`, desde `PUT .../cost`, y `person_days_per_unit`, `person_days_source`, `person_days_is_assumption`, desde `PUT .../person-days`, D3) | `scenarios`, `scenario_versions`, `intervention_types` | — | 5232   |
| 14 | `aprobacion`     | Envío a revisión, aprobación y rechazo                              | `POST /api/v1/scenarios/{id}/submit`, `POST /api/v1/scenarios/{id}/review`, `GET /api/v1/reviews/pending`                                       | `scenario_versions` (solo `status`, `submitted_at`, `disease_params`, `reviewed_by`, `reviewed_at`, `review_comment`) | `scenarios`, `scenario_interventions`, `diseases`, `intervention_types`, `regions`, `users` (`id`, `full_name`) | `validacion` (`GET /api/v1/versions/{id}/validation`); `notificaciones` al enviar a revisión (a los EPIDEMIOLOGO), al aprobar y al rechazar (al autor), best-effort: si no responde solo se anota en el log | 5233   |
| 15 | `validacion`     | Revisa un escenario contra el motor; no guarda nada                 | `POST /api/v1/validate`, `GET /api/v1/versions/{id}/validation`                                                                                 | —                                                            | `scenarios`, `scenario_versions`, `scenario_interventions`, `intervention_types`, `diseases`, `regions`, `region_age_groups`, `users` (`id`, `full_name`) | —                                                                               | 5234   |
| 16 | `escenarios-xml` | Exporta e importa escenarios completos en XML, validados contra XSD | `GET /api/v1/scenarios/{id}/export`, `POST /api/v1/scenarios/import`, `GET /api/v1/schemas/scenario.xsd`                                        | —                                                            | `scenarios`, `scenario_versions`, `scenario_interventions`, `diseases`, `regions`, `intervention_types` | `validacion` (JSON); `escenarios` (le manda el escenario **en XML**); `intervenciones` (JSON) | 5235   |

- `intervenciones` guarda el costo en `intervention_types`, como el monolito: cambiarlo desde
  una intervención cambia el de todas las de ese tipo (conflicto abierto con el catálogo de
  `tipos-intervencion`, que es de solo lectura).
- `escenarios` y `escenarios-xml`: el reparto por edad no viaja entre servicios; `escenarios`
  lo toma del censo de la región cuando `stratify` es verdadero, y `validacion` rechaza un XML
  cuyo reparto no coincide. `escenario.xsd` es público (`GET /api/v1/schemas/scenario.xsd`) y
  el export solo existe en XML. Las intervenciones no guardan región destino.
- `aprobacion` → `notificaciones`: con token de servicio (`token_servicio()`), porque la ruta
  que crea avisos es interna. Es best-effort: si falla, el cambio de estado se mantiene.
- `sincronizacion` → `notificaciones`: un aviso `NEW_CASES` por lote, a los EPIDEMIOLOGO, solo
  cuando el lote se procesa por primera vez y crea al menos un caso. También con token de
  servicio y best-effort. `POST /api/v1/notifications` acepta `role` (`EPIDEMIOLOGO` o
  `ADMINISTRADOR`) en lugar de `user_id`: crea un aviso por cada persona activa con ese rol.
- `estado-servicios` → `notificaciones`: las alertas técnicas (F7), un aviso `SYSTEM` a los
  ADMINISTRADOR cuando un servicio cambia de estado durante 30 s. Con token de servicio; lo que
  no se entrega se reintenta cada 60 s (ver su README).

## Simulación

| #  | Servicio      | Hace una cosa                                                   | Rutas principales                                                                                                           | Escribe                                                                                           | Lee                                                                                                                                                                 | Llama a                                                                                            | Puerto |
|----|---------------|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|--------|
| 17 | `corridas`    | Lanza, cancela y consulta corridas                              | `POST /api/v1/runs` (202), `GET /api/v1/runs`, `GET /api/v1/runs/{id}` (estado y progreso), `POST /api/v1/runs/{id}/cancel`, `POST /api/v1/runs/{id}/retry` (reintenta una fallida, D44), `GET /api/v1/runs/{id}/equivalent` | `simulation_batches`, `simulation_runs` (alta, cancelación y reintento)                                    | `simulation_batches`, `simulation_runs`, `scenario_versions`, `scenarios`, `diseases`, `regions`, `users` (`id`, `username`, `full_name`)                           | `roles` (`GET /api/v1/scopes/me`, alcance por región, D43); Redis: encola la corrida en la cola de su motor (`{"id", "forzar_error"}`) y toma el candado | 5241   |
| 18 | `simulador`   | Proceso trabajador: corre las corridas de la cola de su motor | `GET /api/v1/worker/status` (más `/health`)                                                                                 | `simulation_runs` (estado, avance, intentos y, al completar, resumen, huella y trazabilidad; 038 y 045); `simulation_batches` (estado, el de su corrida); MongoDB `series_corridas` (un documento por día, D28) | `simulation_runs`, `scenario_versions`, `scenarios`, `scenario_interventions`, `intervention_types`, `diseases`, `regions`, `users` (`id`, `username`, `full_name`) | Redis (cola y progreso); MongoDB (la serie, antes de confirmar la corrida; si no responde, la reintenta y la corrida igual termina); `notificaciones` al terminar o fallar, con token de servicio, best-effort | 5242   |
| 19 | `resultados`  | Curvas e indicadores de una corrida                             | `GET /api/v1/runs/{id}/results`, `.../curves`, `.../indicators`, `.../band`                                                           | —                                                                                                 | `simulation_runs`, `scenario_versions`, `scenarios`, `diseases`, `regions`, `users` (`id`, `username`, `full_name`); MongoDB `series_corridas` | `roles` (`GET /api/v1/scopes/me`, alcance por región, D43); Redis (caché, 300 s); MongoDB (la serie: sin él, `/results` y `/curves` dan 503 y `/indicators` sigue) | 5243   |
| 20 | `comparacion` | Compara corridas lado a lado                                    | `GET /api/v1/comparisons?runs=a,b,c[&base=a][&sin_intervencion=a]`                                                                                     | —                                                                                                 | —                                                                                                                                                                   | `resultados` (`GET /runs/{id}/results` y `.../band`) y `pareto` (`GET /pareto`, solo para los costos; sin él, no hay costos), con el token de la persona | 5244   |
| 21 | `pareto`      | Costo contra impacto y frontera de Pareto, con la explicación de cada dominancia; sensibilidad exploratoria y estado de calibración (D46) | `GET /api/v1/pareto?runs=a,b,c`; `GET /api/v1/pareto/sensitivity`; `GET /api/v1/pareto/calibration`                                                                                             | —                                                                                                 | `simulation_runs` (el resumen, 038), `scenario_versions`, `scenarios`, `scenario_interventions`, `intervention_types` (costos), `diseases`, `regions`, `users`  | `roles` (`GET /api/v1/scopes/me`, alcance por región, D43)                                                                                       | 5245   |

- Excepción a "un dueño por tabla": `simulation_runs.status` lo cambian `corridas` (para
  cancelar una encolada) y `simulador` (para ejecutarla). Las dos usan la transición
  condicionada de hoy (`WHERE status = ...`), así que no se pisan. Las dos llevan también el
  lote (`simulation_batches.status` y `finished_at`) al estado de su corrida, en la misma
  transacción (`_sincroniza_lote`).
- Al arrancar, `simulador` regresa a `encolado` las corridas de su motor que quedaron en
  `ejecutando`, para repetirlas con la misma semilla; las que llegan a 3 intentos o son de otra
  versión del motor se cierran como fallidas y su serie se borra (D38,
  `reencola_corridas_interrumpidas`). Después, al arrancar y cada vez que Redis vuelve, mete otra
  vez en la cola las `encolado` de la base (D19).
- `forzar_error` viaja en la cola junto al id: no tiene columna en PostgreSQL.
- Hay una cola por motor y prioridad (`queue:simulaciones:<motor>`, más `:alta` y `:baja`, D44; el simulador toma primero las altas). `corridas` mete cada corrida en la
  de su motor (`engine`, por omisión `seir-ref`, guardado en `simulation_batches.engine`) y
  cada `simulador` toma solo la suya, así que uno sin GPU nunca toma una corrida de `abm-gpu`.
  `corridas` acepta otro motor solo si `MOTORES_HABILITADOS` lo nombra. El compose trae un
  simulador de `seir-ref`, otro de `abm-ref` (`simulador-abm`, con `SIMULADOR_MOTOR`) y, en el
  perfil `gpu`, uno de `abm-gpu` (`simulador-gpu`, con FLAME GPU 2).
- `pareto` lee el resumen de cada corrida directo de `simulation_runs` (038), con su propio
  `datos.py`, y no llama a `resultados`: no necesita la serie de MongoDB. También arma el
  escenario de cada versión y lee los costos.

## Analítica

| #  | Servicio      | Hace una cosa                                      | Rutas principales                                                     | Escribe | Lee                                   | Llama a       | Puerto |
|----|---------------|----------------------------------------------------|-----------------------------------------------------------------------|---------|---------------------------------------|---------------|--------|
| 22 | `indicadores` | Indicadores del tablero y situación por enfermedad | `GET /api/v1/dashboard/indicators`, `GET /api/v1/dashboard/situation`, `GET /api/v1/dashboard/curve` (públicas); `GET /api/v1/dashboard/situation/export` (con sesión) | `audit_log` (EXPORT, migración 046) | `cases`, `regions`, `simulation_runs` | Redis (caché) | 5251   |
| 23 | `series`      | Curva epidémica y series por edad y sexo           | `GET /api/v1/series/cases`, `.../by-age`, `.../by-sex`, `.../totals`, `.../aggregate`, `.../highcharts`  | —       | `cases`                               | Redis (caché) | 5252   |
| 24 | `zonas`       | Mapa por municipio y detalle por zona              | `GET /api/v1/zones`, `GET /api/v1/zones/diseases`, `GET /api/v1/zones/export`, `GET /api/v1/zones/map`, `GET /api/v1/zones/heatmap`, `GET /api/v1/zones/jurisdictions`, `GET /api/v1/zones/geometry`, `GET /api/v1/zones/locate` | `audit_log` (EXPORT, migración 046) | `cases`, `regions`, `diseases` | Redis (caché) | 5253   |

## Plataforma

| #  | Servicio           | Hace una cosa                                  | Rutas principales                                                                                                              | Escribe         | Lee | Llama a                                  | Puerto |
|----|--------------------|------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|-----------------|-----|------------------------------------------|--------|
| 25 | `notificaciones`   | Avisos para las apps                           | `GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications` (solo con token de servicio), `GET` y `PUT /api/v1/notifications/preferences` (D49) | `notifications`, `notification_preferences` | `users` (`id`, `is_active`), `user_roles`, `roles` | —                                        | 5261   |
| 26 | `estado-servicios` | Lista de servicios y sondeo de su salud        | `GET /api/v1/services`, `GET /api/v1/services/health`, `GET /api/v1/services/capacity`, `GET /api/v1/services/{nombre}/history`                                 | MongoDB `historial_servicios` (un sondeo por documento, 30 días, D28) | MongoDB `historial_servicios` | El `/health` de los 26, incluido el suyo, **en XML**; `notificaciones` para las alertas técnicas (F7) | 5262   |
| —  | `consola`          | Página tipo Swagger/Postman para probar los 29 | —                                                                                                                              | —               | —   | Todos, desde el navegador                | 5260   |

- La `consola` es una página: el navegador llama a cada servicio con la URL que da el
  directorio, y cada servicio abre CORS solo para `CONSOLE_ORIGIN` (en el compose,
  `http://localhost:5260`). Su servidor solo entrega la página: no tiene base ni Redis.
- `estado-servicios` también es el directorio: las apps y la consola le preguntan la URL de
  cada servicio en vez de tenerlas escritas a mano. No hay pasarela; es la única forma de
  encontrarlos. Sus tres rutas son públicas, porque la URL de `auth` se necesita antes de
  iniciar sesión. Su rol de PostgreSQL solo se conecta, para su propio `/health` (migración
  030).

---

## Quién llama a quién

```
app móvil (JSON) ────┐                 ┌── consola (navegador)
app escritorio (XML) ┤  token Bearer   │
web (JSON, D36) ─────┤                 │
                     ▼                 ▼
   auth ──► sesiones ──► Redis   (abrir sesión)
   usuarios, roles ──► sesiones   (cerrar sesiones)

   escenarios ──JSON──► validacion ◄──JSON── aprobacion ──► notificaciones
        ▲                    ▲
        └──XML── escenarios-xml ──► intervenciones

   corridas ──cola Redis──► simulador ──► notificaciones
                               │
                               ▼
                    MongoDB (series_corridas) ◄── resultados ◄── comparacion ──► pareto
                  base de datos ◄── pareto   (el resumen, sin resultados)
   sincronizacion ──JSON (el lote y las correcciones)──► casos
   evidencias ──► bucket de Cloud Storage   (fotos y reportes, URLs firmadas)

   estado-servicios ──XML──► /health de los 29
          └──► MongoDB (historial_servicios)
```

Las llamadas entre servicios llevan el **token de la persona** y el `X-Correlation-ID`.
Cuando no hay persona detrás (el `simulador` avisando que terminó, o `estado-servicios`
sondeando), usan un **token de servicio**: dura poco, tiene su propia audiencia y solo lo
aceptan las rutas marcadas como internas.

## Llaves de Redis por servicio

Los nombres salen de `microservicios/comun/epidemia_comun/llaves.py`, y una prueba revisa que
coincidan con esta tabla. Todas llevan TTL, salvo las colas. Del `sid` y del *refresh* solo se
guarda su huella (SHA-256).

| Llave                        | Qué guarda                                                                        | TTL                                                                | Escribe                                        | Módulo     |
|------------------------------|-----------------------------------------------------------------------------------|--------------------------------------------------------------------|------------------------------------------------|------------|
| `session:<h(sid)>`           | Hash: usuario, roles, creada, expira, la huella del *refresh* vigente y la del dispositivo (si el login lo envió) | La sesión, contada desde el login; renovar no la alarga            | `auth`, `sesiones`                             | `sesiones` |
| `user:<id>:sessions`         | Conjunto con las huellas de las sesiones de una cuenta                            | La sesión                                                          | `auth`, `sesiones`                             | `sesiones` |
| `refresh:<h(rt)>`            | Huella del `sid` de su sesión                                                     | Lo que le quede a la sesión                                        | `auth`, `sesiones`                             | `sesiones` |
| `refresh:usado:<h(rt)>`      | Huella del `sid` de un *refresh* ya rotado, para detectar si alguien lo reutiliza | Lo que le quede a la sesión                                        | `sesiones`                                     | `sesiones` |
| `jwt:revoked:<jti>`          | `1`                                                                               | Lo que le quede al token, más 60 s                                 | `sesiones`                                     | `sesiones` |
| `captcha:<id>`               | La respuesta esperada de un captcha de inicio de sesión                           | 5 min; se borra al usarlo, así que sirve para un solo intento      | `auth`                                         | —          |
| `mfa:<h(token)>`             | Hash del inicio de sesión a medias de un perfil crítico: la cuenta, la huella del dispositivo y los intentos fallidos del segundo factor | 5 min; se borra al usarlo o al quinto fallo | `auth`                                         | —          |
| `mfa:fallos:<id>`            | Contador de códigos de segundo factor probados contra una cuenta, sin importar el token de MFA (tope de 5) | 15 min desde el primer intento; se borra al pasar el MFA | `auth` | — |
| `mfa:alta:<id>`              | Huella del código de alta que un ADMINISTRADOR emitió para que esa cuenta enrole su MFA (D40) | 15 min; se borra al usarlo, así que sirve una sola vez | `auth` | — |
| `queue:simulaciones:<motor>` | Corridas por ejecutar con ese motor y prioridad normal: `{"id", "forzar_error"}` en JSON | **Sin TTL**: la vacía el `simulador`, y lo que manda es PostgreSQL | `corridas`                                     | `cola`     |
| `queue:simulaciones:<motor>:<prioridad>` | Las de prioridad `alta` o `baja` de ese motor (D44); el simulador las toma en el orden alta, normal y baja | **Sin TTL**: la vacía el `simulador`, y lo que manda es PostgreSQL | `corridas` | `cola` |
| `lock:corrida:<version>`     | Marca de la petición que lo tomó                                                  | Unos segundos                                                      | `corridas`                                     | `candados` |
| `worker:<motor>:<simulador>` | Latido de un simulador: su motor, su nombre (el del contenedor), la corrida que ejecuta y cuántas lleva, en JSON; `estado-servicios` cuenta los vivos y los ocupados por motor | 30 s; el simulador lo renueva cada 10 s mientras su trabajador corre | `simulador` | — |
| `job:<id>:progress`          | Avance de una corrida (10, 30, 90 y 100)                                          | 24 h (86400 s), desde el último avance                             | `simulador`                                    | —          |
| `cache:<servicio>:<clave>`   | La respuesta, en JSON                                                             | Corto; lo fija cada servicio (`resultados`: 300 s)                 | `resultados`, `indicadores`, `series`, `zonas` | `cache`    |
| `sync:lote:<id>`             | Resultado de un lote ya recibido                                                  | 7 días (`SYNC_LOTE_TTL_SECONDS`, por defecto 604800)               | `sincronizacion`                               | —          |
| `sync:lote:<id>:candado`     | Marca de la petición que está procesando ese lote                                 | 300 s                                                              | `sincronizacion`                               | `candados` |
| `ratelimit:<usuario>:<ruta>` | Contador de peticiones de la ventana; sin sesión, `<usuario>` es `ip-<dirección>` y `<ruta>` es `MÉTODO:regla` | La ventana (60 s por defecto)                                      | todos los servicios                            | `limites`  |
| `health:<servicio>`          | Último sondeo de un servicio, en JSON                                             | Tres intervalos de sondeo: 30 s con `SONDEO_SEGUNDOS` en 10        | `estado-servicios`                             | —          |
| `alert:<servicio>`           | Lo último que se avisó de un servicio a los ADMINISTRADOR (`estado`) y cuándo se avisó su última falla, en JSON (alertas técnicas, F7) | 7 días, desde el último aviso; si vence con el servicio caído, la falla se vuelve a avisar | `estado-servicios` | — |
| `errors:<servicio>`          | Contador de respuestas 5xx del servicio (sin contar `/health`); lo lee el panel   | 24 h, desde el primer error de la ventana                          | todos los servicios                            | —          |

- Todas las rutas protegidas leen `session:` y `jwt:revoked:` desde `@requiere_token`
  (`seguridad.py`), con la misma regla que `epidemia_comun.sesiones.verificar()`.
- Qué servicio es dueño de cada regla de negocio: [`duenos_de_reglas.md`](duenos_de_reglas.md) (E8).
- Las llaves sin módulo se escriben con `requerido()` u `opcional()` de `redis_compartido`,
  siempre con `ex=`. Quien implemente el servicio anota aquí el TTL que eligió.
- Toda llave sale de `llaves.py`, también en la biblioteca. Una prueba busca llaves armadas a
  mano (`"captcha:" + x` o `f"captcha:{x}"`) fuera de ese archivo.

## Opcionales (si sobra tiempo o las apps los piden)

| Servicio        | Hace una cosa                                                        | Tabla que ya existe |
|-----------------|----------------------------------------------------------------------|---------------------|
| `recuperacion`  | Restablecer contraseña; el envío del correo queda fuera de alcance   | `password_resets`   |
| `configuracion` | Ajustes del sistema que leen las apps                                | `system_settings`   |
