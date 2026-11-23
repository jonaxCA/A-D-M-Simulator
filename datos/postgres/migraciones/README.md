# Migraciones de PostgreSQL

Modelo físico del Simulador de respuesta a epidemias. Archivos SQL numerados,
sin Alembic: se ejecutan en orden y cada uno registra su aplicación en la tabla
`schema_migrations`.

## Archivos

| Archivo | Contenido |
|---|---|
| `001_base.sql` | Extensiones, funciones compartidas y tabla de control de migraciones |
| `002_seguridad.sql` | `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `password_resets`, `devices` |
| `003_sistema.sql` | `audit_log`, `notifications`, `system_settings` |
| `004_catalogos.sql` | `diseases`, `regions`, `intervention_types` |
| `005_vigilancia.sql` | `vaccine_lots`, `cases`, `case_attachments` |
| `006_escenarios.sql` | `scenarios`, `scenario_versions`, `scenario_interventions` |
| `007_simulacion.sql` | `simulation_batches`, `simulation_runs` |
| `008_comentarios.sql` | `COMMENT ON` de las 21 tablas y sus 183 columnas |
| `009_roles_bd.sql` | Roles de PostgreSQL por microservicio y sus privilegios |
| `010_datos_iniciales.sql` | Roles de negocio, permisos, matriz de permisos y catálogos |
| `019_correccion_manual_poblacion.sql` | `region_population_adjustments`: ajuste vigente de población hecho a mano por un `ADMINISTRADOR` (Bloque C, catálogo de Regiones) |
| `020_letalidad_por_edad.sql` | Letalidad (IFR) por grupo de edad de COVID-19 e influenza, derivada de literatura publicada. La genera `datos/scripts/build_letalidad_edad.py`: no se edita a mano |
| `021_poblacion_por_grupo_edad.sql` | `region_age_groups`: población de los 51 municipios y del estado abierta en los cinco grupos de edad del motor, más la categoría `edad_no_especificada` (Censo 2020, ITER). La genera `datos/scripts/build_grupos_edad.py`: no se edita a mano |
| `022_poblacion_60plus_derivada.sql` | `regions.population_60plus` pasa a derivarse de `region_age_groups` con un trigger; deja de capturarse a mano |
| `023_escenarios_poblacion_por_edad.sql` | `scenario_versions` guarda la población por grupo de edad y la política de edad desconocida; el tope de población sube de 5 a 20 millones para que quepa el estado completo |
| `024_version_congela_parametros.sql` | `scenario_versions.disease_params`: la versión congela los parámetros de la enfermedad al salir de borrador, para que corregir el catálogo no cambie el significado de lo ya aprobado |
| `025_parametros_enfermedades_restantes.sql` | Captura R0, tasa de hospitalización, días de hospitalización y letalidad -- con fuente o supuesto explícito -- de `DENGUE_DEMO`, `ZIKA_DEMO`, `MALARIA_DEMO` y `PATOGENO_X`, las cuatro enfermedades que `017` y `020` no tocaron |
| `026_roles_por_servicio.sql` | Un rol de PostgreSQL (`svc_*`) por cada uno de los 12 microservicios del grupo de las 14:00, con permisos por columna donde solo escriben una parte |
| `027_roles_servicios_escenarios_casos.sql` | Los roles de los siete microservicios de escenarios y de captura de casos |
| `028_roles_comparacion_pareto.sql` | Los roles de `comparacion` y `pareto`, los dos de solo lectura |
| `029_roles_simulacion_notificaciones.sql` | Los roles de `corridas`, `simulador`, `resultados` y `notificaciones`, y el tipo de aviso `SCENARIO_APPROVED` en `notifications` |
| `030_rol_estado_servicios.sql` | El rol de `estado-servicios`, que solo se conecta: no lee ni escribe tablas |
| `031_rol_dispositivos.sql` | El rol de `dispositivos`, dueño de `devices`, y la lectura de `devices` (dueño y revocado) que necesita `casos` |
| `032_rol_evidencias.sql` | El rol de `evidencias`, dueño de `case_attachments` (sin UPDATE: una evidencia se sube o se borra) |
| `033_rol_vacunas.sql` | El rol de `vacunas`, dueño de `vaccine_lots`; de un lote ya registrado solo cambia `doses_used` |
| `034_permisos_d1_y_reportes.sql` | Permisos de D1 y D35: crea `scenarios.approve` (EPIDEMIOLOGO y ADMINISTRADOR) y `reports.upload` (ANALISTA y ADMINISTRADOR), quita `audit.read` al EPIDEMIOLOGO y `cases.create` al ADMINISTRADOR |
| `035_nombres_de_motores.sql` | Los motores cambian de nombre (D2): `python-ref` → `seir-ref`, `numba` → `abm-ref` y `cuda` → `abm-gpu`, en el CHECK, el DEFAULT y los lotes que ya existen. La 034 queda reservada para D1 |
| `036_tope_de_replicas_100.sql` | El tope de réplicas por lote baja de 200 a 100 (D8): CHECK de `simulation_batches.replicas` y `max_replicas_por_lote` de `system_settings` |
| `037_avisos_de_casos_y_revision.sql` | Tipos de aviso `NEW_CASES`, `SCENARIO_SUBMITTED` y `SCENARIO_REJECTED` en el CHECK, y lectura de `users`, `user_roles` y `roles` para `svc_notificaciones`. La 036 queda reservada |
| `039_reportes_de_comparacion.sql` | `comparison_reports`: los metadatos del reporte (PDF) de una comparación, que sube el escritorio o la web al bucket, identificado por sus corridas (D30, D35). `svc_evidencias` es dueño y lee el `id` de `simulation_runs` |
| `040_personas_dia_por_dosis.sql` | `intervention_types` gana el factor de personas-día por dosis de la frontera de Pareto (D3): valor, fuente y marca de supuesto, sin valor por omisión. `svc_intervenciones` puede actualizarlo |
| `045_intentos_de_corridas.sql` | `simulation_runs.attempts` (0 a 3): las veces que una corrida pasó a `ejecutando`. Una interrumpida se reencola mientras le queden intentos (D38); `svc_simulador` lo actualiza |
| `046_bitacora_de_servicios.sql` | Los diez roles `svc_*` que no escribían en `audit_log` reciben INSERT, para anotar el `PERMISSION_DENIED` de sus 403 (D36), y `svc_roles` lee `audit_log` para la consulta de la bitácora (D37) |
| `050_dispositivos_de_sesion.sql` | `session_devices`: los dispositivos desde los que una cuenta inicia sesión, con su estado (`pendiente`, `autorizado`, `revocado`) (D41, RF-A08). `svc_sesiones` es dueño |
| `051_mfa.sql` | `user_mfa` y `mfa_backup_codes`: el secreto TOTP y los códigos de respaldo de los perfiles críticos (D40). `svc_auth` es dueño |
| `054_prioridad_de_corridas.sql` | `simulation_runs.priority` (`baja`, `normal`, `alta`) para la cola con prioridades, y los permisos de `svc_corridas` para reintentar una corrida fallida (D44) |
| `052_instituciones_y_perfiles.sql` | `institutions`, `users.institution_id` y `users.region_id` (opcionales), y los roles INVESTIGADOR y AUTORIDAD_SANITARIA con permisos de solo lectura como supuesto (D42). `svc_usuarios` es dueño de `institutions` |
| `055_historial_con_alcance.sql` | `svc_roles` lee `scenarios`, `scenario_versions` y `scenario_interventions` para aplicar el alcance regional (D43) al historial de un escenario |
| `053_alcances_de_usuario.sql` | `user_scopes`: la región o institución a la que se limita una cuenta; sin filas es nacional (D43). `svc_roles` es dueño |
| `056_nombres_oficiales_municipios.sql` | Nombre oficial de INEGI, con acento, de cuatro municipios que `010` cargó sin él: García, San Pedro Garza García, Juárez y San Nicolás de los Garza |
| `057_seguimiento_de_casos.sql` | `cases.version`, `updated_at`, `updated_by`, `status_reason` y `duplicate_of`; `case_history` (un cambio por fila) y el aviso `CASE_REJECTED`. `svc_casos` actualiza solo las columnas que se corrigen (D47) |
| `058_centroide_de_marin.sql` | El marcador de Marín (`centroid_lat`, `centroid_lon`) dentro de su municipio: su centroide caía en Doctor González. Solo para bases que ya existen; las nuevas lo traen de la semilla |
| `059_formularios_por_enfermedad.sql` | `case_forms` (el formulario de cada enfermedad, por versión: borrador, publicado o retirado) y `cases.form_id` y `form_answers` (D48). `svc_casos` lo administra |
| `060_campanas_y_preferencias.sql` | `campaigns` (las escribe `svc_vacunas`), `notification_preferences` (los avisos que una persona apaga; SYSTEM no) y los tipos `CAMPAIGN` y `DATA_INCOMPLETE` (D49) |
| `061_serie_observada.sql` | `observed_datasets` y `observed_points` (las series observadas, agregadas y versionadas, con fuente, licencia, corte y huella), el permiso `datasets.upload` y el rol `svc_importacion` (D53). Trae la serie de D50: casos confirmados de COVID-19 en Nuevo León por semana de inicio de síntomas, del 2020-03-01 al 2020-07-26 (DGE). La genera `datos/scripts/build_serie_observada.py`: no se edita a mano |
| `063_casos_sinteticos.sql` | Nuevo `COMMENT ON TABLE cases`: en la demostración son sintéticos y no calibran (D50). La 062 es de E (`calibrations`) |
| `064_proyectos_archivado_y_firma.sql` | `research_projects` y `scenarios.project_id` (proyectos de investigación, D54), el UPDATE de `scenarios.status` para archivar y `fn_version_aprobada` sin corridas de escenarios archivados (D54), `scenario_versions.approval_sha256` (la firma de la versión aprobada) y el aviso `SCENARIO_RETURNED` (devolver para cambios, D55) |

El orden importa: `005` referencia catálogos de `004`, y `007` referencia
escenarios de `006`. No cambien la numeración.

## Números reservados (tercer parcial)

Acordados el 2026-11-17 con el líder (bloque 0 del
[checklist](../../../docs/parciales/parcial-3/checklist.md)). Los huecos no son
problema: ya falta la 018.

| Número | Bloque | Contenido |
|---|---|---|
| 034 | C | Permisos de D1 y D35: crea `scenarios.approve` y `reports.upload`, quita `audit.read` al EPIDEMIOLOGO y `cases.create` al ADMINISTRADOR |
| 038 | D | Columnas del resumen en `simulation_runs` y sus permisos para los roles `svc_*` (D28) |
| 039 | D | Tabla de metadatos de los reportes y el rol del servicio que la escribe (D30, D35) |
| 040 | E | Lugar del factor de día-persona por dosis, con fuente o marca de supuesto (D3) |
| 041 | D | Retira `simulation_results`, cuando la web ya no la lea (D28) |
| 042–044 | D | Reserva |
| 045 | E | `simulation_runs.attempts`: intentos de una corrida interrumpida que se reencola (D38) |
| 046 | E | INSERT en `audit_log` para los roles que no lo tenían y lectura para `svc_roles` (D36, D37) |
| 047 | C | Reserva |
| 048–049 | 0 | Reserva del líder (por ejemplo, `cost_unit` en pesos, D3) |
| 050 | E | Dispositivos desde los que una cuenta inicia sesión, `session_devices` (D41) |
| 051 | E | MFA: `user_mfa` y `mfa_backup_codes` (D40) |
| 052 | E | Instituciones, región de cada cuenta y los perfiles nuevos (D42) |
| 053 | E | Alcance por región o institución de cada cuenta (D43) |
| 054 | E | `simulation_runs.priority`: prioridad de la corrida en la cola y permisos para reintentarla (D44) |
| 055 | E | `svc_roles` lee escenarios para el alcance regional del historial (D43) |
| 056 | F | Nombre oficial, con acento, de los cuatro municipios de `010` que no lo tenían (asignada por el líder, 2026-11-22) |
| 057 | F | Corrección y estado de los casos con versión e historial, y el aviso `CASE_REJECTED` (D47) |
| 058 | F | El marcador de Marín dentro de su municipio (2026-11-22) |
| 059 | F | Formularios por enfermedad con versiones y las respuestas de cada caso (D48, 2026-11-22) |
| 060 | F | Campañas, preferencias de avisos y los avisos de campaña y de datos incompletos (D49, 2026-11-22) |
| 061 | D | Serie observada: `observed_datasets` y `observed_points`, con los datos de la serie (D50) |
| 062 | E | `calibrations`, el permiso `calibrations.run` y el rol `svc_calibracion` (D50) |
| 063 | D | Nuevo `COMMENT ON TABLE cases`: sintéticos y sin uso para calibrar (D50) |
| 064 | D | Proyectos, archivado, devolución y firma de versiones (D54, D55). Pedida al líder el 2026-11-23: no cabe en la 042 porque rehace `ck_notifications_type`, y en una instalación limpia la 057 y la 060 lo volverían a dejar sin `SCENARIO_RETURNED` |
| 065 en adelante | — | Se piden al líder |

1. **Cada migración corre en cualquier orden.** El dump las tiene en el orden en
   que se integran, y una instalación limpia las corre por número: la 034 llegará
   al dump después de la 037, pero corre antes en una instalación limpia. Ninguna
   depende de otra que no esté integrada, y todas son idempotentes (D7).
2. **Cada una se copia idéntica al final de `dump_completo.sql`.** Si dos ramas
   agregan migraciones a la vez, chocan ahí. Se conservan los dos bloques, en el
   orden en que se integran.
3. **El bloque usa los números de su fila.** Si se le acaban, pide el siguiente al
   líder y se agrega a esta tabla antes de crear el archivo.

## Cómo ejecutarlas

Con la base ya creada:

```bash
for f in $(ls migraciones/0*.sql | sort); do
  psql -v ON_ERROR_STOP=1 -f "$f" || break
