# Arquitectura y stack tecnológico — v2
 
La v2 reemplaza a la v1: el sistema web es un monolito que habla directo con PostgreSQL, y 26 microservicios pequeños (más una consola de pruebas) atienden solo a las apps de escritorio y móvil. Se basa en `docs/arquitectura/microservicios.md`, `docs/decisiones/decisiones.md` (D9 a D16) y `docs/CHECKLIST_SEGUNDO_PARCIAL.md` del repositorio A-D-M-Simulator, revisados el 23 de octubre de 2026.
 
Si este documento y el catálogo `microservicios.md` no coinciden, manda el catálogo. Si el catálogo y el código no coinciden, manda el código.
 
## Qué cambió respecto al v1
 
| Tema                    | v1                                                       | v2                                                                                             |
| ---                     | ---                                                      | ---                                                                                            |
| Sistema web             | Cliente más de los microservicios, sin acceso a la base  | Monolito Flask con acceso directo a PostgreSQL; no llama a los microservicios                  |
| Microservicios          | 7 servicios grandes (`auth-service`, `catalog-service`…) | 26 servicios de una sola tarea, con nombres en español, más la `consola`                       |
| Quién usa los servicios | Web, Android y escritorio                                | Solo Android (JSON) y escritorio (XML); la consola los sustituye hasta el tercer parcial       |
| Puerta de entrada       | Nginx con TLS y enrutamiento                             | Sin pasarela: cada servicio publica su puerto y `estado-servicios` funciona como directorio    |
| Formato                 | Según la cabecera `Accept`                               | XML por defecto; JSON con `?format=json` o `Accept: application/json`                          |
| Validación y Swagger    | marshmallow + flask-smorest                              | Contrato OpenAPI escrito a mano por servicio, Swagger en `/docs`, XSD validado con `xmlschema` |
| Errores                 | Cuerpo de error propio                                   | RFC 7807 (formato estándar de errores HTTP) en JSON y XML, con un `codigo` estable             |
| Salud                   | Seis rutas `/health/*`                                   | Una sola `/health` con el estado de PostgreSQL y Redis                                         |
| Acceso a datos          | Cada servicio con su almacenamiento                      | Una sola instancia de PostgreSQL, un rol por servicio (migración 026)                          |
| MongoDB y Cloud Storage | Resultados, eventos y archivos                           | Fuera de la etapa actual; los resultados viven en `simulation_results` (PostgreSQL)            |
| Motor acelerado         | C++20 + CUDA propio                                      | FLAME GPU 2                                                                                    |
| Motor actual            | Python + NumPy/Numba con agentes                         | SEIR por grupos de edad en Python + NumPy, sin agentes                                         |
 
## 1. Principios de diseño
 
Seis reglas explican por qué el sistema está armado así. Si hay duda sobre dónde poner algo, se resuelve con ellas.
 
**1. Las apps no tocan las bases de datos; la web sí.** La app móvil y la de escritorio solo hablan con los microservicios. El sistema web es la excepción: es un monolito que lee y escribe PostgreSQL directo. Para que la misma regla de negocio no quede escrita dos veces, web y servicios importan la misma capa de datos (`backend_web`).
 
**2. Una tarea por servicio.** Si la descripción de un servicio necesita un "y además", probablemente son dos servicios. Si `escenarios` se cae, la captura de casos sigue funcionando.
 
**3. Un dueño por tabla.** Solo un servicio escribe cada tabla o columna; los demás la leen. Lo impone PostgreSQL: cada servicio se conecta con su propio rol, y ese rol no tiene permiso de escribir lo ajeno. `audit_log` es la excepción: todos insertan, nadie edita.
 
**4. Lo lento va a una cola.** Una petición HTTP responde en segundos; una simulación puede tardar minutos. `corridas` encola el trabajo, responde 202 ("aceptado, en proceso") con el identificador, y el cliente consulta después.
 
**5. El motor está aislado.** `procesamiento/motor` no importa Flask ni toca la base: recibe un diccionario con el escenario y regresa otro con los resultados. Por eso se puede cambiar el SEIR actual por FLAME GPU 2 sin tocar nada más.
 
**6. PostgreSQL es la fuente de verdad.** Redis no guarda nada que no se pueda reconstruir. Si Redis se reinicia, la gente vuelve a iniciar sesión, las cachés se rellenan solas y la cola se recupera desde `simulation_runs`.
 
## 2. Vista general
 
&#91;embedded content: vista general · 4 clientes, 26 servicios en 7 dominios, motor, Redis y PostgreSQL\]
 
La web y los microservicios comparten la misma base y la misma capa de datos (`backend_web`), pero la web no llama a los servicios. Las apps y la consola nunca tocan PostgreSQL ni Redis.
 
## 3. Capa de clientes
 
Hay cuatro clientes: el sistema web, que va directo a la base, y la app Android, la de escritorio y la consola, que pasan por los microservicios.
 
