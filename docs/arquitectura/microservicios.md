# EPIDEMIA — Catálogo de microservicios (propuesta)

Son **26 microservicios** pequeños, cada uno con una sola tarea, más una **consola** web para
probarlos. Los usan **solo las apps de escritorio (XML) y móvil (JSON)**. El sistema web, que
es el monolito, sigue hablando directo con PostgreSQL y no los consume.

Esta propuesta parte de los siete servicios de `arquitectura_v1.md` y los divide en tareas
específicas. Sin MongoDB, Cloud Storage ni nginx.

## Reglas comunes

- **Una tarea por servicio.** Si la descripción necesita un "y además", probablemente son
  dos servicios.
- **JSON y XML en todos.** Responden XML por defecto y JSON con `?format=json`, como en
  clase, o con la cabecera `Accept: application/json`; si los dos chocan, manda `?format`.
  Aceptan cuerpos en los dos formatos según el `Content-Type`. Cuando un servicio llama a
  otro, también puede pedir cualquiera de los dos.
- **Un dueño por tabla.** Solo un servicio escribe en cada tabla o columna. Los demás la
  leen, y su rol de PostgreSQL no tiene permiso para escribirla. Las excepciones están
  anotadas abajo.
- **`audit_log` es de todos, pero solo para insertar.** Cada escritura se audita en la misma
  transacción, con `log_audit(..., cur=cur)`, como hoy.
- **Un contenedor por servicio.** Todos parten de la misma imagen base, escuchan en el puerto
  8000 dentro de su contenedor y publican un puerto propio hacia fuera, según la tabla.
- **La lógica no se reescribe.** Los servicios importan `backend_web`, cuya capa de datos ya
  no depende de Flask, y el motor de `procesamiento/`. Al construir la API de un dominio, ese
  dominio sale de `queries.py` a su propio módulo, con `queries.py` como fachada (LIMP-11e).

## Esquema de puertos

| Dominio    | Puertos   |
|------------|-----------|
| Identidad  | 5201–5204 |
| Catálogos  | 5211–5215 |
| Vigilancia | 5221–5222 |
| Escenarios | 5231–5235 |
| Simulación | 5241–5245 |
| Analítica  | 5251–5253 |
| Plataforma | 5260–5262 |

Fuera de este esquema quedan el monolito (5000), PostgreSQL (5432) y Redis (6379 en la red
de Docker; en tu máquina, `127.0.0.1:6380`, para no chocar con Memurai).

---

## Identidad y acceso

| # | Servicio   | Hace una cosa                                    | Rutas principales                                                                                                                       | Escribe                                    | Lee                                                | Llama a                                               | Puerto |
|---|------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------------------------------------------------|-------------------------------------------------------|--------|
| 1 | `auth`     | Inicia sesión y emite el *access* y el *refresh* | `POST /api/v1/auth/login`                                                                                                               | `users` (intentos fallidos, último acceso) | `users`, `roles`, `user_roles`                     | Redis (abre la sesión)                                | 5201   |
| 2 | `sesiones` | Renueva, cierra y revoca sesiones                | `POST /api/v1/sessions/refresh`, `POST /api/v1/sessions/logout`, `GET /api/v1/sessions/current`, `DELETE /api/v1/sessions/user/{id}`    | —                                          | —                                                  | Redis                                                 | 5202   |
| 3 | `usuarios` | Administra cuentas                               | `GET/POST /api/v1/users`, `GET/PUT /api/v1/users/{id}`, `POST /api/v1/users/{id}/activate` y `/deactivate`, `DELETE /api/v1/users/{id}` | `users`                                    | `user_roles` y las tablas que hacen de dependencia | `sesiones`, para cerrar las de una cuenta desactivada | 5203   |
| 4 | `roles`    | Consulta roles y permisos, y los asigna          | `GET /api/v1/roles`, `GET /api/v1/roles/{id}/permissions`, `PUT /api/v1/roles/assignments/{user_id}`                                    | `user_roles`                               | `roles`, `permissions`, `role_permissions`         | `sesiones`, para cerrar sesiones al quitar un rol     | 5204   |

## Catálogos

