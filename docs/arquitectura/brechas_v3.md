> **Estado: Borrador** · 2026-11-01 · Revisado el 2026-11-16

# Inventario de brechas para la arquitectura v3

Compara lo que pide `docs/rubrica/trabajo_por_parcial.txt` (tercer parcial y entrega final) con lo que documenta `arquitectura_v2.md`, `microservicios.md` y `decisiones/decisiones.md`, y con lo que hay en el código (revisado por última vez el 2026-11-11).

Tipos de brecha:

- **Falta:** se pide y no existe.
- **Contradicción:** dos fuentes no coinciden, o el documento dice una cosa y el código hace otra.
- **Ambigüedad:** nadie lo ha decidido.
- **Verificar:** no se pudo confirmar leyendo el código; alguien tiene que probarlo.

Todas las decisiones de `decisiones/` (D1 a D35) están aceptadas. Lo que queda aquí es lo que falta documentar en la v3 o implementar. Por D21, todo lo pendiente es del tercer parcial.

Primero se termina el documento de arquitectura. El código se toca después, con el plan de implementación (§10).

**Ya resueltas:** I2 y S3; S1 (con pruebas de revocación); A1 (`abm-ref` en `procesamiento/abm/`, corre en `simulador-abm`; FLAME GPU solo si sobra tiempo) y A2 ([`ficha_simulador.md`](ficha_simulador.md)). C9: aplicar dosis y marcar avisos como leídos basta como «actualización de información» de la móvil (D32). A6, la calibración, queda fuera de alcance por D24.

## 1. Fallas de estructura

| #  | Problema                                                                                                                                                                                   | Evidencia                       | Tipo                                         |
|----|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------|----------------------------------------------|
| E5 | Los requerimientos funcionales, la trazabilidad y el contexto general están marcados como **Obsoleto**, y la matriz de permisos y las reglas de negocio como "revisar". La v3 no tiene una base de requerimientos vigente. | Encabezados de `requerimentos/` | Borrador del 2026-11-16 en [`requerimentos/`](../requerimentos/README.md); falta validarlo en equipo |
| E7 | La v2 deja fuera de alcance MongoDB, Cloud Storage y los límites de consumo, que ya decidieron D28, D30 y D31.                                                                             | `arquitectura_v2.md` §9.1 y §8  | Contradicción: la v3 tiene que incluirlos    |

## 2. Aplicaciones cliente

| #   | Requisito de la rúbrica                                | Documentado                                  | Implementado                                                                                                                                                                                                                                                       | Tipo                                                                                                               |
|-----|--------------------------------------------------------|----------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| C3  | Android: indicador de conexión                         | `frontend_movil/README.md`, secciones 3 y 4  | Token cifrado con una llave del Keystore (`sesion/`). Una sola renovación a la vez (`red/Renovador.kt`). Al cerrar o perder la sesión se borran los tokens; los casos sin enviar se quedan y se mandan cuando vuelve la conexión (D19). Para la conexión, solo hay mensajes de «Sin conexión» en cada pantalla                                 | Falta (parcial): un indicador de conexión fijo                                                                     |
| C8  | Menú por rol en ambas apps                             | D1 aceptada. La matriz sigue «por confirmar» | Escritorio: solo entran ANALISTA y ADMINISTRADOR, y «forzar error» es solo de ADMINISTRADOR. Móvil: muestra el mismo menú a cualquier rol                                                                                                                          | Falta (parcial): el menú por rol de la móvil                                                                       |
| C10 | Escritorio: validación del JWT y modificación de datos | `frontend_desktop/README.md`, «Sesión»       | No decodifica el JWT: lo valida cada servicio, y la app renueva con `TOKEN_EXPIRADO` y regresa al login con los demás 401 (`app/api.py`). Modifica: crea versiones; agrega, quita y mueve intervenciones; cancela corridas y envía a revisión (`app/servicios.py`) | Falta (D35): la app lee `exp` sin verificar la firma y renueva el token antes de que venza. La modificación está **Hecha** |

## 3. Integración completa