### 3.1 Sistema web (monolito)
 
**Stack:** Python 3.9 o superior (los contenedores usan 3.12), Flask, Jinja2, HTML5, CSS3, JavaScript, Highcharts y Highcharts Maps. Corre en el puerto 5000.
 
Es el núcleo administrativo y funciona aunque los microservicios estén caídos. Está partido en dos carpetas:
 
- `frontend_web/`: rutas, plantillas, estáticos, sesión y decoradores de permisos. Aquí no se escribe SQL.
- `backend_web/`: la capa de datos (conexión, consultas, auditoría, credenciales y ejecución de corridas). Los microservicios la importan, así que una regla de negocio vive en un solo lugar.
**Acceso a datos:** se conecta a PostgreSQL con su propio rol, `epidemia_app`. Las migraciones de los servicios (026 en adelante) no le quitan permisos.
 
**Autenticación:** JWT firmado con `JWT_SECRET_KEY` y guardado en cookie. Hoy no consulta Redis; las sesiones de Redis son de las apps.
 
**Simulaciones:** la web lanza la corrida en un hilo de fondo (un segundo flujo de ejecución dentro del mismo proceso), responde de inmediato y la pantalla de detalle consulta el estado. Los estados son los mismos que usa `simulador`: `encolado`, `ejecutando`, `completado`, `fallido`, `cancelado`.
 
| Módulo                     | Contenido                                                                                           |
| ---                        | ---                                                                                                 |
| Sitio público              | Descripción del proyecto y tablero de indicadores agregados                                         |
| Tablero de control         | Curvas epidémicas con Highcharts, mapa por municipio de Nuevo León, indicadores del día             |
| Usuarios, roles y permisos | Cuatro roles: ADMINISTRADOR, EPIDEMIOLOGO, ANALISTA y CAPTURISTA                                    |
| Catálogos                  | Enfermedades, parámetros con fuente o marca de supuesto, regiones, población, tipos de intervención |
| Vigilancia                 | Captura y consulta de casos                                                                         |
| Escenarios                 | Alta, versiones, intervenciones, envío a revisión y aprobación                                      |
| Simulaciones               | Lanzar corridas sobre versiones aprobadas, ver resultados y comparar en la frontera de eficiencia   |
| Monitoreo y bitácora       | Estado del sistema y auditoría de quién hizo qué                                                    |
 
En este avance los escenarios se crean en la web. Cuánto de ese trabajo pasa a la app de escritorio sigue abierto (D4).
 
### 3.2 Aplicación Android
 
**Stack:** Kotlin, Retrofit (cliente HTTP), Room (base local en el teléfono), CameraX, ML Kit (lectura de QR y códigos de barras) y WorkManager (tareas en segundo plano que se reintentan). Se entrega en el tercer parcial.
 
Consume **solo JSON** y solo a través de los microservicios. Nunca toca PostgreSQL ni Redis.
 
| Función                                                       | Servicio que la atiende                                       |
| ---                                                           | ---                                                           |
| Inicio de sesión y renovación automática del token            | `auth`, `sesiones`                                            |
| Registro de casos con validación local y geolocalización      | `casos`                                                       |
| Modo sin conexión: cola en Room y envío posterior por lotes   | `sincronizacion`                                              |
| Consulta de catálogos e indicadores                           | `enfermedades`, `regiones`, `indicadores`, `zonas`            |
| Avisos                                                        | `notificaciones`                                              |
| Fotos de evidencia, lotes de vacuna y registro de dispositivo | Servicios opcionales `evidencias`, `vacunas` y `dispositivos` |
 
**Estrategia sin conexión:** cada caso se guarda primero en Room como `pendiente`, con un identificador generado en el teléfono. WorkManager lo reenvía cuando hay red. `sincronizacion` guarda el resultado de cada lote en Redis (`sync:lote:<id>`), así que un lote enviado dos veces no duplica casos.
 
### 3.3 Aplicación de escritorio
 
**Stack:** Python + PySide6. Se entrega en el tercer parcial.
 
Consume **solo XML**, el formato por defecto de los servicios. Valida su sesión a través de `sesiones`, que la consulta en Redis.
 
| Función                                             | Servicio que la atiende                                        |
| ---                                                 | ---                                                            |
| Editor de escenarios en XML, validado contra su XSD | `escenarios-xml`, `escenarios`, `intervenciones`, `validacion` |
| Revisión y aprobación                               | `aprobacion`                                                   |
| Lanzamiento de corridas por lotes                   | `corridas`                                                     |
| Comparador y frontera de eficiencia                 | `resultados`, `comparacion`, `pareto`                          |
| Mapa por municipio                                  | `zonas`                                                        |
 
**Por qué XML aquí:** un escenario es una estructura jerárquica (población, parámetros de la enfermedad, calendario de intervenciones). En simulación epidemiológica los archivos de configuración suelen ser XML, así que el requisito de la materia coincide con la práctica del área.
 