| # | Servicio             | Hace una cosa                                                       | Rutas principales                                                                                 | Escribe                                                                    | Lee                            | Llama a | Puerto |
|---|----------------------|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|--------------------------------|---------|--------|
| 5 | `enfermedades`       | Alta, edición y baja lógica de enfermedades                         | `GET/POST /api/v1/diseases`, `GET/PUT /api/v1/diseases/{id}`, `POST .../activate` y `/deactivate` | `diseases` (todo menos `default_params`)                                   | `cases` (para la actividad)    | —       | 5211   |
| 6 | `parametros`         | Parámetros epidemiológicos, cada uno con fuente o marca de supuesto | `GET/PUT /api/v1/diseases/{id}/parameters`, `GET /api/v1/diseases/{id}/parameters/status`         | `diseases.default_params`                                                  | `diseases`                     | —       | 5212   |
| 7 | `regiones`           | Nuevo León y sus 51 municipios, solo lectura                        | `GET /api/v1/regions`, `GET /api/v1/regions/{id}`                                                 | —                                                                          | `regions`, `region_age_groups` | —       | 5213   |
| 8 | `poblacion`          | Población y bandas de edad, con sus correcciones                    | `GET/PUT /api/v1/regions/{id}/population`, `GET/PUT /api/v1/regions/{id}/age-groups`              | `regions.population`, `region_age_groups`, `region_population_adjustments` | `regions`                      | —       | 5214   |
| 9 | `tipos-intervencion` | Tipos de intervención con el esquema de sus parámetros              | `GET /api/v1/intervention-types`, `GET /api/v1/intervention-types/{code}`                         | —                                                                          | `intervention_types`           | —       | 5215   |

## Vigilancia

| #  | Servicio         | Hace una cosa                                                 | Rutas principales                                                   | Escribe                           | Lee                   | Llama a                        | Puerto |
|----|------------------|---------------------------------------------------------------|---------------------------------------------------------------------|-----------------------------------|-----------------------|--------------------------------|--------|
| 10 | `casos`          | Registra y consulta casos                                     | `POST /api/v1/cases`, `GET /api/v1/cases`, `GET /api/v1/cases/{id}` | `cases`                           | `diseases`, `regions` | —                              | 5221   |
| 11 | `sincronizacion` | Recibe lotes de casos capturados sin conexión en la app móvil | `POST /api/v1/sync/cases`, `GET /api/v1/sync/batches/{id}`          | — (los casos los escribe `casos`) | —                     | `casos`, uno por caso, en JSON | 5222   |

- `sincronizacion` usa Redis para que el mismo lote enviado dos veces no duplique casos
  (`sync:lote:<id>`). Regresa el resultado de cada caso: creado, duplicado o rechazado con su
  error.

## Escenarios

| #  | Servicio         | Hace una cosa                                                       | Rutas principales                                                                                                                               | Escribe                                                      | Lee                                                        | Llama a                                                                         | Puerto |
|----|------------------|---------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|------------------------------------------------------------|---------------------------------------------------------------------------------|--------|
| 12 | `escenarios`     | Alta, versiones nuevas, historial y duplicado                       | `GET/POST /api/v1/scenarios`, `GET /api/v1/scenarios/{id}`, `GET/POST /api/v1/scenarios/{id}/versions`, `POST /api/v1/scenarios/{id}/duplicate` | `scenarios`, `scenario_versions` (alta y contenido)          | `diseases`, `regions`, `region_age_groups`                 | `validacion`                                                                    | 5231   |
| 13 | `intervenciones` | Intervenciones de una versión en borrador                           | `GET/POST /api/v1/versions/{id}/interventions`, `DELETE .../{iid}`, `POST .../{iid}/move`, `PUT .../{iid}/cost`                                 | `scenario_interventions`                                     | `scenario_versions`, `intervention_types`                  | —                                                                               | 5232   |
| 14 | `aprobacion`     | Envío a revisión, aprobación y rechazo                              | `POST /api/v1/scenarios/{id}/submit`, `POST /api/v1/scenarios/{id}/review`, `GET /api/v1/reviews/pending`                                       | `scenario_versions` (solo las columnas de estado y revisión) | `scenarios`, `scenario_interventions`                      | `validacion`; `notificaciones` al aprobar                                       | 5233   |
| 15 | `validacion`     | Revisa un escenario contra el motor; no guarda nada                 | `POST /api/v1/validate`, `GET /api/v1/versions/{id}/validation`                                                                                 | —                                                            | `scenario_versions`, `diseases`                            | —                                                                               | 5234   |
| 16 | `escenarios-xml` | Exporta e importa escenarios completos en XML, validados contra XSD | `GET /api/v1/scenarios/{id}/export`, `POST /api/v1/scenarios/import`, `GET /api/v1/schemas/scenario.xsd`                                        | —                                                            | `scenarios`, `scenario_versions`, `scenario_interventions` | `validacion`; `escenarios` (le manda el escenario **en XML**); `intervenciones` | 5235   |

## Simulación