| #  | Requisito de la rúbrica                                                                                                   | Documentado                                                                                         | Implementado                                                                                                                                                                                                                                                                                                                                                                                                                                       | Tipo  |
|----|---------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|
| I1 | ≥ 3 procesos de principio a fin: usuario, app, microservicios, Redis, BD, bucket, auditoría, notificación y visualización | No hay una lista de los tres procesos; ver la propuesta en §9.1                                     | P1 va de punta a punta en la móvil (caso, sincronización y fotos). P2 y P3 van en el escritorio (escenario, revisión, aprobación en la web, corridas y comparación). P3 notifica al terminar cada corrida. P2 solo notifica si se aprueba por `aprobacion`: en la web no, y nadie avisa al enviar a revisión ([`procesos_v3.md`](procesos_v3.md), 2.7 y 2.8). Faltan el bucket y MongoDB, y P1 no notifica a nadie (D32: será un aviso por lote a los EPIDEMIOLOGO): `casos`, `sincronizacion` y `evidencias` no llaman a `notificaciones` (solo lo hacen `aprobacion` y `simulador`) | Falta |
| I3 | "Todos los componentes deberán consultar Redis durante la autenticación"                                                  | Sin documentar para la web. La rúbrica lo pide desde el segundo parcial («Implementación de Redis») | Verificado: la web no usa Redis en ningún lado. Firma su propio JWT, lo guarda en una cookie (`frontend_web/app/routes.py`) y lo verifica `backend_web/auth.py` contra PostgreSQL. Cerrar sesión borra la cookie, pero el token sigue valiendo hasta que vence: no hay revocación. D20 no lo impide: la web puede seguir directa a PostgreSQL y consultar Redis solo para la sesión                                                                 | Hecho (verificado el 2026-11-16): la web consulta Redis y revoca al cerrar sesión. Con Redis caído conserva las sesiones abiertas y no deja entrar (D33) |

## 4. Datos

| #   | Requisito de la rúbrica                                                                     | Documentado                                                                                                                       | Implementado                                                                                                                                                                                  | Tipo                                                         |
|-----|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| D-1 | MongoDB con inserción, consulta, actualización, agregación e índices, y su diseño           | D28: `historial_servicios` y `series_corridas`, con sus índices, TTL y `version_esquema`                                          | Ninguna referencia a `pymongo` en el código; no hay contenedor                                                                                                                                | Falta: decidido, falta pasarlo a la v3 e implementarlo. La web ya pide las curvas a `resultados` con el JWT de la sesión (D34) y vuelve a PostgreSQL si no responde |
| D-3 | Cloud Storage para fotos y evidencias, con URLs firmadas para los archivos privados         | D30: `evidencias` pasa a un bucket con URLs firmadas; en local, emulador o interfaz que cambie de disco a bucket                  | `evidencias` guarda el archivo en un volumen del servicio, no en la base. `case_attachments` lleva la ruta, el tipo, el tamaño, la huella, la privacidad, quién lo subió y cuándo. El archivo se baja con token | Falta: decidido, falta implementarlo                         |
| D-5 | Carga de archivos en la web                                                                 | Verificar                                                                                                                         | Ningún `request.files` en el código                                                                                                                                                           | Falta. D35: la web recibe el reporte de una comparación (ANALISTA y ADMINISTRADOR, `reports.upload`) |
| D-6 | Conjunto de datos de alto volumen y mediciones con y sin Redis                              | D29: unas 10,000 corridas de 180 días del SEIR en `series_corridas` (~1.8 millones de documentos)                                 | `gen_demo_data.py` genera datos de demostración; verificar el volumen                                                                                                                         | Falta; la cifra se confirma con el profesor                  |

## 5. Seguridad

