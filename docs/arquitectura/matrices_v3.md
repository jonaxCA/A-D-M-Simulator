> **Estado: Borrador** · 2026-11-22 · Por validar en equipo

# Matrices e inventario de datos de la v3

Es el paso 2 del orden de trabajo de [`brechas_v3.md`](brechas_v3.md) (§10): las matrices (§9.2) y el inventario de datos (§9.3). Todo sale de [`procesos_v3.md`](procesos_v3.md), leído por columnas. El catálogo de servicios está en [`microservicios.md`](microservicios.md) y el diseño de la v3 en [`arquitectura_v3.md`](arquitectura_v3.md). Si un documento contradice una decisión, manda la decisión ([`decisiones.md`](../decisiones/decisiones.md)). Las contradicciones que afectan una celda están anotadas debajo de cada tabla.

### 1. Matriz de componentes

Web es el monolito (`frontend_web` y `backend_web`), que consume los servicios por HTTP, sin credenciales de PostgreSQL, MongoDB ni Redis (D36, que reemplaza D20). Qué servicio atiende cada pantalla está en [`inventario_web_servicios.md`](inventario_web_servicios.md). «—» quiere decir que el componente no participa.

| Función | Proceso y paso | Web | Android | Escritorio | Simulador |
|---|---|---|---|---|---|
| Entrar con captcha y contraseña | P1 · 1.1 | — | Pide captcha; `auth` valida y `sesiones` abre la sesión. Guarda los tokens cifrados | — | — |
| Registrar el teléfono | P1 · 1.2 | — | Registra el dispositivo en `dispositivos`, uno por cuenta | — | — |
| Descargar catálogos | P1 · 1.3 | — | Baja `enfermedades` y `regiones` a Room | — | — |
| Capturar el caso sin conexión | P1 · 1.4 | — | Formulario con validación local y GPS; el caso queda pendiente | — | — |
| Tomar las fotos del caso | P1 · 1.5 | — | Cámara; reduce a 1600 px, quita el EXIF y guarda en Room | — | — |
| Sincronizar casos por lotes | P1 · 1.6 | — | Envía lotes de hasta 100 con WorkManager; muestra enviados, rechazados y faltantes | — | — |
| Subir las fotos de casos creados | P1 · 1.7 | — | Sube cada foto a `evidencias` | — | — |
| Leer lote de vacuna y aplicar dosis | P1 · 1.8 | — | Lee el QR o código de barras; registra el lote en `vacunas` y aplica dosis | — | — |
| Ver casos nuevos en tablero y mapa | P1 · 1.9 | `/dashboard` y `/mapa` con `indicadores`, `series` y `zonas` (D36). La URL firmada de la foto ya está en `evidencias` (D2); falta mostrarla en la web (C3) | — | — | — |
| Entrar a la app de escritorio | P2 · 2.1 | — | — | Pide captcha; revisa la sesión en Redis y el rol. Solo ANALISTA y ADMINISTRADOR | — |
| Buscar y abrir escenarios | P2 · 2.2 | Solo lectura (D4); no tiene paso en procesos | — | Busca y abre el escenario con sus versiones e intervenciones | — |
| Crear escenario, versión o duplicado | P2 · 2.3 | No (D4) | — | Crea en borrador con `escenarios` | — |
| Agregar, quitar y mover intervenciones | P2 · 2.4 | No (D4) | — | Edita la línea de tiempo con `intervenciones` | — |
| Validar la versión | P2 · 2.5 | — | — | Revisa con `validacion` antes de enviar | — |
| Exportar e importar XML | P2 · 2.6 | — | — | Exporta o importa `.xml` validado con el XSD (`escenarios-xml`). El archivo queda local | — |
| Enviar a revisión | P2 · 2.7 | No (D4) | — | Envía con `aprobacion`. Nadie avisa a los EPIDEMIOLOGO (falta I1) | — |
| Aprobar o rechazar versión | P2 · 2.8 | Bandeja `/revisiones`; aprueba o rechaza con comentario. Al rechazar no avisa (falta I1) | — | No aprueba (D4) | — |
| Ver aviso y estado de la versión | P2 · 2.9 | — | — | Lee `notificaciones` y el estado de la versión | — |
| Lanzar lote de réplicas | P3 · 3.1 | No (D4) | — | Lanza N réplicas por versión aprobada con `corridas`; encola en Redis | — |
| Correr la simulación | P3 · 3.2 | — | — | — | Toma la corrida de la cola de su motor; corre el motor; guarda resumen y serie; avisa |
| Seguir avance y cancelar | P3 · 3.3 | — | — | Ve el avance de cada corrida y cancela con `corridas` | — |
| Ver aviso de corridas terminadas | P3 · 3.4 | — | — | Lee `notificaciones` | — |
| Comparar y ver frontera y curvas | P3 · 3.5 | Vista de comparación de solo consulta (D4); no tiene paso en procesos | — | Resume media, mediana y p5–p95 en la app (D8). Frontera con `comparacion` y `pareto` (†) | — |
| Exportar el reporte | P3 · 3.6 | No (D4) | — | Exporta CSV y PDF, o imprime, en la computadora. Subir el PDF a `evidencias` (`POST /api/v1/reports`, D2, D35) y abrirlo con su URL firmada falta en la app (A2) | — |
| Consultar corrida y curvas | P3 · 3.7 | `/simulaciones/corridas/<id>` con `corridas` (D36): el resumen sale de `simulation_runs` y las curvas, de `resultados` (D28). La URL firmada del reporte ya está en `evidencias` (D2); falta abrirla en la web (C3) | — | — | — |
| Inicio de sesión y cierre | Soporte | Con `auth` y `sesiones`, que revisa la sesión en cada petición; la web no lee Redis (C6, D36) | `auth` y `sesiones`: entra y renueva. Al cerrar borra lo guardado (C3) | `auth` y `sesiones` (2.1). Renueva con `TOKEN_EXPIRADO`. El cierre no está en procesos | — |
| Perfil del usuario | Soporte | — | Muestra el perfil con `usuarios` (`GET /users/me`) | — | — |
| Administración de usuarios y roles | Soporte | Administra cuentas con `usuarios` y roles con `roles` (D36) | — | — | — |
| Catálogos | Soporte | Catálogos con sus servicios (D36). `parametros` y `poblacion` no tienen proceso | Lee `enfermedades` y `regiones` (1.3) | Lee `enfermedades`, `regiones` y `tipos-intervencion` (2.2) | Lee la versión y sus catálogos (`diseases`, `regions`, `intervention_types`) |
| Tablero e indicadores | Soporte (visualización) | Tablero y mapa con `indicadores`, `series` y `zonas` (D36) | — | — | — |
| Monitoreo y directorio | Soporte | — | Pide a `estado-servicios` la URL de cada servicio (1.1) | Pide a `estado-servicios` la URL de cada servicio (2.1) | — |
| Sitio público sin sesión | Soporte | Páginas públicas sin sesión (arquitectura_v3 §4). Sin detalle en los documentos | — | — | — |
| Notificaciones (avisos) | Soporte | No hay avisos en la web: el autor no se entera de un rechazo (falta I1) | Lee avisos y los marca como leídos (D32). Ningún paso de P1 lo tiene | Lee avisos (2.9, 3.4) | Crea el aviso al terminar o fallar una corrida, con token de servicio (3.2) |
| Auditoría | Soporte | Consulta la bitácora; solo ADMINISTRADOR (D1; la 034 se la quitó al EPIDEMIOLOGO) | Sus escrituras quedan en `audit_log` (`LOGIN`, `CREATE`, `UPDATE`, `SYNC`) | Sus escrituras quedan en `audit_log` (`LOGIN`, `RUN`, `CANCEL`, `CREATE`, `UPDATE`) | Anota `RUN` al empezar y al cerrar cada corrida |
| Límites de consumo (D31) | Soporte | — (la web no pasa por `epidemia_comun`) | Sujeta a límite; `casos` y `sincronizacion` son más permisivos. Falta (S2) | Sujeta a límite; `corridas` es más estricto. Falta (S2) | — |
| Entrada por HTTPS y nginx (D25, D26) | Soporte | Entra por nginx en 443. Falta (S6) | Entra por `https://<dominio>` con la raíz de Let's Encrypt que trae la app (D26) | Entra por HTTPS; `requests` confía en certifi (D26) | Sin entrada propia; `simulador-gpu` llega a PostgreSQL y Redis por IP interna (arquitectura_v3 §8) |
| Carga de archivos en la web | Soporte (D-5) | Falta (D-5): hoy la web no recibe archivos | — | — | — |