### 3.4 Consola de pruebas
 
Página web tipo Swagger/Postman en el puerto 5260. Sustituye a las apps mientras no existan y es la herramienta del guion de aceptación del segundo parcial.
 
- Panel de salud de los 26 servicios, leído de `estado-servicios`.
- Swagger UI con selector de los 26 contratos y "Try it out" funcionando.
- Inicio de sesión real contra `auth`; el token vive en la memoria de la página, no en `localStorage`.
- Probador: cuerpo en JSON o XML, respuesta en JSON o XML, con código, tiempo, cabeceras y `X-Correlation-ID`.
## 4. Capa de microservicios
 
Son 26 servicios Flask de una sola tarea, agrupados en siete dominios, más la `consola`. Cada uno corre en su contenedor, escucha en el puerto 8000 dentro de él y publica un puerto propio hacia fuera. El detalle de cada servicio (tablas que escribe y lee, a quién llama) está en `docs/arquitectura/microservicios.md`.
 
### 4.1 Catálogo
 
| Dominio    | Puertos   | Servicios                                                                    |
| ---        | ---       | ---                                                                          |
| Identidad  | 5201–5204 | `auth`, `sesiones`, `usuarios`, `roles`                                      |
| Catálogos  | 5211–5215 | `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion`  |
| Vigilancia | 5221–5222 | `casos`, `sincronizacion`                                                    |
| Escenarios | 5231–5235 | `escenarios`, `intervenciones`, `aprobacion`, `validacion`, `escenarios-xml` |
| Simulación | 5241–5245 | `corridas`, `simulador`, `resultados`, `comparacion`, `pareto`               |
| Analítica  | 5251–5253 | `indicadores`, `series`, `zonas`                                             |
| Plataforma | 5260–5262 | `consola` (5260), `notificaciones` (5261), `estado-servicios` (5262)         |
 
Fuera del esquema quedan el monolito (5000), PostgreSQL (5432) y Redis (6379 en la red de Docker; `127.0.0.1:6380` en la máquina de desarrollo, para no chocar con Memurai en Windows).
 
**Opcionales**, si sobra tiempo o las apps los piden: `recuperacion` (restablecer contraseña), `dispositivos`, `evidencias` (adjuntos en un volumen de Docker), `vacunas` y `configuracion`. Sus tablas ya existen.
 
### 4.2 Convenciones de todos los servicios
 
Lo que los 26 repiten vive una sola vez en la biblioteca común `epidemia_comun` (`microservicios/comun/`). Un servicio nuevo se genera con `scripts/nuevo_servicio.py <nombre> <puerto>`.
 
**Versionado.** Rutas en inglés bajo `/api/v1/` (por ejemplo, `/api/v1/scenarios`). Un cambio incompatible crea `/api/v2/` y `v1` sigue funcionando. Los nombres de los servicios van en español.
 
**Formato.** XML por defecto; JSON con `?format=json` o con `Accept: application/json`. Si los dos chocan, manda `?format`; un valor desconocido es 400. Los cuerpos se aceptan en JSON o XML según el `Content-Type`; el XML se lee con `defusedxml`, que bloquea ataques de entidades XML.
 
**Autenticación.** `@requiere_token(roles=...)` revisa en orden: la cabecera `Bearer`, que el algoritmo sea HS256 (rechaza `none`), la firma, `iss`, `aud`, `exp` y `nbf`, que la sesión siga abierta y el token no esté revocado en Redis, y el rol. Si Redis no responde, la ruta protegida responde 503 y nunca deja pasar.
 
**Errores.** Formato RFC 7807 (`application/problem+json` o `problem+xml`) con un `codigo` estable: `TOKEN_AUSENTE`, `TOKEN_INVALIDO`, `TOKEN_EXPIRADO`, `TOKEN_REVOCADO`, `PERMISO_INSUFICIENTE`, `CREDENCIALES_INVALIDAS`, `NO_ENCONTRADO`, `CONFLICTO`, `DATOS_INVALIDOS`, `SERVICIO_NO_DISPONIBLE` y `ERROR_INTERNO`. Un 500 no expone la traza ni el SQL.
 
| Código | Uso                                                                      |
| ---    | ---                                                                      |
| 400    | Datos mal formados o `?format` desconocido                               |
| 401    | Sin token, token inválido, vencido o revocado                            |
| 403    | Token válido, rol insuficiente                                           |
| 404    | Recurso inexistente                                                      |
| 409    | Conflicto (duplicado, versión desactualizada)                            |
| 415    | `Content-Type` que no es JSON ni XML                                     |
| 422    | Datos bien formados pero inválidos (por ejemplo, XML que no pasa su XSD) |
| 503    | Redis u otro servicio no disponible                                      |
| 500    | Error interno                                                            |
 