done
```

Con Docker Compose, montar la carpeta en el directorio de inicialización de la
imagen oficial. Postgres ejecuta los archivos en orden alfabético la primera vez
que arranca con un volumen vacío:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: simulador
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./Datos/postgres/migraciones:/docker-entrypoint-initdb.d:ro
      - pgdata:/var/lib/postgresql/data
```

Ojo: `/docker-entrypoint-initdb.d` solo corre con el volumen vacío. Para aplicar
una migración nueva sobre una base existente, ejecútenla con `psql` a mano.

## Reglas de trabajo

**Nunca editen un archivo ya aplicado.** Si algo cambia, se agrega un archivo
nuevo con el número siguiente. Editar el 004 después de que tres personas lo
corrieron deja tres bases distintas que parecen iguales.

**Todos los archivos son idempotentes.** Se pueden volver a correr sin error, lo
que permite reconstruir una base local sin borrar nada. Está probado.

**Una transacción por archivo.** Si algo falla a la mitad, no queda un esquema
a medias.

## Verificación

Estas migraciones se ejecutaron contra PostgreSQL 16.15 y producen:

- 22 tablas (21 del modelo más `schema_migrations`)
- 33 llaves foráneas
- 67 restricciones `CHECK`
- 72 índices
- 4 triggers
- 205 comentarios de documentación