- **†, `resultados` en 3.5:** `comparacion` llama a `resultados` (`/results` y `/band`) y usa su caché (`procesos_v3.md`, 3.5, D28).
- **Costos:** el costo de cada escenario se calcula en 3.5, con el costo unitario de `intervention_types`. El costo unitario lo cambia `intervenciones` (`PUT .../cost`), fuera de los procesos.
- **Consultas de la web:** la lectura de escenarios (2.2) y la vista de comparación (3.5) vienen de D4, pero `procesos_v3.md` no les da paso.
- **Aviso al autor:** `aprobacion` avisa al aprobar (`microservicios.md`, línea 115). El rechazo no avisa (2.8).
- **Consola:** la consola de pruebas del equipo no es cliente del producto (`arquitectura_v3.md` §4), así que no entra en la matriz.

#### Cotejo con la rúbrica: Android

Requisitos de la [`rúbrica`](../rubrica/trabajo_por_parcial.txt) para la app móvil en el tercer parcial.

| Requisito de la rúbrica | Paso o función que lo cubre | ¿Cubierto? |
|---|---|---|
| Inicio de sesión | 1.1 | Sí |
| Almacenamiento seguro del token | 1.1 (tokens cifrados con llave del Keystore) | Sí |
| Renovación de sesión | 1.1 y «Inicio de sesión y cierre» (`sesiones`) | Sí |
| Perfil del usuario | «Perfil del usuario» | Sí |
| Menú por rol | — (C8) | Falta |
| Consulta de información | 1.3 (catálogos) y 1.8 (lote de vacuna) | Sí |
| Registro de información | 1.2, 1.4 y 1.8 | Sí |
| Actualización de información | 1.8 (aplicar dosis) y avisos leídos (D32, C9) | Sí |
| Consumo de al menos cuatro microservicios | 1.1 a 1.8 (once servicios con `notificaciones`, arquitectura_v3 §4) | Sí |
| Manejo de errores | Ningún paso lo describe; arquitectura_v3 §4 lo da por hecho | En parte |
| Indicador de conexión | — (C3) | Falta |
| Validación de formularios | 1.4 | Sí |
| Cierre de sesión | «Inicio de sesión y cierre» | Sí |
| Eliminación local de credenciales | «Inicio de sesión y cierre» (C3) | Sí |
| Al menos dos capacidades del dispositivo | 1.4 (GPS), 1.5 (cámara), 1.8 (QR y código de barras), 1.4 y 1.5 (almacenamiento local), 1.6 (sincronización) | Sí |
| Consumir exclusivamente JSON | Formato de P1 (todos los pasos en JSON, salvo la web de 1.9) | Sí |