**Validación de entradas.** Cada ruta valida su cuerpo antes de tocar la lógica. Los recursos con XSD (error, enfermedad y sus parámetros, escenario, resultado de corrida, caso y lote de sincronización) se validan con `xmlschema`.
 
**Correlación y registro.** Cada petición lleva un `X-Correlation-ID`; si no viene, se genera. Se propaga a las llamadas internas y se registra con método, ruta, código, duración y usuario.
 
**Salud.** Una sola ruta `/health`, en XML o JSON, con el estado de PostgreSQL y Redis y la versión del servicio. Docker la usa como *healthcheck* (la prueba que hace el contenedor para saber si sigue sano).
 
**Documentación.** Cada servicio sirve su contrato en `/openapi.json` y Swagger UI en `/docs`. El mismo contrato vive en `docs/contratos/<servicio>/` con un ejemplo JSON y uno XML por ruta, y una prueba revisa que ambos sean idénticos.
 
**Datos.** Cada servicio se conecta a PostgreSQL con su rol de la migración 026 y solo puede escribir lo que el catálogo le asigna. Toda escritura se audita en `audit_log` dentro de la misma transacción. La lógica no se reescribe: los servicios importan `backend_web` y `procesamiento/motor`.
 
### 4.3 Comunicación entre servicios
 
No hay pasarela (un punto de entrada único como Nginx). Las apps y la consola le piden a `estado-servicios` la URL de cada servicio y lo llaman directo. Entre servicios se usa `llamar(...)` de la biblioteca común, en JSON o en XML.
 
- Cuando hay una persona detrás, se reenvía **su** token; nunca se cambia por uno con más permisos.
- Cuando no la hay (`simulador` avisando que terminó, `estado-servicios` sondeando), se usa un **token de servicio**: dura poco, tiene su propia audiencia (`epidemia-interno`) y solo lo aceptan las rutas marcadas con `@solo_servicios`.
- Un servicio caído se convierte en 503 `SERVICIO_NO_DISPONIBLE`, no en un 500.
- Hay dos llamadas en XML a propósito, para demostrar el formato entre servicios: `escenarios-xml` → `escenarios` y `estado-servicios` → `/health` de los demás.
### 4.4 Autenticación con JWT
 
| Pieza                           | Regla                                                                                     |
| ---                             | ---                                                                                       |
| Token de acceso (*access*)      | HS256, 20 minutos; claims `iss`, `aud`, `sub`, `roles`, `sid`, `jti`, `iat`, `nbf`, `exp` |
| Sesión                          | 8 horas desde el inicio de sesión; renovar no la alarga                                   |
| Token de renovación (*refresh*) | De un solo uso: reutilizar uno ya rotado cierra la sesión completa                        |
| Cierre de sesión                | `sesiones` marca el `jti` como revocado en Redis y borra la sesión                        |
| Captcha                         | `auth` lo emite y lo guarda en Redis 300 segundos                                         |
 
En Redis solo se guarda la huella SHA-256 (un resumen irreversible) del identificador de sesión y del *refresh*, nunca el valor.
 
### 4.5 Servicio de monitoreo
 
`estado-servicios` cumple el papel del `monitoring-service` del v1 y además es el directorio. Sondea el `/health` de los otros 25 en XML y expone la lista de servicios, su salud y su historial (`/api/v1/services`, `/services/health`, `/services/{nombre}/history`). Guarda la última salud y un historial corto en Redis (`health:<servicio>`, `health:history:<servicio>`).
 
**Estados:** *disponible* = `/health` responde 200 con PostgreSQL y Redis bien. *Degradado* = responde 200 pero una dependencia falla o el tiempo supera el umbral. *Caído* = no responde o responde error.
 
## 5. Capa de datos
 
En la etapa actual solo hay dos almacenes: PostgreSQL, que es la fuente de verdad, y Redis, para lo temporal. MongoDB y Google Cloud Storage salieron del catálogo de esta etapa (ver la sección 9).
 
### 5.1 PostgreSQL — datos transaccionales
 
Una sola instancia, compartida por el monolito y los 26 servicios. El esquema real son las migraciones numeradas de `datos/postgres/migraciones/` (001 a 026), no este documento.
 
```
users, roles, permissions, user_roles, role_permissions
password_resets, devices
diseases (con default_params), regions, region_age_groups,
  region_population_adjustments, intervention_types
cases, case_attachments, vaccine_lots
scenarios, scenario_versions, scenario_interventions
simulation_batches, simulation_runs, simulation_results
notifications, system_settings, audit_log
```
 
**Roles por servicio.** La migración 026 crea un rol de PostgreSQL por servicio, con permisos por tabla y, en `parametros`, `poblacion` y `aprobacion`, por columna. Cada servicio lee todo y escribe solo lo suyo; ninguno usa el usuario `postgres`. El monolito conserva su rol `epidemia_app`.
 