| #  | Requisito de la rúbrica    | Documentado                                                                                | Implementado                    | Tipo                                 |
|----|----------------------------|--------------------------------------------------------------------------------------------|---------------------------------|--------------------------------------|
| S2 | Rate limiting              | D31: `ratelimit:<usuario>:<ruta>` en Redis, desde `epidemia_comun`                         | `epidemia_comun/limites.py` (429, `Retry-After`, `LIMITE_EXCEDIDO`); valores supuestos | Cerrada en la biblioteca; falta el 429 en los `openapi.json` |
| S5 | Secretos protegidos en GCP | No                                                                                         | `genera_env.py` solo para local | Falta                                |
| S6 | HTTPS en Compute Engine y entrada por nginx | D25 (nginx, ajusta D13) y D26 (Let's Encrypt)                             | No: `infra/` no tiene nginx     | Falta: decidido, falta implementarlo |

## 6. Nube, monitoreo y fallos

| #  | Requisito de la rúbrica                                                                              | Documentado                          | Implementado                                                                                                                                                                                                                                                                                                                         | Tipo                                                                           |
|----|------------------------------------------------------------------------------------------------------|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| N1 | Despliegue en Compute Engine con firewall y puertos controlados                                      | Pendiente en la v2                   | No                                                                                                                                                                                                                                                                                                                                   | Falta                                                                          |
| N2 | Diagrama de distribución en la nube: web, servicios, PostgreSQL, MongoDB, Redis, archivos, monitoreo | No                                   | —                                                                                                                                                                                                                                                                                                                                    | Falta                                                                          |
| N3 | Health check con proceso, PostgreSQL, MongoDB, Redis, bucket, tiempo de respuesta y versión          | La v2 reconoce que hay una sola ruta | `/health` en `comun/fabrica.py` revisa Redis, PostgreSQL y la versión; faltan MongoDB, bucket y tiempo                                                                                                                                                                                                                               | Falta (parcial)                                                                |
| N4 | Panel central: estado, errores, historial, servicios degradados, dependencias caídas                 | `estado-servicios`                   | Por servicio: estado (`ok`, `degradado` o `caido`), última revisión, latencia, versión, dependencias caídas (PostgreSQL o Redis) e historial en Redis (`/api/v1/services/<nombre>/history`). `/api/v1/services/health` resume cuántos hay en cada estado y la consola lo muestra. No cuenta errores. El historial pasa a MongoDB (D28) | Falta (parcial): el número de errores, y MongoDB y el bucket como dependencias |
| N5 | Demostrar la caída de un servicio, Redis, MongoDB, PostgreSQL, el bucket y un *timeout*              | No hay plan de pruebas de fallos     | Hay `test_redis_caido.py`                                                                                                                                                                                                                                                                                                            | En curso: `infra/demo_fallos.py` y `test_compose_fallos.py` escritos; MongoDB y bucket pendientes del compose |
| N6 | Logs centralizados en la nube                                                                        | No                                   | No                                                                                                                                                                                                                                                                                                                                   | Falta                                                                          |

## 7. Algoritmo y rendimiento

| #  | Requisito de la rúbrica                                                                                                                   | Documentado                                                                        | Implementado                                                                                                                                       | Tipo                                         |
|----|-------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| A3 | Réplicas de una comparación y cómo se resumen                                                                                             | D8: 30 réplicas con semillas 1..N; media, mediana y p5–p95; Pareto sobre medianas | En el escritorio (`frontend_desktop/app/resumen.py`)                                                                                               | Falta (parcial): el aviso de bandas encimadas (bloque A) |
| A4 | Pruebas con Locust por perfil (consulta, registro, móvil, escritorio, procesos automáticos)                                               | Pendiente                                                                          | No                                                                                                                                                 | Falta                                        |
| A5 | Métricas: usuarios concurrentes, peticiones por segundo, tiempo medio, p95, p99, errores, saturación, recuperación y endpoints más lentos | No                                                                                 | No                                                                                                                                                 | Falta                                        |

## 8. Pregunta pendiente al profesor

Con la v3 escrita: confirmar el volumen de D29 y, si el ABM va en GPU, si hay créditos de GCP para ella.

## 9. Cómo ordenar las funcionalidades

Hay que empezar por los procesos y no por los componentes. Lo que hace cada app, el simulador y cada almacén se *deduce* de los procesos; no se inventa por separado. Así no quedan funciones huérfanas ni servicios que nadie usa.

No todo sale de los procesos. El inicio de sesión, los catálogos, la administración de usuarios, el monitoreo y el sitio público son **funciones de soporte**: van como renglones propios en la matriz de componentes (§9.2), sin proceso.

Los requerimientos se trabajan en tres momentos. Antes son insumo (§9.0), durante salen de los procesos (§9.1) y después se redactan y se trazan (§9.6). No se reescriben antes de tener los procesos, porque se escribirían dos veces.

### 9.0 Insumos

- **Rúbrica:** los requisitos de la materia. No son los del producto, pero hay que cumplirlos.
- **Roles (D1) y reglas de negocio** (`requerimentos/reglas-negocio.md`, en revisión): quién hace cada paso y con qué restricciones.
- **Los `rf-*.md` y `rnf-*.md` obsoletos:** materia prima. Se consultan al escribir cada proceso; no se actualizan antes.

### 9.1 Escribir los procesos paso a paso

Cada proceso es una tabla con un renglón por paso:

| Paso | Quién (rol) | Dónde (app) | Qué hace | RF | Servicio | Formato | Escribe en | Lee de | Archivo en GCS | Auditoría | Notifica a |
|------|-------------|-------------|----------|----|----------|---------|------------|--------|----------------|-----------|------------|

Propuesta de los tres procesos, sacada del catálogo actual. Validada el 2026-11-16 (D32). Las tablas paso a paso están en [`procesos_v3.md`](procesos_v3.md):

- **P1 · Captura en campo (Android, JSON).** Una persona en campo registra un caso con GPS y foto, aunque no tenga conexión, y sincroniza después. Servicios: `auth`, `sesiones`, `casos`, `sincronizacion`, `regiones`, `enfermedades` y `evidencias`. Usa la cámara, el GPS, el almacenamiento local y la sincronización. Escribe el caso en PostgreSQL y la foto en GCS (D30). El resultado se ve en el tablero web. Opcional: el QR de lotes de `vacunas`. **Implementado en `frontend_movil/`, con `evidencias` y el QR de `vacunas`; faltan GCS y la notificación (I1).**
- **P2 · Diseño y aprobación de escenarios (escritorio, XML).** Se arma un escenario con sus intervenciones y costos, se importa o exporta en XML validado con XSD y se envía a revisión; quien revisa lo aprueba y se notifica. Servicios: `escenarios`, `intervenciones`, `validacion`, `escenarios-xml`, `aprobacion` y `notificaciones`. **Implementado en `frontend_desktop/`; la aprobación queda en la web (D4).**
- **P3 · Simulación y comparación (escritorio o web, más el simulador).** Se lanza un lote de corridas, que entra a la cola de Redis; el motor las ejecuta, las series diarias van a MongoDB (`series_corridas`, D28), se comparan con Pareto y se exporta un reporte a GCS con URL firmada. Servicios: `corridas`, `simulador`, `resultados`, `comparacion` y `pareto`. **El escritorio ya lanza los lotes con el SEIR o el ABM, compara y exporta el reporte a un archivo local. Faltan MongoDB, GCS y la URL firmada.**

Los tres pasan por Redis (la sesión) y por la auditoría. Repartidos entre seis personas, tocan dos por proceso.

**Requerimientos funcionales.** Cada paso es un requerimiento funcional candidato, y la columna **RF** lo anota. Al escribir cada proceso se abren los módulos que le corresponden:

| Módulo                                                                               | Dónde entra                            |
|--------------------------------------------------------------------------------------|----------------------------------------|
| C (vigilancia), I (Android)                                                          | P1 · Captura en campo                  |
| D (escenarios), H (escritorio)                                                       | P2 · Diseño y aprobación de escenarios |
| E (simulación), F (resultados)                                                       | P3 · Simulación y comparación          |
| G (tablero web)                                                                      | La visualización de P1 y P3            |
| A (autenticación), B (catálogos), J (publicación), K (monitoreo), L (administración) | Funciones de soporte                   |

Con cada RF viejo se hace una de cuatro cosas:

- Si encaja en un paso, se conserva con su ID (por ejemplo, RF-C03) para no romper la trazabilidad.
- Si cambió, se corrige.
- Si no encaja en ningún paso, va a funciones de soporte o a "fuera de alcance".
- Si un paso no tiene RF, se crea uno nuevo con el prefijo de su módulo.

**Requerimientos no funcionales.** Se adjuntan al paso como restricciones: p95 de un servicio, tamaño máximo de una foto, TTL de una sesión. Salen de la rúbrica (seguridad, Locust, health checks) y del inventario de datos (volumen y retención). Los que valen para todo un componente, como los logs o la disponibilidad, se anotan una sola vez en ese componente.

### 9.2 Sacar las tres matrices de los procesos

Ya escritos los procesos, se leen por columnas:

- **Matriz de componentes:** función × web, Android, escritorio y simulador, con un renglón por paso de proceso y uno por función de soporte. Responde qué hace cada app. Se coteja con las listas de la rúbrica para Android y para escritorio.
- **Inventario de datos:** dato · quién lo crea · quién lo lee · almacén · por qué ahí · vida (TTL o retención) · volumen esperado. Responde qué va a cada base y a GCS.
- **Mapa de servicios:** servicio × proceso. Un servicio que ningún proceso usa es candidato a recorte; un paso sin servicio pide uno nuevo.

Entre las tres sale la clasificación por componente que la rúbrica pide para los requerimientos: web, microservicios, móvil, escritorio, bases de datos, infraestructura, seguridad y monitoreo.

### 9.3 Dónde va cada dato

| Almacén    | Va ahí si…                                                                   | Qué va                                                                                                  |
|------------|------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| PostgreSQL | Pide integridad, relaciones o transacciones, o es la fuente de verdad        | Usuarios, roles, casos, escenarios y versiones, estado de las corridas, auditoría, metadatos de archivos |
| MongoDB    | Es semiestructurado o de alta frecuencia, o se agrega más de lo que se edita | D28: `historial_servicios` y `series_corridas`; los lotes de `sincronizacion` solo si sobra tiempo      |
| Redis      | Es temporal, tiene TTL y se puede reconstruir (D19)                          | Sesiones, tokens revocados, caché, contadores de límites (D31), candados, cola y progreso de corridas  |
| GCS        | Es un archivo binario o grande                                               | D30: fotos y evidencias; reportes y exportaciones; el XML de intercambio solo si sobra tiempo (D32)                       |

### 9.4 El simulador

Ver [`ficha_simulador.md`](ficha_simulador.md). Las tablas de validación y de tiempos se repiten con `python -m procesamiento.mediciones`.

### 9.5 Cierre: pasar la rúbrica por las matrices

Cada punto de la rúbrica (Android, escritorio, integración, seguridad, nube, monitoreo) tiene que caer en alguna celda o aparecer de forma explícita en "fuera de alcance". Lo que no cae en ningún lado es una brecha nueva.

### 9.6 Después de validar la v3: redactar y trazar

- **`rf-*.md` y `rnf-*.md`:** se reescriben a partir de las tablas, que ya tienen todo, y se les quita la marca de Obsoleto.
- **Historias de usuario y criterios de aceptación** (`historias-usuario.md`, pendiente en `docs/todo.md`): la historia es el paso visto desde quien lo hace. Las columnas *Escribe en*, *Auditoría* y *Notifica a* son su criterio de aceptación.
- **Casos de uso principales:** son los tres procesos.
- **Matriz de permisos y reglas de negocio:** se cierran con D1 y con la columna *Quién* de los procesos.
- **Matriz de trazabilidad** (`trazabilidad.md`): va al último porque necesita todo lo anterior. Cada renglón une RF, proceso, componente, servicio y prueba.

## 10. Orden de trabajo

1. Validar en equipo los tres procesos de [`procesos_v3.md`](procesos_v3.md) con su columna RF (§9.0 y §9.1). **Hecho el 2026-11-16 (D32).**
2. Sacar las matrices y el inventario de datos (§9.2 y §9.3).
3. Escribir la v3 a partir de la v2, con un apartado por cliente, el diagrama de despliegue en GCP con nginx y el diseño de MongoDB y de GCS.
4. Validar la v3 contra la rúbrica (§9.5) y confirmar el volumen con el profesor (§8).
5. Redactar los requerimientos, las historias de usuario y la trazabilidad (§9.6). **Borrador del 2026-11-16** en [`requerimentos/`](../requerimentos/README.md); falta validarlo en equipo.
6. Escribir el plan de implementación con las tareas que salen de los RF. **Borrador del 2026-11-16** en [`parciales/parcial-3/checklist.md`](../parciales/parcial-3/checklist.md); falta validarlo en equipo.
7. Marcar la v2 como Obsoleta.

## 11. Qué implementar después de la v3

Cada punto sigue su decisión:

1. MongoDB ([D28](../decisiones/D28-uso-de-mongodb.md)).
2. Volumen y mediciones con y sin índice y con y sin Redis ([D29](../decisiones/D29-volumen-de-datos.md)).
3. Locust por perfil, con p95, p99, errores y saturación (A4 y A5).
4. Límites de consumo ([D31](../decisiones/D31-limites-de-consumo.md)), reencolado de corridas ([D19](../decisiones/D19-redis-sin-datos-autoritativos.md)) y demostración de fallos (N5).
a. Archivos en un bucket o emulador con URLs firmadas ([D30](../decisiones/D30-archivos-en-cloud-storage.md)); nginx local con certificado de mkcert ([D25](../decisiones/D25-nginx-como-entrada.md) y [D26](../decisiones/D26-certificado-https.md)).