#### Cotejo con la rúbrica: escritorio

Requisitos de la rúbrica para la app de escritorio en el tercer parcial.

| Requisito de la rúbrica | Paso o función que lo cubre | ¿Cubierto? |
|---|---|---|
| Inicio de sesión | 2.1 | Sí |
| Validación del JWT | 2.1. La app no decodifica el JWT; cada servicio lo valida (C10) | En parte |
| Menú por perfil | 2.1 (solo ANALISTA y ADMINISTRADOR; «forzar error» solo ADMINISTRADOR, C8) | Sí |
| Consulta de datos | 2.2, 2.9, 3.3 y 3.4 | Sí |
| Captura de datos | 2.3 y 2.4 | Sí |
| Modificación de datos | 2.3 a 2.7 y 3.3 (C10 la da por hecha) | Sí |
| Consumo de al menos cuatro microservicios | 2.1 a 3.5: `escenarios`, `intervenciones`, `validacion`, `escenarios-xml`, `aprobacion`, `corridas`, `comparacion`, `pareto`, `notificaciones`, `estado-servicios` | Sí |
| Validación mediante XSD | 2.6 (`escenarios-xml`, con `escenario.xsd`) | Sí |
| Manejo de errores | Ningún paso lo describe; arquitectura_v3 §4 lo da por hecho | En parte |
| Tabla de resultados | 3.3 y 3.5 muestran avance y resultados; ningún paso dice que sea una tabla | En parte |
| Búsqueda | 2.2 | Sí |
| Filtros | — (ningún paso lo pide) | Falta |
| Exportación inicial | 2.6 (XML) y 3.6 (CSV, PDF e impresión, en local) | Sí |
| Cierre de sesión | — (la app lo tiene, pero ningún paso ni función de soporte lo describe) | En parte |
| Proceso distinto al de la móvil | P2 y P3; P1 es de la móvil | Sí |
| Consumir exclusivamente XML | Formato de P2 y P3 (XML en todos los pasos de escritorio) | Sí |
| No ser copia de la web | D4: el escritorio hace el diseño, el XML, las corridas y la comparación completa | Sí |

La integración de los tres procesos cubre usuario, app, servicios, Redis, PostgreSQL, MongoDB, el bucket (D2; en GCP falta crearlo), auditoría, visualización y los avisos de P1 (I1).

### 2. Inventario de datos

Una fila por dato: las tablas de PostgreSQL que dejan las migraciones, las llaves de Redis, las colecciones de MongoDB, los archivos del bucket y lo que guarda el teléfono. Las reglas de almacén son las de §9.3 de `brechas_v3.md`.

- **Vida:** la fija D52. PostgreSQL y el bucket no borran nada por antigüedad, y cada fila dice cómo termina su dato: no se borra, baja lógica, lo borra el ADMINISTRADOR por error, en cascada con su padre (`ON DELETE CASCADE`) o se reemplaza. Redis y MongoDB vencen por TTL.
- **Volumen:** lo que hace crecer el dato y, en las tablas, las filas de la base de la demostración contadas el 2026-11-22. Las de la migración 039 y de la 057 en adelante todavía no están en esa base.
- Una prueba revisa que cada tabla tenga su fila y que todas digan su vida y su volumen (`microservicios/comun/tests/test_inventario_de_datos.py`).