**Resultados de simulación.** Viven en `simulation_results`, en PostgreSQL, enlazados a `simulation_runs`. Los metadatos de la corrida (quién, cuándo, con qué versión y semilla) están en `simulation_runs`.
 
**Excepción a "un dueño por tabla".** `simulation_runs.status` lo cambian `corridas` (para cancelar una corrida encolada) y `simulador` (para ejecutarla). Las dos usan una actualización condicionada (`UPDATE ... WHERE status = ...`), así que no se pisan.
 
### 5.2 Redis — temporal y rápido
 
Redis 7.4 en Docker, con contraseña (`requirepass`), persistencia en disco (`appendonly yes`) y política `noeviction`: con la memoria llena rechaza escrituras en vez de borrar sesiones o revocaciones. Los nombres de las llaves salen de `epidemia_comun/llaves.py` y una prueba revisa que coincidan con esta tabla.
 
| Llave                                             | Qué guarda                                            | Duración (TTL)                  | La escribe                                     |
| ---                                               | ---                                                   | ---                             | ---                                            |
| `session:<h(sid)>`                                | Usuario, roles, fechas y huella del *refresh* vigente | La sesión (8 h desde el login)  | `auth`, `sesiones`                             |
| `user:<id>:sessions`                              | Huellas de las sesiones de una cuenta                 | La sesión                       | `auth`, `sesiones`                             |
| `refresh:<h(rt)>`                                 | Huella del `sid` de su sesión                         | Lo que le quede a la sesión     | `auth`, `sesiones`                             |
| `refresh:usado:<h(rt)>`                           | Refresh ya rotado, para detectar reuso                | Lo que le quede a la sesión     | `sesiones`                                     |
| `jwt:revoked:<jti>`                               | Marca de token revocado                               | Lo que le quede al token + 60 s | `sesiones`                                     |
| `captcha:<id>`                                    | Respuesta del captcha                                 | 300 s                           | `auth`                                         |
| `queue:simulaciones`                              | Lista de ids de corrida pendientes                    | Sin TTL; la vacía `simulador`   | `corridas`                                     |
| `lock:corrida:<version>`                          | Candado para no lanzar dos veces la misma corrida     | Unos segundos                   | `corridas`                                     |
| `job:<id>:progress`                               | Avance de una corrida                                 | Lo fija `simulador`             | `simulador`                                    |
| `cache:<servicio>:<clave>`                        | Respuesta en caché                                    | Corto (60 s en analítica)       | `resultados`, `indicadores`, `series`, `zonas` |
| `sync:lote:<id>`                                  | Resultado de un lote ya recibido                      | Lo fija `sincronizacion`        | `sincronizacion`                               |
| `health:<servicio>` y `health:history:<servicio>` | Última salud e historial corto                        | Lo fija `estado-servicios`      | `estado-servicios`                             |
 
Nada aquí es irrecuperable: si Redis se reinicia, la gente vuelve a iniciar sesión, las cachés se rellenan solas y lo que manda sobre las corridas es PostgreSQL. Las rutas públicas y la caché de analítica siguen funcionando contra la base aunque Redis esté caído.
 
### 5.3 MongoDB y Google Cloud Storage
 
No forman parte de la etapa actual: el catálogo de servicios y el checklist del segundo parcial los dejan fuera de alcance. Lo que el v1 les asignaba quedó así:
 
| Dato                                                    | En el v1                                 | Hoy                                                                    |
| ---                                                     | ---                                      | ---                                                                    |
| Series y resúmenes de cada corrida                      | MongoDB (`run_results`, `run_summaries`) | `simulation_results` en PostgreSQL                                     |
| Historial de salud                                      | MongoDB (`health_history`)               | Redis (`health:history:<servicio>`)                                    |
| Lotes del móvil tal como llegaron                       | MongoDB (`raw_sync_payloads`)            | Redis (`sync:lote:<id>`), solo el resultado                            |
| Registro de eventos y errores                           | MongoDB (`event_log`)                    | Registro de peticiones de cada servicio y `audit_log`                  |
| Fotos de evidencia                                      | Cloud Storage                            | Servicio opcional `evidencias`, en un volumen de Docker                |
| Reportes, escenarios exportados, artefactos de corridas | Cloud Storage                            | Exportación XML al vuelo desde `escenarios-xml`; lo demás, sin asignar |
 
La materia sí exige MongoDB y Cloud Storage. Cuándo y para qué entran está en la sección 9.
 
## 6. Procesamiento asíncrono
 
Hay dos caminos para correr una simulación, que comparten la tabla `simulation_runs`, los estados y el motor: el monolito usa un hilo de fondo, y los microservicios una cola en Redis con un proceso trabajador.
 
### 6.1 Ciclo de vida de una corrida
 
```
encolado → ejecutando → { completado | fallido | cancelado }
```
 