| #  | Servicio      | Hace una cosa                                                   | Rutas principales                                                                                                           | Escribe                                                      | Lee                                     | Llama a                                                 | Puerto |
|----|---------------|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|-----------------------------------------|---------------------------------------------------------|--------|
| 17 | `corridas`    | Lanza, cancela y consulta corridas                              | `POST /api/v1/runs` (202), `GET /api/v1/runs`, `GET /api/v1/runs/{id}` (estado y progreso), `POST /api/v1/runs/{id}/cancel` | `simulation_batches`, `simulation_runs` (alta y cancelación) | `scenario_versions`                     | Redis: encola la corrida y toma el candado              | 5241   |
| 18 | `simulador`   | Proceso trabajador: toma corridas de la cola y ejecuta el motor | `GET /api/v1/worker/status` (más `/health`)                                                                                 | `simulation_runs` (estado), `simulation_results`             | escenarios y enfermedades               | Redis (progreso); `notificaciones` al terminar o fallar | 5242   |
| 19 | `resultados`  | Curvas e indicadores de una corrida                             | `GET /api/v1/runs/{id}/results`, `.../curves`, `.../indicators`                                                             | —                                                            | `simulation_results`, `simulation_runs` | Redis (caché)                                           | 5243   |
| 20 | `comparacion` | Compara corridas lado a lado                                    | `GET /api/v1/comparisons?runs=a,b,c`                                                                                        | —                                                            | `simulation_runs`, `simulation_results` | —                                                       | 5244   |
| 21 | `pareto`      | Costo contra impacto y frontera de Pareto                       | `GET /api/v1/pareto?runs=a,b,c`                                                                                             | —                                                            | `scenario_interventions` (costos)       | `resultados` (indicadores, en JSON)                     | 5245   |

- Excepción a "un dueño por tabla": `simulation_runs.status` lo cambian `corridas` (para
  cancelar una encolada) y `simulador` (para ejecutarla). Las dos usan la transición
  condicionada de hoy (`WHERE status = ...`), así que no se pisan.
- Al arrancar, `simulador` cierra como fallidas las corridas que quedaron a medias (hoy es
  `recupera_corridas_interrumpidas`).

## Analítica

| #  | Servicio      | Hace una cosa                                      | Rutas principales                                                     | Escribe | Lee                                   | Llama a       | Puerto |
|----|---------------|----------------------------------------------------|-----------------------------------------------------------------------|---------|---------------------------------------|---------------|--------|
| 22 | `indicadores` | Indicadores del tablero y situación por enfermedad | `GET /api/v1/dashboard/indicators`, `GET /api/v1/dashboard/situation` | —       | `cases`, `regions`, `simulation_runs` | Redis (caché) | 5251   |
| 23 | `series`      | Curva epidémica y series por edad y sexo           | `GET /api/v1/series/cases`, `.../by-age`, `.../by-sex`, `.../totals`  | —       | `cases`                               | Redis (caché) | 5252   |
| 24 | `zonas`       | Mapa por municipio y detalle por zona              | `GET /api/v1/zones`, `GET /api/v1/zones/map`                          | —       | `cases`, `regions`                    | Redis (caché) | 5253   |

## Plataforma

| #  | Servicio           | Hace una cosa                                  | Rutas principales                                                                                                              | Escribe         | Lee | Llama a                                  | Puerto |
|----|--------------------|------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|-----------------|-----|------------------------------------------|--------|
| 25 | `notificaciones`   | Avisos para las apps                           | `GET /api/v1/notifications`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications` (solo con token de servicio) | `notifications` | —   | —                                        | 5261   |
| 26 | `estado-servicios` | Lista de servicios y sondeo de su salud        | `GET /api/v1/services`, `GET /api/v1/services/health`, `GET /api/v1/services/{nombre}/history`                                 | —               | —   | El `/health` de los otros 25, **en XML** | 5262   |
| —  | `consola`          | Página tipo Swagger/Postman para probar los 26 | —                                                                                                                              | —               | —   | Todos, desde el navegador                | 5260   |

- `estado-servicios` también es el directorio: las apps y la consola le preguntan la URL de
  cada servicio en vez de tenerlas escritas a mano. No hay pasarela; es la única forma de
  encontrarlos.

---

## Quién llama a quién

```
app móvil (JSON) ─┐                 ┌── consola (navegador)
app escritorio ───┤  token Bearer   │
(XML)             ▼                 ▼
   auth ──► Redis ◄── sesiones ◄── usuarios, roles   (cerrar sesiones)

   escenarios ──JSON──► validacion ◄──JSON── aprobacion ──► notificaciones
        ▲                    ▲
        └──XML── escenarios-xml ──► intervenciones

   corridas ──cola Redis──► simulador ──► notificaciones
                               │
                     resultados ◄── pareto
   sincronizacion ──JSON (un caso a la vez)──► casos

   estado-servicios ──XML──► /health de los 25 restantes