**Identidad y acceso**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `users` | `usuarios` (altas, edición, baja lógica y borrado). `auth` anota intentos fallidos y último acceso | `auth` (1.1, 2.1); `usuarios`; los servicios que muestran el nombre del autor | PostgreSQL | Integridad y relaciones (§9.3) | Baja lógica (`is_active`). `usuarios` borra solo una cuenta sin casos, evidencias, lotes, escenarios ni corridas (409 si los tiene); con ella se van en cascada sus roles, alcances, dispositivos, avisos, preferencias y MFA, y `audit_log` conserva sus asientos con `user_id` nulo (migración 011) | Una por persona. Demostración: 4 |
| `user_roles` | `roles` (asignación) | `auth` (1.1, 2.1); `usuarios` | PostgreSQL | Integridad y relaciones (§9.3) | Se reemplaza al reasignar los roles de la cuenta; en cascada con ella. El cambio queda en `audit_log` | Una o dos por cuenta. Demostración: 4 |
| `user_scopes` (053) | `roles` (D43) | `roles` (`GET /scopes/me`), que consultan en cada petición `corridas`, `resultados`, `comparacion`, `pareto` y `series` | PostgreSQL | Relación con la cuenta, la región y la institución | Se reemplaza al reasignar el alcance; en cascada con la cuenta, la región o la institución | Ninguna por cuenta nacional; unas cuantas por cuenta limitada. Demostración: 0 |
| `institutions` (052) | `usuarios` (D42) | `usuarios` (perfil); `roles` (alcance) | PostgreSQL | Catálogo con integridad | Baja lógica (`is_active`); no se borra | Decenas. Demostración: 0 |
| `user_mfa` (051) | `auth` (D40) | `auth` (1.1, 2.1) | PostgreSQL | Secreto ligado a la cuenta | Hasta que un ADMINISTRADOR lo restablece (`DELETE /auth/mfa/{id}`) o se borra la cuenta (cascada) | Una por cuenta con perfil crítico (D40). Demostración: 0 |
| `mfa_backup_codes` (051) | `auth` (D40) | `auth` | PostgreSQL | Ligados a la cuenta, de un solo uso | Se reemplazan al volver a enrolar el MFA; uno usado queda con `used_at`. Se borran al restablecer el MFA o con la cuenta | 8 por cuenta con MFA. Demostración: 0 |
| `session_devices` (050) | `sesiones` (D41) | `sesiones` (1.1, 2.1: revisa el dispositivo al abrir la sesión) | PostgreSQL | Estado (`pendiente`, `autorizado`, `revocado`) ligado a la cuenta | No se borra: revocar es baja lógica. En cascada con la cuenta | Unos cuantos por cuenta; hasta 10 pendientes. Demostración: 0 |
| `devices` | `dispositivos` (alta, versión, última conexión y revocación) | `casos` (valida el dispositivo en 1.6); `dispositivos` | PostgreSQL | Relación con la cuenta (§9.3) | Revocar es para siempre (baja lógica, `microservicios.md`). En cascada con la cuenta | Uno por teléfono o PC de cada cuenta (1.2). Demostración: 0 |
| `roles`, `permissions`, `role_permissions` | Las migraciones (010, 034 y 052). Ningún servicio las escribe | `auth` (roles del token); `usuarios`; `roles` (`/roles/{id}/permissions`, `/permissions/me`) | PostgreSQL | Catálogo con integridad (RNF-K01) | Las fijan las migraciones; no se borran | Demostración: 6 roles, 25 permisos y 68 asignaciones |
| `password_resets` | Nadie: es del servicio opcional `recuperacion`, que no se hizo | Nadie | PostgreSQL | — | Sin uso. En cascada con la cuenta | 0 |
| Sesión: `session:<h(sid)>`, `user:<id>:sessions`, `refresh:<h(rt)>`, `refresh:usado:<h(rt)>`, `jwt:revoked:<jti>` | `auth` (abre); `sesiones` (renueva y revoca) | Todas las rutas protegidas (`requiere_token`) | Redis | Temporal, con TTL y reconstruible (D19) | Sesión: 8 h desde el login; renovar no la alarga (`arquitectura_v2.md` §4.4). Token de acceso: 20 min (v2 §4.4). Revocado: lo que le quede al token, más 60 s | Una por sesión abierta; hasta 3 por cuenta (`MAX_SESIONES`, D41) |
| Captcha `captcha:<id>` | `auth` (1.1, 2.1) | `auth` | Redis | Temporal (D19). Sirve para un solo intento | 5 min; se borra al usarlo | Uno por intento de inicio de sesión |
| MFA: `mfa:<h(token)>`, `mfa:fallos:<id>`, `mfa:alta:<id>` | `auth` (1.1, 2.1, D40) | `auth` | Redis | Temporal (D19) | `mfa:`: 5 min, o se borra al usarlo o al quinto fallo. `mfa:fallos:`: 15 min. `mfa:alta:`: 15 min, o se borra al usarlo | Uno por inicio de sesión a medias de un perfil crítico |
| Límite: `ratelimit:<usuario>:<ruta>` | `epidemia_comun`, en los 30 servicios (D31) | Los mismos servicios | Redis | Contador temporal (§9.3, D31) | La ventana: 60 s en los cuatro perfiles (`limites.py`) | Un contador por usuario y ruta. Sin sesión, por IP (`arquitectura_v3.md` §5) |