Solo se simula una versión de escenario **aprobada**, y su enfermedad debe tener todos los parámetros con fuente o marca de supuesto; si falta uno, el sistema se niega a simular.
 
**Camino de las apps (microservicios):**
 
1. La app hace `POST /api/v1/runs` a `corridas` con la versión aprobada.
2. `corridas` toma el candado `lock:corrida:<version>`, crea el registro en `simulation_runs` como `encolado`, empuja el id a `queue:simulaciones` y **responde 202 de inmediato** con el id.
3. `simulador` saca el id de la cola y lo pasa a `ejecutando` con una actualización condicionada. Si hay varios contenedores de `simulador`, solo uno gana cada corrida.
4. Ejecuta el motor, actualiza `job:<id>:progress` y al terminar escribe en `simulation_results` y marca `completado` o `fallido`.
5. Avisa a `notificaciones` con un token de servicio. La app consulta `GET /api/v1/runs/{id}` o lee sus avisos.
Al arrancar, `simulador` marca como `fallido` toda corrida que quedó a medias.
 
**Camino de la web (monolito):** la ruta crea el registro, lanza la corrida en un hilo de fondo y redirige a la pantalla de detalle, que consulta el estado. No usa Redis.
 
### 6.2 El motor de simulación
 
Es la única pieza que no es Flask. Vive en `procesamiento/motor/`, no conoce HTTP, sesiones ni la base, y su contrato es simple: recibe un diccionario con el escenario y una semilla, y regresa un diccionario serializable a JSON. La misma entrada con la misma semilla da exactamente la misma salida bajo la misma `ENGINE_VERSION`.
 
| Componente | Función |
| --- | --- |
| Validación de parámetros | Revisa el escenario y regresa errores y avisos; lo usa `validacion` sin guardar nada |
| Núcleo de simulación | Ejecuta el paso diario |
| Motor de intervenciones | Aplica las reglas programadas en cada fecha y capa de contacto |
| Indicadores | Agrega casos, hospitalizaciones, muertes y costo por corrida |
| Frontera de Pareto | Compara corridas por costo contra impacto (`pareto.py`) |
 
**Dos implementaciones detrás del mismo contrato:**
 
- **Implementación de referencia (hoy):** Python + NumPy. Es un SEIR estocástico por grupos de edad, con hospitalizados, fallecidos y vacunados; es decir, un modelo compartimental que divide a la población en grupos (susceptibles, expuestos, infecciosos, recuperados), no un modelo de agentes. Es la que garantiza que el sistema funcione.
- **Implementación acelerada (tercer parcial):** FLAME GPU 2, una biblioteca de C++/CUDA con interfaz en Python para simular agentes en GPU. Objetivo: entre 100 mil y 1 millón de agentes sintéticos del área metropolitana de Monterrey. Sustituye al motor propio en C++20 + CUDA que planteaba el v1.
Ambas leen la misma entrada y escriben el mismo formato de resultado. **Si FLAME GPU 2 no llega a tiempo, se queda la implementación de referencia y ningún otro componente se entera.** Es el principal mecanismo de control de riesgo del proyecto.
 
FLAME GPU 2 tiene licencia AGPL-3.0: si el motor se ofrece como servicio en red, el código que lo usa debe publicarse con la misma licencia. Para un repositorio académico público no es un problema, pero conviene anotarlo.
 
## 7. Infraestructura y despliegue
 
Todo corre en Docker con un solo `infra/docker-compose.yml`: un contenedor por microservicio, más la consola, PostgreSQL y Redis. Hoy el compose solo levanta Redis; el resto llega con el bloque J del checklist.
 
### 7.1 Contenedores
 
```
auth · sesiones · usuarios · roles
enfermedades · parametros · regiones · poblacion · tipos-intervencion
casos · sincronizacion
escenarios · intervenciones · aprobacion · validacion · escenarios-xml
corridas · simulador (uno o varios) · resultados · comparacion · pareto
indicadores · series · zonas
notificaciones · estado-servicios · consola
postgres · redis
```
 
- **Imagen base** `epidemia/base` (`infra/docker/base.Dockerfile`): `python:3.12-slim`, usuario sin privilegios y las dependencias de `epidemia_comun`, `backend_web` y `procesamiento`.
- **Un Dockerfile por servicio**, que parte de la imagen base, arranca con waitress (un servidor WSGI de producción para Python, en lugar del servidor de desarrollo de Flask) en el puerto 8000 y declara su `HEALTHCHECK` a `/health`.
- **Arranque ordenado** con `depends_on` y `condition: service_healthy`: un servicio no arranca hasta que PostgreSQL y Redis estén sanos.
- **Perfiles por dominio** (`identidad`, `catalogos`, `escenarios`…) para levantar solo una parte en máquinas con poca memoria.
- **PostgreSQL** se inicializa con el dump, las semillas y las migraciones 026 en adelante.
- El monolito web puede correr fuera de Docker (`python -m frontend_web.run`) contra el PostgreSQL local o el del compose.
### 7.2 Entornos
 
