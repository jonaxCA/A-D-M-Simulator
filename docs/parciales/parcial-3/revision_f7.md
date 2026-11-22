# Revisión de los servicios del bloque F contra la retroalimentación (F7)

Revisado el 2026-11-21 contra [`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`](RETROALIMENTACION_SEGUNDO_PARCIAL.txt)
(servicios 10, 11 y 22 a 26, y la parte de Android sobre formularios), con el código de
`feat/tercer-parcial` (`a6bc5f2`). Los servicios del bloque F son `casos`, `sincronizacion`,
`dispositivos`, `vacunas`, `indicadores`, `series`, `zonas`, `notificaciones` y
`estado-servicios` («Dueños de los servicios» del [checklist](checklist.md)).

**Cumple** = hay ruta y prueba. **Parcial** = una parte, o solo de lectura. **Falta** = no existe.
Lo que se cerró después de la revisión dice **Hecho**, con su fecha.

## Vigilancia

### `casos` (5221)

> Registro, actualización y seguimiento de casos ficticios o autorizados; clasificación, fecha
> epidemiológica, región, estado, duplicados, validaciones y trazabilidad.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Registro | **Cumple** | `POST /cases` y, para la móvil, `POST /cases/batch` (F4). Solo CAPTURISTA (D1) |
| Actualización | Falta | No hay `PUT`/`PATCH`: un caso no se corrige después de capturarlo |
| Seguimiento | Falta | `status` (`pendiente`, `validado`, `duplicado`, `descartado`) existe, pero ninguna ruta lo cambia |
| Clasificación | Parcial | `test_result` y `severity`; no hay clasificación formal (sospechoso, probable, confirmado) |
| Fecha epidemiológica | Parcial | `onset_date` y `report_date`, validadas; falta la semana epidemiológica |
| Región | **Cumple** | `region_id` (municipio), filtrable en `GET /cases` |
| Estado | Parcial | Se lee y se filtra; no se cambia (ver seguimiento) |
| Duplicados | Parcial | Idempotencia por `local_uuid` (un reintento no duplica); no se detectan duplicados probables (misma persona, otro dispositivo) |
| Validaciones | **Cumple** | `queries.valida_caso`: catálogos vigentes, fechas, rangos, coordenadas; 422 con el motivo |
| Trazabilidad | Parcial | `reported_by`, `device_id`, `synced_at` y `CREATE` en la bitácora; sin historial de cambios, porque no hay cambios |

### `sincronizacion` (5222)

> Sincronización Android offline, identificadores únicos, operaciones pendientes, reintentos,
> control de duplicados, conflictos y confirmación de recepción por servidor.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Identificadores únicos | **Cumple** | `batch_id` del lote y `local_uuid` de cada caso |
| Operaciones pendientes | **Cumple** | La cola es de la app (WorkManager); el servidor recuerda cada lote 7 días |
| Reintentos | **Cumple** | Reenviar el mismo lote regresa lo guardado; 503 y 429 (con `Retry-After`) se reintentan |
| Control de duplicados | **Cumple** | `local_uuid` en `casos` y el lote repetido |
| Conflictos | Parcial | Dos envíos del mismo lote a la vez dan 409 (candado); falta el conflicto entre lo editado sin conexión y lo que cambió otro profesional, que necesita que `casos` tenga actualización |
| Confirmación de recepción | **Cumple** | Resultado por caso (`creado`, `duplicado`, `rechazado`) y `GET /sync/batches/{id}` |

### Formularios dinámicos por enfermedad

> Campos definidos por enfermedad, versiones de formularios, validaciones y datos obligatorios
> (parte de Android; B4 lo espera).

**Falta.** Los campos de un caso son fijos. Hace falta una tabla de formularios por enfermedad con
versiones, una ruta que la app consulte y que `casos` valide contra la versión con que se capturó.

### `dispositivos` (5223) y `vacunas` (5225) (D27)

No vienen en la lista de 26 servicios: entraron con D27 para la móvil.