**Catálogos**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `diseases` (con `default_params`) | `enfermedades` (alta, edición, baja lógica). `parametros` (`default_params`) | Móvil (1.3); escritorio (2.2); `casos`, `escenarios`, `validacion`, `simulador` | PostgreSQL | Catálogo con integridad. Las versiones copian sus parámetros (D5) | Baja lógica; no se borra (`microservicios.md`) | Decenas. Demostración: 6 |
| `regions` | Las migraciones (010, 056 y 058). `poblacion` cambia `population` y `population_60plus` | Móvil (1.3); escritorio (2.2); web (1.9); `zonas`, `indicadores`, `escenarios` | PostgreSQL | Catálogo con integridad. La población se congela en cada versión (D5) | La fijan las migraciones; no se borra | 52: Nuevo León y sus 51 municipios |
| `region_age_groups` | La migración 021 (Censo 2020). `poblacion` corrige la población de un grupo | `regiones`, `poblacion`, `escenarios`, `validacion` | PostgreSQL | El motor reparte por edad; la versión la congela (D5) | La fija la migración; `poblacion` solo cambia `population`. En cascada con su región | 312: seis grupos por región |
| `region_population_adjustments` | `poblacion` | `poblacion` (la fuente de la cifra en pantalla) | PostgreSQL | Estado vigente del ajuste; el historial va en `audit_log` | Se reemplaza en cada ajuste | Uno por región y campo ajustado. Demostración: 0 |
| `intervention_types` | Las migraciones. `intervenciones` cambia el costo y las personas-día (`PUT .../cost` y `.../person-days`, D3) | `tipos-intervencion` (2.2); `intervenciones` (2.4); `pareto` (costo, 3.5); `validacion`; `simulador` | PostgreSQL | Catálogo con integridad. El costo alimenta la frontera (3.5) | Lo fijan las migraciones; no se borra | Demostración: 6 |

**Vigilancia**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `cases` | `casos`, al recibir el lote de 1.6. Solo CAPTURISTA, desde la móvil (D1) | Web (1.9); `enfermedades`, `evidencias`, `indicadores`, `series`, `zonas` | PostgreSQL | Integridad. `local_uuid` evita duplicados (1.6, D19) | No se borra: un caso se descarta o se marca duplicado (D47), y `case_history` lo referencia (`ON DELETE RESTRICT`) | Demostración: 3824. `gen_demo_data.py` genera cientos de miles para medir (D29) |
| `case_history` (057) | `casos` (D47): una fila por corrección o cambio de estado | `casos` (`GET /cases/{id}/history`) | PostgreSQL | Va en la misma transacción que el cambio del caso | No se borra: solo se inserta, y su caso no se borra | Una por corrección o cambio de estado |
| `case_forms` (059) | `casos` (D48) | `casos` (`GET /forms/current`, para la móvil en 1.3) | PostgreSQL | Versiones; cada caso apunta a la suya | No se borra: una versión publicada no cambia, y `cases.form_id` la referencia (`ON DELETE RESTRICT`) | Unas cuantas versiones por enfermedad |
| `case_attachments` | `evidencias` (1.7) | `evidencias`; la web para ver la foto (1.9), con la URL firmada de `evidencias` (D2) | PostgreSQL (solo metadatos) | Relación con el caso. El archivo va a GCS (D30) | Un ADMINISTRADOR borra una por error, con su objeto. En cascada con su caso, que no se borra | Unas cuantas por caso, de hasta 20 MB cada una. Demostración: 0 |
| `vaccine_lots` | `vacunas` (alta; `doses_used` con actualización condicionada) | `vacunas` (consulta, 1.8) | PostgreSQL | Integridad: nunca más dosis que las que quedan (`microservicios.md`) | No se borra; uno caducado ya no acepta dosis | Uno por lote escaneado. Demostración: 0 |
| `campaigns` (060) | `vacunas` (D49) | `vacunas`; las apps | PostgreSQL | Integridad con la enfermedad y el municipio | No se borra: se cancela con motivo, y su estado sale de las fechas | Unas cuantas por enfermedad y municipio |
| Fotos de casos (`evidencias`) | `evidencias` (1.7); la app sube el archivo | `evidencias` (con token) o quien reciba su URL firmada de 15 minutos; la web (1.9) | GCS, prefijo `evidencias/` (D2; en local, el emulador) | Archivo binario (§9.3, D30) | La de su fila: al borrarla se borra el objeto. `dias_retencion_evidencias` (1825 días, migración 010) no se aplica (D52) | Máximo 20 MB por archivo (`microservicios.md`) |
| Candados: `lock:corrida:<version>`, `sync:lote:<id>:candado` | `corridas` (3.1); `sincronizacion` (1.6) | Los mismos servicios | Redis | Temporal. Vence solo (D19) | `lock:`: unos segundos. Candado de lote: 300 s | Uno por versión o lote en proceso |
| Resultado de lote: `sync:lote:<id>` | `sincronizacion` (1.6) | `sincronizacion` (responde «duplicado»); la app reenvía el mismo lote | Redis | Temporal. Si se pierde, `casos` evita duplicados por `local_uuid` (D19) | 7 días (`SYNC_LOTE_TTL_SECONDS`, 604 800 s) | Uno por lote recibido. Un lote trae hasta 100 casos |
| Lote crudo de `sincronizacion` | — | — | No se implementa: era MongoDB «solo si sobra tiempo» (D28, §9.3) | — | — | — |
| `observed_datasets` (061) | `importacion` (D53), cuando EPIDEMIOLOGO, ANALISTA o ADMINISTRADOR importa una serie desde el escritorio (A4); la 061 carga la serie de D50 | `importacion` (lista y detalle, dentro del alcance de la cuenta); `calibracion` (E7, D50) | PostgreSQL | Integridad con la enfermedad y la región, versión por clave y auditoría | No se borra (D52): otra importación de la misma clave es una versión nueva | Uno por versión de cada serie; hoy, 1 (la de D50) |
| `observed_points` (061) | `importacion`, con su conjunto | `importacion` (`/datasets/{id}/points`); `calibracion` (E7) | PostgreSQL | Solo agregados por periodo: ningún registro por persona (RNF-I05) | La de su conjunto (`ON DELETE CASCADE`), que no se borra | De 4 a 5 000 por conjunto; la serie de D50 trae 22 semanas |
| Archivo de la DGE (`COVID19MEXICO2020.zip`) | — | — | No entra: trae un registro por persona y solo se procesa en local con `datos/scripts/build_serie_observada.py` (D50) | — | — | — |