| Entorno                | Dónde                                                           | Para qué                                 |
| ---                    | ---                                                             | ---                                      |
| Desarrollo             | Local, con docker compose                                       | Trabajo diario                           |
| Pruebas de integración | Compose aparte sobre `simulador_epidemico_pruebas` y otro Redis | Nunca tocar los datos de la demostración |
| Producción             | Google Compute Engine                                           | Demostración y evaluación (pendiente)    |
 
### 7.3 Red y seguridad
 
- Red interna de Docker. Solo se publican los puertos del catálogo; PostgreSQL y Redis no quedan expuestos fuera de la máquina (Redis escucha en `127.0.0.1`).
- Sin Nginx: no hay TLS de borde en desarrollo. En Compute Engine hará falta definir cómo se protege el tráfico (sección 9).
- CORS cerrado: los navegadores solo aceptan llamadas desde el origen de la consola.
- La IP de origen se toma de la conexión, y de `X-Forwarded-For` solo si viene de la red interna de Docker.
- Secretos en archivos `.env` sin versionar (`.env`, `infra/.env`, `.env.shared`), documentados con su `.env.example`. Un servicio se niega a arrancar si falta un secreto o si conserva el valor de ejemplo.
- **Ningún secreto en el repositorio** ni en las evidencias.
### 7.4 Máquinas
 
| Instancia    | Contenido                                                 |
| ---          | ---                                                       |
| VM principal | Monolito web, microservicios, consola, PostgreSQL y Redis |
| VM con GPU   | `simulador` con FLAME GPU 2 (tercer parcial)              |
 
La VM con GPU se enciende solo cuando se necesita, porque cada integrante tiene 100 USD de crédito en GCP para todo el proyecto. Si no alcanza, `simulador` corre en la VM principal con el motor de referencia.
 
### 7.5 Pruebas
 
- **Unitarias e integración** con `pytest`, que también corre las 431 pruebas de `unittest` del monolito y el motor.
- **Pruebas de contrato:** cada ejemplo XML valida contra su XSD y cada respuesta JSON contra su esquema OpenAPI.
- **Integración:** flujo completo por HTTP (login → escenario → intervenciones → aprobación → corrida → resultados → comparación), revocación entre servicios, dos `simulador` con diez corridas y Redis apagado a mitad de la prueba.
- **Carga** con Locust contra consulta e ingesta (catálogos, tablero, sincronización), no contra el lanzamiento de corridas, que solo encola. Pendiente.
- **Integración continua** con GitHub Actions: pendiente; hoy no hay flujos en el repositorio.
## 8. Stack tecnológico completo
 
| Capa                     | Tecnología                                                   | Estado                                     | Por qué                                           |
| ---                      | ---                                                          | ---                                        | ---                                               |
| Web                      | Python, Flask, Jinja2                                        | En uso                                     | Requisito de la materia                           |
| Gráficas y mapas         | Highcharts, Highcharts Maps                                  | En uso                                     | Requisito de la materia                           |
| Frontend                 | HTML5, CSS3, JavaScript                                      | En uso                                     | Requisito de la materia                           |
| Acceso a datos           | psycopg2, SQL escrito a mano en `backend_web`                | En uso                                     | Una sola capa de datos para web y servicios       |
| Microservicios           | Flask + biblioteca común `epidemia_comun`                    | En construcción                            | Patrón de la librería vista en clase              |
| Servidor de aplicaciones | waitress                                                     | En construcción                            | Servidor de producción sencillo y multiplataforma |
| Formatos                 | XML (`defusedxml`) y JSON                                    | En construcción                            | XML por defecto, JSON a pedido (D9)               |
| Esquemas XML             | XSD validado con `xmlschema`                                 | En construcción                            | Requisito de la materia (D15)                     |
| Documentación de API     | OpenAPI 3 + Swagger UI en `/docs`                            | En construcción                            | Requisito de la materia                           |
| Autenticación            | JWT HS256 (PyJWT), contraseñas con bcrypt, sesiones en Redis | En uso (web) y en construcción (servicios) | Requisito de la materia                           |
| Base relacional          | PostgreSQL 15+, migraciones SQL numeradas                    | En uso                                     | Requisito de la materia; fuente de verdad         |
| Caché, sesiones y cola   | Redis 7.4                                                    | En uso                                     | Requisito de la materia                           |
| Contenedores             | Docker, docker compose, imagen `python:3.12-slim`            | En construcción                            | Requisito de la materia                           |
| Pruebas                  | pytest, fakeredis                                            | En uso                                     | D14                                               |
| Motor (referencia)       | Python, NumPy                                                | En uso                                     | SEIR por grupos de edad; siempre funciona         |
| Motor (acelerado)        | FLAME GPU 2                                                  | Tercer parcial                             | Simulación de agentes en GPU a escala             |
| Móvil                    | Kotlin, Retrofit, Room, CameraX, ML Kit, WorkManager         | Tercer parcial                             | Requisito de la materia (JSON)                    |
| Escritorio               | Python, PySide6                                              | Tercer parcial                             | El equipo ya usa Python (XML)                     |
| Base documental          | MongoDB                                                      | Fuera de esta etapa                        | Requisito de la materia                           |
| Archivos                 | Google Cloud Storage                                         | Fuera de esta etapa                        | Requisito de la materia                           |
| Nube                     | Google Compute Engine                                        | Pendiente                                  | Requisito de la materia                           |
| Pruebas de carga         | Locust                                                       | Pendiente                                  | Requisito de la materia                           |
| Integración continua     | GitHub Actions                                               | Pendiente                                  | Control de calidad básico                         |
 