- `dispositivos`: registrar, listar y revocar el teléfono que sincroniza; `casos` rechaza uno revocado. **Cumple** lo de D27. Ojo: D41 (bloque E) creó aparte los dispositivos de **sesión**; falta decidir si se unen.
- `vacunas`: lotes y dosis aplicadas. Se acerca al servicio opcional 32 (`vacunacion`: campañas, coberturas, poblaciones objetivo), que no está en el alcance; las **campañas** tampoco existen, y `notificaciones` las pide.

## Analítica

### `indicadores` (5251)

> Incidencia, prevalencia cuando aplique, mortalidad, hospitalizaciones, capacidad utilizada y
> otros indicadores definidos con numerador, denominador y periodo.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Incidencia | **Cumple** | Tasa por 100 000 habitantes de la semana, contra la previa (`/dashboard/indicators`) |
| Prevalencia | Falta | Casos activos sí; prevalencia como tasa, no |
| Mortalidad | **Hecho** (2026-11-21) | `tasa_mortalidad` (fallecidos por 100 000 habitantes, contra la semana previa) y `letalidad` (% de los casos) |
| Hospitalizaciones | Parcial | No hay un dato de hospitalización; desde el 2026-11-21, `casos_graves` (% con gravedad `grave`) es lo más cercano |
| Capacidad utilizada | Falta | No hay fuente de capacidad (es el servicio opcional 31) |
| Numerador, denominador y periodo | **Hecho** (2026-11-21) | `indicadores` en `/dashboard/indicators`: cada uno con `numerador`, `denominador`, `factor`, `periodo` (fechas), la semana previa y la variación |

### `series` (5252)

> Series temporales por enfermedad, periodo, región y grupo; filtrado, paginación,
> agregaciones y formatos para Highcharts.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Por enfermedad, periodo y región | **Cumple** | `disease_id`, `region_id` y `days` (7, 30 o 90) |
| Por grupo | Parcial | Rutas aparte por edad y por sexo; no se combinan con la serie diaria |
| Filtrado | Parcial | `days` acepta solo 7, 30 o 90; no hay rango de fechas libre |
| Paginación | Falta | |
| Agregaciones | Falta | Solo por día; ni por semana epidemiológica ni por mes |
| Formato para Highcharts | Falta | Listas de filas; Highcharts espera `series: [{name, data: [[x, y]]}]` |

### `zonas` (5253)

> Mapas temáticos, indicadores geoespaciales, agrupaciones territoriales, datos para mapas de
> calor y consultas espaciales optimizadas.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Mapas temáticos | **Cumple** | `/zones/map`: incidencia y semáforo por municipio, con la línea de tiempo |
| Indicadores geoespaciales | **Cumple** | Casos, incidencia, variación a 7 días y graves por municipio (`/zones`) |
| Agrupaciones territoriales | Falta | Solo municipios; no por jurisdicción sanitaria o región del estado |
| Datos para mapas de calor | Falta | Los casos traen latitud y longitud, pero no hay ruta que las agregue |
| Consultas espaciales optimizadas | Falta | Sin índice espacial (PostGIS) ni consultas por área |
| Geometría oficial de los municipios | Falta | El mapa del escritorio (A4) dibuja marcadores; necesita los polígonos y su fuente |

## Plataforma

### `notificaciones` (5261)

> Avisos de campañas, datos incompletos, escenarios por aprobar, corridas terminadas, errores
> operativos y alertas configurables por perfil.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Escenarios por aprobar | **Cumple** | `SCENARIO_SUBMITTED` a los EPIDEMIOLOGO (y aprobado o rechazado al autor) |
| Corridas terminadas | **Cumple** | `RUN_FINISHED` y `RUN_FAILED` a quien la pidió |
| Casos nuevos | **Cumple** | `NEW_CASES` a los EPIDEMIOLOGO, una vez por lote (D32) |
| Errores operativos | **Hecho** (2026-11-21) | `estado-servicios` manda `SYSTEM` a los ADMINISTRADOR cuando un servicio cae, se degrada o se recupera (ver «Alertas técnicas») |
| Datos incompletos | Falta | |
| Campañas | Falta | No hay campañas (ver `vacunas`) |
| Alertas configurables por perfil | Parcial | Se puede avisar a un rol (EPIDEMIOLOGO y, desde el 2026-11-21, ADMINISTRADOR); no hay preferencias por perfil. `THRESHOLD_EXCEEDED` existe sin uso |