**Escenarios y simulación**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `research_projects` (064) | `escenarios` (D54), cuando ANALISTA, EPIDEMIOLOGO o ADMINISTRADOR crea un proyecto de investigación desde el escritorio (A4) | `escenarios` (lista y detalle, dentro del alcance de la cuenta; también INVESTIGADOR y AUTORIDAD_SANITARIA) | PostgreSQL | Integridad con la enfermedad, la región, el dueño y sus escenarios (`scenarios.project_id`) | No se borra (D52): se archiva (`status`) y los escenarios lo referencian (`ON DELETE RESTRICT`) | Unos cuantos por equipo de investigación. Demostración: 0 |
| `scenarios` | `escenarios` (2.3; 2.6 al importar; archivar, restaurar y mover de proyecto, D54) | `escenarios` (2.2, 2.9, 3.1); la web, solo lectura (D4) | PostgreSQL | Integridad y relaciones (§9.3) | No se borra: se archiva (RF-D12, D54) y queda de solo lectura | Demostración: 8 |
| `scenario_versions` | `escenarios` (2.3, versiones y duplicados). `aprobacion` (2.7: pasa a `en_revision` y congela `disease_params`, D5; aprueba con su firma `approval_sha256`, rechaza o la devuelve a borrador, D55). Web (2.8, por `aprobacion`) | `escenarios` (2.2); `validacion` (2.5); `corridas` (3.1, solo `aprobado`); web (2.8) | PostgreSQL | Estado y congelado de la versión. La base impone las reglas (D5) | No se borra: fuera de borrador es inmutable (D5) y sus corridas la referencian (`ON DELETE RESTRICT`) | Unas cuantas por escenario. Demostración: 10 |
| `scenario_interventions` | `intervenciones` (2.4). `escenarios` (al versionar o duplicar). `escenarios-xml` (2.6, vía `intervenciones`) | `escenarios` (2.2); `validacion`; `aprobacion`; `simulador`; `pareto` | PostgreSQL | Relación con la versión; altas, bajas y movimientos | `intervenciones` las quita o cambia mientras la versión es borrador; después quedan congeladas. En cascada con su versión | Unas cuantas por versión. Demostración: 18 |
| `simulation_batches` | `corridas` (3.1, `encolado`). `corridas` y `simulador` actualizan el estado junto con la corrida | `corridas` (3.3); `simulador` | PostgreSQL | Fuente de verdad del lote (D19) | No se borra | Uno por lote lanzado (3.1). Demostración: 270 |
| `simulation_runs` | `corridas` (3.1 `encolado`; 3.3 `cancelada`; reintento, D44). `simulador` (3.2 `ejecutando`, `completado` o `fallido`) | `corridas`; `simulador`; `resultados`, `comparacion`, `pareto` (3.5); web (3.7) | PostgreSQL | Estado de cada corrida. La base manda si Redis se pierde (D19). Lleva también el resumen, la huella y la trazabilidad, que la web lee de aquí (D28, migración 038) | No se borra; su serie vive lo que ella (D52) | Una por réplica; 30 por versión por omisión (D8). Demostración: 270 |
| `simulation_results` | Nadie: retirada con la migración 041 | Nadie | — | El resumen pasó a `simulation_runs` (038) y la serie a `series_corridas` (D-1, D28) | — | — |
| `series_corridas` (MongoDB) | `simulador` (3.2): un documento por día y corrida | `resultados`, para el escritorio (3.5) y para la web (3.7) | MongoDB | Alta frecuencia y se agrega (§9.3, D28) | Sin TTL: lo que viva su corrida en `simulation_runs`, que no se borra. La serie de una corrida cerrada como fallida se borra (D38) | 1.81 millones de documentos con 10 000 corridas de 180 días (D29; medido en `docs/pruebas/volumen/2026-11-18`) |
| `comparison_reports` (039) | `evidencias`, cuando el ANALISTA o el ADMINISTRADOR sube el reporte desde el escritorio (3.6) o la web (D35) | `evidencias` (lista, datos y URL firmada) para el escritorio y la web (3.7) | PostgreSQL (solo metadatos) | Relación con las corridas que compara (`run_ids`) y auditoría; el PDF va a GCS (D30) | Sin fecha: un ADMINISTRADOR lo borra por error, con su objeto | Uno por comparación exportada, de hasta 20 MB |
| Reportes de P3 (PDF) | ANALISTA o ADMINISTRADOR desde el escritorio (3.6) o la web, por `POST /api/v1/reports` de `evidencias` (D2, D35) | Los roles con `reports.read`, con URL firmada de 15 minutos | GCS, prefijo `reportes/` | Archivo grande (§9.3, D30). Sus metadatos, en `comparison_reports` (039) | La de su fila | Máximo 20 MB por archivo |
| Cola: `queue:simulaciones:<motor>` y `:<prioridad>` | `corridas` (3.1) | `simulador` del mismo motor (3.2) | Redis | Temporal y reconstruible (D19): al arrancar y cuando Redis vuelve, el simulador mete otra vez las `encolado` de la base (D38) | Sin TTL; la vacía `simulador` | Una entrada por corrida pendiente; 30 réplicas por versión por omisión (D8) |
| Avance: `job:<id>:progress` | `simulador` (3.2) | `corridas` (3.3) | Redis | Temporal (§9.3) | 24 h desde el último avance | Una por corrida en curso |
| Latido: `worker:<motor>:<simulador>` | `simulador` | `estado-servicios` (cuenta los simuladores vivos y ocupados) | Redis | Temporal: si el simulador muere, desaparece solo | 30 s; el simulador lo renueva cada 10 s | Uno por simulador vivo |
| Caché: `cache:<servicio>:<clave>` | `resultados`, `indicadores`, `series` y `zonas` | Los mismos servicios | Redis | Temporal. Perderla solo cuesta tiempo (D19) | `resultados`: 300 s. `indicadores`, `series` y `zonas`: 60 s (`TTL_CACHE`) | Una por consulta distinta y ámbito de quien pregunta |
| XML de intercambio (2.6) | — | — | No se implementa: por D32, P2 no usa bucket y el XML se regenera desde la versión | — | — | — |
| Salida cruda del motor (3.2) | — | — | No se implementa: la serie va a MongoDB y el resumen a `simulation_runs` (D28) | — | — | — |