Se validaron dos veces seguidas para confirmar idempotencia, y se probaron 15
casos negativos que las restricciones deben rechazar: correos con mayúsculas,
casos reportados antes del inicio de síntomas, dosis aplicadas mayores que las
del lote, dos versiones vigentes del mismo escenario, corridas completadas sin
fecha de término, intentos de modificar la bitácora, y demás. Los 15 fallan como
se espera.

## Pendientes

- **Contraseña del administrador inicial.** `010` inserta el usuario `admin` con
  un hash marcador que no permite autenticarse. Hay que generarlo y sustituirlo
  antes de la demostración.
- **Contraseñas de los roles de servicio.** `009` las crea con un marcador. En
  Compute Engine se generan aparte y se inyectan desde Secret Manager.
- **AGEB.** `010` carga estado y los diez municipios del área metropolitana. Las
  AGEB son miles y se cargan con un script aparte desde el marco geoestadístico
  del INEGI.
- **Parámetros de enfermedad.** Los de `010` son valores de literatura sin
  calibrar. La calibración contra la ola histórica los sustituye.
- **Particionamiento.** Si `audit_log` o `simulation_runs` crecen mucho durante
  las pruebas de carga, evaluar partición por rango de fecha.

## Aplicar migraciones a una base que ya existe

`infra/postgres/10-inicializa.sh` solo corre la primera vez, con el volumen vacío. A una base que
ya existe (la de la máquina de GCP, o la del compose en tu PC) las migraciones nuevas se le aplican
con `infra/aplica_migraciones.sh`, que primero la respalda:

```bash
sudo bash infra/aplica_migraciones.sh 050 051 052 053 054 055
```

La base de la máquina se creó el 2026-11-20 con el dump de entonces: le faltan las 050 a 055 del
bloque E. Se aplican **antes** de desplegar ese código, porque `corridas` ya escribe `priority`
(054), `auth` y `sesiones` usan `session_devices` y el MFA (050 y 051) y `usuarios` lee
`institution_id` (052). La base de pruebas de tu PC se rehace con
`python datos/scripts/prepara_base_pruebas.py`.