```

Las llamadas entre servicios llevan el **token de la persona** y el `X-Correlation-ID`.
Cuando no hay persona detrás (el `simulador` avisando que terminó, o `estado-servicios`
sondeando), usan un **token de servicio**: dura poco, tiene su propia audiencia y solo lo
aceptan las rutas marcadas como internas.

## Llaves de Redis por servicio

Los nombres salen de `microservicios/comun/epidemia_comun/llaves.py`, y una prueba revisa que
coincidan con esta tabla. Todas llevan TTL, salvo la cola. Del `sid` y del *refresh* solo se
guarda su huella (SHA-256).

| Llave                       | Qué guarda                                                                        | TTL                                                                | Escribe                                        | Módulo     |
|-----------------------------|-----------------------------------------------------------------------------------|--------------------------------------------------------------------|------------------------------------------------|------------|
| `session:<h(sid)>`          | Hash: usuario, roles, creada, expira y la huella del *refresh* vigente            | La sesión, contada desde el login; renovar no la alarga            | `auth`, `sesiones`                             | `sesiones` |
| `user:<id>:sessions`        | Conjunto con las huellas de las sesiones de una cuenta                            | La sesión                                                          | `auth`, `sesiones`                             | `sesiones` |
| `refresh:<h(rt)>`           | Huella del `sid` de su sesión                                                     | Lo que le quede a la sesión                                        | `auth`, `sesiones`                             | `sesiones` |
| `refresh:usado:<h(rt)>`     | Huella del `sid` de un *refresh* ya rotado, para detectar si alguien lo reutiliza | Lo que le quede a la sesión                                        | `sesiones`                                     | `sesiones` |
| `jwt:revoked:<jti>`         | `1`                                                                               | Lo que le quede al token, más 60 s                                 | `sesiones`                                     | `sesiones` |
| `captcha:<id>`              | La respuesta esperada de un captcha de inicio de sesión                           | 5 min; se borra al usarlo, así que sirve para un solo intento      | `auth`                                         | —          |
| `queue:simulaciones`        | Lista de ids de corrida                                                           | **Sin TTL**: la vacía el `simulador`, y lo que manda es PostgreSQL | `corridas`                                     | `cola`     |
| `lock:corrida:<version>`    | Marca de la petición que lo tomó                                                  | Unos segundos                                                      | `corridas`                                     | `candados` |
| `job:<id>:progress`         | Avance de una corrida                                                             | Lo fija el `simulador`                                             | `simulador`                                    | —          |
| `cache:<servicio>:<clave>`  | La respuesta, en JSON                                                             | Corto; lo fija cada servicio                                       | `resultados`, `indicadores`, `series`, `zonas` | `cache`    |
| `sync:lote:<id>`            | Resultado de un lote ya recibido                                                  | Lo fija `sincronizacion`                                           | `sincronizacion`                               | —          |
| `health:<servicio>`         | Última salud de un servicio                                                       | Lo fija `estado-servicios`                                         | `estado-servicios`                             | —          |
| `health:history:<servicio>` | Lista corta de sondeos                                                            | Lo fija `estado-servicios`                                         | `estado-servicios`                             | —          |

- Todas las rutas protegidas leen `session:` y `jwt:revoked:` desde `@requiere_token`
  (`seguridad.py`), con la misma regla que `sesiones.verificar()`.
- Las llaves sin módulo se escriben con `requerido()` u `opcional()` de `redis_compartido`,
  siempre con `ex=`. Quien implemente el servicio anota aquí el TTL que eligió.
- Toda llave sale de `llaves.py`, también en la biblioteca. Una prueba busca llaves armadas a
  mano (`"captcha:" + x` o `f"captcha:{x}"`) fuera de ese archivo.

## Opcionales (si sobra tiempo o las apps los piden)

| Servicio        | Hace una cosa                                                        | Tabla que ya existe |
|-----------------|----------------------------------------------------------------------|---------------------|
| `recuperacion`  | Restablecer contraseña; el envío del correo queda fuera de alcance   | `password_resets`   |
| `dispositivos`  | Registro y revocación de los dispositivos móviles                    | `devices`           |
| `evidencias`    | Adjuntos de casos en un volumen de Docker, en lugar de Cloud Storage | `case_attachments`  |
| `vacunas`       | Lotes de vacunas escaneados y el consumo de dosis                    | `vaccine_lots`      |
| `configuracion` | Ajustes del sistema que leen las apps                                | `system_settings`   |