**Plataforma**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `notifications` | `notificaciones`, con token de servicio: `aprobacion`, `simulador`, `sincronizacion` (`NEW_CASES`, D32), `casos` (`CASE_REJECTED`, `DATA_INCOMPLETE`), `vacunas` (`CAMPAIGN`) y `estado-servicios` (`SYSTEM`) | `notificaciones` (lista y marca leído); las apps (2.9, 3.4; la móvil, D32) | PostgreSQL | Integridad y relaciones (§9.3); el aviso tiene estado (leído o no) | No se borra: leer solo llena `read_at`. En cascada con la cuenta | Uno por persona y evento; los de un rol, uno por cada persona activa con ese rol. Demostración: 275 |
| `notification_preferences` (060) | `notificaciones` (D49) | `notificaciones` (antes de crear un aviso) | PostgreSQL | Ligada a la cuenta | Volver a prender un tipo actualiza la fila. En cascada con la cuenta | Una por persona y tipo de aviso que cambió |
| `audit_log` | Cada escritura de los servicios, en la misma transacción (`log_audit`). `sincronizacion` anota `SYNC`; `requiere_token`, cada 403 (`PERMISSION_DENIED`, 046) | ADMINISTRADOR, por `roles` (`GET /api/v1/audit`, D1, D37; `audit.read` salió del EPIDEMIOLOGO en la 034) | PostgreSQL | Va en la misma transacción que la escritura. Solo se inserta (`microservicios.md`) | No se borra: el trigger `tg_audit_log_inmutable` impide editarla o borrarla. Borrar una cuenta solo pone su `user_id` en nulo (011) | Una por escritura o 403. Demostración: 1173 |
| `system_settings` | Las migraciones (010, 035 y 036). Ningún servicio lo escribe: `configuracion` es opcional | Ningún servicio lo lee hoy | PostgreSQL | Ajustes editables sin desplegar | Lo fijan las migraciones. `dias_retencion_evidencias` no se aplica (D52) | 5 claves |
| `schema_migrations` | Cada migración | `verifica_migraciones.py` y `prepara_base_pruebas.py` | PostgreSQL | Registro de lo aplicado (D17) | No se borra | Una por migración |
| Salud: `health:<servicio>` | `estado-servicios` | `estado-servicios` (panel) | Redis | Temporal: el último sondeo. El historial está en MongoDB (`historial_servicios`) | Tres intervalos de sondeo: 30 s con `SONDEO_SEGUNDOS` en 10 | Una por servicio: 29 |
| Alertas y errores: `alert:<servicio>`, `errors:<servicio>` | `estado-servicios` (alertas técnicas, F7); todos los servicios (`errors:`, cada 5xx) | `estado-servicios` (panel y alertas) | Redis | Temporal (D19) | `alert:`: 7 días desde el último aviso. `errors:`: 24 h desde el primer error de la ventana | Una de cada una por servicio: 29 |
| `historial_servicios` (MongoDB) | `estado-servicios` (un documento por sondeo) | `estado-servicios` (panel: disponibilidad, latencia, último error) | MongoDB (D-1, D28) | Alta frecuencia y se agrega (§9.3, D28) | 30 días (TTL sobre `fecha`, `epidemia_comun/mongo.py`) | 30 servicios cada 10 s: unos 260 000 documentos al día y 7.8 millones con el TTL lleno |