**Retirados respecto al v1:** Nginx (D13, sin pasarela), marshmallow y flask-smorest (los contratos se escriben a mano), Flask-Limiter (los límites de consumo quedaron fuera de alcance), Numba y C++20 + CUDA propio (reemplazados por NumPy hoy y FLAME GPU 2 después), Google Secret Manager (los secretos van en archivos `.env`).
 
## 9. Brechas y decisiones abiertas
 
La arquitectura actual deja fuera varias piezas que los requisitos de la materia piden de forma explícita. Conviene confirmarlas con el profesor antes de la entrega, porque algunas se piden ya en el segundo parcial.
 
### 9.1 Brechas con los requisitos de la materia
 
| Requisito             | Qué pide la materia                                                                                             | Qué hay                                                     | Cuándo se pide  |
| ---                   | ---                                                                                                             | ---                                                         | ---             |
| MongoDB               | Almacenamiento real con inserción, consulta, actualización, agregación e índices                                | Fuera de alcance                                            | Segundo parcial |
| Límites de consumo    | Cada microservicio con límite; Redis para contadores                                                            | Fuera de alcance                                            | Segundo parcial |
| Google Cloud Storage  | Imágenes, documentos y evidencias                                                                               | Fuera de alcance                                            | Sistema final   |
| Locust                | Pruebas de carga de los microservicios                                                                          | Pendiente                                                   | Sistema final   |
| Compute Engine        | Despliegue de los servicios principales                                                                         | Pendiente                                                   | Sistema final   |
| Endpoints de salud    | La materia da como ejemplo seis rutas (`/health/live`, `/ready`, `/database`, `/redis`, `/mongodb`, `/storage`) | Una sola `/health`                                          | Segundo parcial |
| Web consume servicios | La guía de la materia supone que los clientes pasan por servicios                                               | La web va directo a PostgreSQL, por indicación del profesor | Confirmado      |
 
Si el profesor confirma que MongoDB y los límites de consumo entran ya, los candidatos más naturales son:
 
- **MongoDB:** el historial de `estado-servicios` y los lotes crudos de `sincronizacion` (datos de alta frecuencia y semiestructurados), y las series diarias de cada corrida cuando lleguen los agentes de FLAME GPU 2.
- **Límites de consumo:** un contador por usuario y ruta en Redis (`ratelimit:<usuario>:<ruta>`), más permisivo en `casos` y `sincronizacion` y más estricto en `corridas`.
### 9.2 Decisiones abiertas del proyecto
 
Cada una tiene su número en `docs/decisiones/decisiones.md`.
 
- [ ] D1 · Quién captura casos, quién aprueba versiones y quién consulta la auditoría
- [ ] D2 · El papel del SEIR (opción A o B de la corrección 2)
- [ ] D3 · Unidad de costo: personas-día, pesos o ambas por separado
- [ ] D4 · Qué parte del trabajo con escenarios queda en la web y qué en la app de escritorio
- [ ] D6 · Si la población de un escenario son habitantes, agentes simulados o un factor de escala
- [ ] D7 · Política para corregir datos en migraciones ya aplicadas
- [ ] D8 · Cuántas réplicas usa una comparación y cómo se resumen (tercer parcial)
- [ ] Cómo se protege el tráfico en Compute Engine sin Nginx (TLS y puertos expuestos)
- [ ] Fuente y serie histórica para calibrar el modelo de agentes
## 10. Orden de construcción
 
&#91;embedded content: orden de construcción · 3 parciales\]
 
Dentro del segundo parcial, la ruta crítica es la biblioteca común con su plantilla y la imagen base de Docker: hasta que existan, nadie puede generar su servicio. Si el tiempo no alcanza, se recortan primero `comparacion`, `pareto`, `indicadores`, `series` y `zonas`; los imprescindibles son `auth`, `sesiones`, `usuarios`, `enfermedades`, `regiones`, `casos`, `escenarios`, `validacion`, `aprobacion`, `escenarios-xml`, `corridas`, `simulador`, `resultados` y `estado-servicios`, más la consola, Docker y Redis.