### `estado-servicios` (5262)

> Estado de APIs, bases de datos, simulador, colas, tiempos de respuesta, capacidad de
> procesamiento, errores y alertas técnicas.

| Pide | Estado | Cómo, o qué falta |
|---|---|---|
| Estado de las APIs | **Cumple** | Sondea el `/health` de los 29 servicios; directorio y panel (consola) |
| Bases de datos | **Cumple** | PostgreSQL, Redis, MongoDB y el bucket como causas (`degradado`) |
| Simulador | **Hecho** (2026-11-21) | Se sondean como servicios y, además, cada simulador renueva un latido en Redis cada 10 s mientras su trabajador corre (`worker:<motor>:<simulador>`, TTL de 30 s); cuenta también el de `abm-gpu` de la PC con GPU |
| Colas | **Hecho** (2026-11-21) | `GET /services/capacity`: corridas en cola por motor y por prioridad (`queue:simulaciones:<motor>`, `:alta` y `:baja`, D44) |
| Tiempos de respuesta | **Cumple** | `latencia_ms` de cada sondeo, con historial de 30 días en MongoDB |
| Capacidad de procesamiento | **Hecho** (2026-11-21) | En la misma ruta: simuladores vivos, ocupados y libres por motor, con la corrida de cada uno |
| Errores | **Cumple** | 5xx de las últimas 24 h por servicio (`errores`) |
| Alertas técnicas | **Hecho** (2026-11-21) | `SYSTEM` a los ADMINISTRADOR por `notificaciones` cuando un servicio cambia de estado durante 30 s; un aviso por ronda, sin repetir, y lo que no se pudo entregar (Redis o PostgreSQL caídos) llega cuando vuelven |

## Lo que cruza a todos

- **E8:** `casos`, `sincronizacion`, `dispositivos`, `vacunas`, `indicadores`, `series`, `zonas` y
  `notificaciones` todavía importan `backend_web`. Es el siguiente paso de E8 para el bloque F.
- **D42 y D43 (bloque E):** los perfiles INVESTIGADOR y AUTORIDAD_SANITARIA no están en los candados
  de las rutas de lectura de F, y el alcance por región no filtra casos, series, zonas ni
  indicadores. Las dos decisiones esperan la validación del líder.
- **«Ninguna aplicación cliente se conecta a la base»:** la web todavía lee PostgreSQL para su
  tablero y su mapa (D36, bloque C), aunque `indicadores`, `series` y `zonas` ya dan esos datos.

## Qué sigue, por tamaño

| Tamaño | Qué | Servicio |
|---|---|---|
| ~~Chico~~ | **Hecho** el 2026-11-21: cola, ejecutando y simuladores vivos por motor (`/services/capacity`) | `estado-servicios` y `simulador` |
| ~~Chico~~ | **Hecho** el 2026-11-21: avisar con `SYSTEM` a los ADMINISTRADOR cuando un servicio cae o se recupera (alertas técnicas y errores operativos) | `estado-servicios` y `notificaciones` |
| ~~Chico~~ | **Hecho** el 2026-11-21: numerador, denominador y periodo en cada indicador; mortalidad, letalidad y casos graves | `indicadores` |
| Mediano | Agregación por semana o mes, paginación y salida para Highcharts | `series` |
| Mediano | Puntos agregados para el mapa de calor y agrupación por región del estado | `zonas` |
| Mediano | Cambiar estado (validar, descartar, marcar duplicado) y corregir datos, con historial y control de versión (`If-Match`); con eso, los conflictos de la sincronización | `casos` y `sincronizacion` |
| Grande | Formularios por enfermedad con versiones | `casos` (y la móvil, B4) |
| Grande | Geometría oficial de los municipios y consultas espaciales | `zonas` |
| Grande | Campañas, avisos de datos incompletos y preferencias por perfil | `notificaciones` y `vacunas` |
| Transversal | Dejar de importar `backend_web` (E8), los perfiles nuevos y el alcance (D42, D43) | los nueve |