**Teléfono**

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| Tokens de sesión (cifrados) | La app, al iniciar sesión (1.1) | La app (renovación y cierre) | Teléfono, cifrado con llave del Keystore | Hace falta sin red, y la llave protege el token (C3) | Hasta cerrar o perder la sesión (C3) | Uno por sesión activa |
| `device_uid` | La app (1.2), uno por cuenta en el teléfono (`Telefono.kt`) | La app; viaja con cada caso (D27) | Teléfono (DataStore) | Sin él no se manda el dispositivo (D27) | Lo que dure la instalación: cerrar sesión no lo borra. Si el servidor lo rechaza (409), la app genera otro | Uno por cuenta que inicia sesión en el teléfono |
| Catálogos en Room (`enfermedades`, `regiones`, formularios) | La app (1.3) | La app, en el formulario (1.4) | Teléfono (Room) | Captura sin red (1.4) | Se reemplazan completos en cada descarga (`CatalogoDao.kt`) | Unas cuantas enfermedades y sus formularios, y 51 municipios |
| Casos pendientes (con `local_uuid`) | La app (1.4) | La app, al enviar (1.6) | Teléfono (Room) | Captura sin red (1.4) | Hasta que se envían (1.6): entonces se borran los datos de la persona y queda el comprobante (enfermedad, municipio, fecha y `case_id`). Uno rechazado se queda hasta que se descarta. Al cerrar sesión se quedan (D19) | Los que se capturen sin red; se envían en lotes de hasta 100 |
| Fotos por subir | La app (1.5): 1600 px, sin EXIF | La app (1.7) | Teléfono (Room y archivo) | Captura sin red. Se sube después (1.7) | Hasta que se suben (1.7): entonces se borra el archivo. Si se descarta el caso, se va con él | Unas cuantas por caso |

- **`sync_batches`:** no es una tabla. Es la entidad con que `SYNC` se anota en `audit_log` (`microservicios.md`).
- **Sesión:** las 8 h y los 20 min vienen de `arquitectura_v2.md` §4.4. La v3 no los repite.
- **Casos pendientes al cerrar sesión:** se quedan en el teléfono y se mandan cuando vuelve la conexión (D19). Al cerrar sesión solo se borran los tokens.

### 3. Mapa de servicios

Los 30 servicios del catálogo. En P1, P2 y P3 van los pasos que los usan (según la columna *Servicio* de `procesos_v3.md`).

| Servicio | P1 | P2 | P3 | Soporte |
|---|---|---|---|---|
| `auth` | 1.1 | 2.1 | — | Inicio de sesión y cierre |
| `sesiones` | 1.1 | 2.1 | — | Inicio de sesión y cierre |
| `usuarios` | — | 2.1 | — | Perfil del usuario; administración de usuarios y roles |
| `roles` | — | — | — | Administración de usuarios y roles |
| `enfermedades` | 1.3 | 2.2 | — | Catálogos |
| `parametros` | — | — | — | Catálogos |
| `regiones` | 1.3 | 2.2 | — | Catálogos |
| `poblacion` | — | — | — | Catálogos |
| `tipos-intervencion` | — | 2.2 | — | Catálogos |
| `casos` | 1.6 (llamado por `sincronizacion`) | — | — | — |
| `sincronizacion` | 1.6 | — | — | — |
| `escenarios` | — | 2.2, 2.3, 2.6, 2.9 | — | — |
| `intervenciones` | — | 2.4, 2.6 | — | — |
| `aprobacion` | — | 2.7, 2.8 (la web) | — | — |
| `validacion` | — | 2.5 | — | — |
| `escenarios-xml` | — | 2.6 | — | — |
| `corridas` | — | — | 3.1, 3.3, 3.7 (la web) | — |
| `simulador` | — | — | 3.2 | — |
| `resultados` | — | — | 3.5 (†), 3.7 (curvas para la web, con D28) | — |
| `comparacion` | — | — | 3.5 | — |
| `pareto` | — | — | 3.5 | — |
| `indicadores` | 1.9 (la web) | — | — | Tablero e indicadores |
| `series` | 1.9 (la web) | — | — | Tablero e indicadores |
| `zonas` | 1.9 (la web) | — | — | Tablero e indicadores |
| `notificaciones` | — | 2.9 | 3.4 | Notificaciones |
| `estado-servicios` | 1.1 (directorio) | 2.1 (directorio) | — | Monitoreo y directorio |
| `dispositivos` | 1.2 | — | — | — |
| `evidencias` | 1.7, 1.9 (la foto) | — | 3.6, 3.7 (el reporte, D35) | — |
| `vacunas` | 1.8 | — | — | — |
| `importacion` | — | — | — | Gestión de datos y calibración (D50, D53) |

- **Servicios que ningún proceso usa (4):** `roles`, `parametros` y `poblacion` son de soporte (administración y catálogos), e `importacion`, de la gestión de datos del escritorio y de la calibración (D53), que todavía no tienen proceso en `procesos_v3.md`.
- **Pasos sin servicio:** solo los del teléfono, que son locales: 1.4 y 1.5. Desde D36 la web llama a los servicios en 1.9, 2.8 y 3.7, y desde D2 el reporte de 3.6 sube a `evidencias` (D35).
- **Avisos en la app:** `notificaciones` aparece en P2 y P3, pero la app móvil también lee avisos (arquitectura_v3 §4, D32) y ningún paso de P1 lo tiene.
- **Opcionales:** `recuperacion` y `configuracion` (`microservicios.md`) no están entre los 30 y no aparecen aquí.
