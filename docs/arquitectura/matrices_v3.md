> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Matrices e inventario de datos de la v3

Es el paso 2 del orden de trabajo de [`brechas_v3.md`](brechas_v3.md) (§10): las matrices (§9.2) y el inventario de datos (§9.3). Todo sale de [`procesos_v3.md`](procesos_v3.md), leído por columnas. El catálogo de servicios está en [`microservicios.md`](microservicios.md) y el diseño de la v3 en [`arquitectura_v3.md`](arquitectura_v3.md). Si un documento contradice una decisión, manda la decisión ([`decisiones.md`](../decisiones/decisiones.md)). Las contradicciones que afectan una celda están anotadas debajo de cada tabla.

### 1. Matriz de componentes

Web es el monolito (`frontend_web` y `backend_web`), que va directo a PostgreSQL (D20). «—» quiere decir que el componente no participa.

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
| Ver casos nuevos en tablero y mapa | P1 · 1.9 | Lee `cases` y `regions` directo a PostgreSQL en `/dashboard` y `/mapa`. Falta ver la foto (D-3) | — | — | — |
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
| Exportar el reporte | P3 · 3.6 | No (D4) | — | Exporta CSV y PDF, o imprime, en la computadora. Subir a GCS con URL firmada falta (D-3) | — |
| Consultar corrida y curvas | P3 · 3.7 | `/simulaciones/corridas/<id>`, directo a PostgreSQL (D20). Con D28, el resumen sale de `simulation_runs` y las curvas se piden a `resultados`. Abrir el reporte con URL firmada falta (D-3) | — | — | — |
| Inicio de sesión y cierre | Soporte | Login propio: firma su JWT, lo guarda en cookie y lo verifica contra PostgreSQL. Sin Redis (falta I3) | `auth` y `sesiones`: entra y renueva. Al cerrar borra lo guardado (C3) | `auth` y `sesiones` (2.1). Renueva con `TOKEN_EXPIRADO`. El cierre no está en procesos | — |
| Perfil del usuario | Soporte | — | Muestra el perfil con `usuarios` (`GET /users/me`) | — | — |
| Administración de usuarios y roles | Soporte | Administra cuentas y roles directo a PostgreSQL (arquitectura_v3 §4, D20) | — | — | — |
| Catálogos | Soporte | Catálogos directo a PostgreSQL (arquitectura_v3 §4). `parametros` y `poblacion` no tienen proceso | Lee `enfermedades` y `regiones` (1.3) | Lee `enfermedades`, `regiones` y `tipos-intervencion` (2.2) | Lee la versión y sus catálogos (`diseases`, `regions`, `intervention_types`) |
| Tablero e indicadores | Soporte (visualización) | Tablero y mapa leen PostgreSQL directo (D20). `indicadores`, `series` y `zonas` existen, pero la web no los llama | — | — | — |
| Monitoreo y directorio | Soporte | — | Pide a `estado-servicios` la URL de cada servicio (1.1) | Pide a `estado-servicios` la URL de cada servicio (2.1) | — |
| Sitio público sin sesión | Soporte | Páginas públicas sin sesión (arquitectura_v3 §4). Sin detalle en los documentos | — | — | — |
| Notificaciones (avisos) | Soporte | No hay avisos en la web: el autor no se entera de un rechazo (falta I1) | Lee avisos y los marca como leídos (D32). Ningún paso de P1 lo tiene | Lee avisos (2.9, 3.4) | Crea el aviso al terminar o fallar una corrida, con token de servicio (3.2) |
| Auditoría | Soporte | Consulta la bitácora; solo ADMINISTRADOR (D1). La migración 010 aún la da también al EPIDEMIOLOGO | Sus escrituras quedan en `audit_log` (`LOGIN`, `CREATE`, `UPDATE`, `SYNC`) | Sus escrituras quedan en `audit_log` (`LOGIN`, `RUN`, `CANCEL`, `CREATE`, `UPDATE`) | Anota `RUN` al empezar y al cerrar cada corrida |
| Límites de consumo (D31) | Soporte | — (la web no pasa por `epidemia_comun`) | Sujeta a límite; `casos` y `sincronizacion` son más permisivos. Falta (S2) | Sujeta a límite; `corridas` es más estricto. Falta (S2) | — |
| Entrada por HTTPS y nginx (D25, D26) | Soporte | Entra por nginx en 443. Falta (S6) | Entra por `https://<dominio>` con la raíz de Let's Encrypt que trae la app (D26) | Entra por HTTPS; `requests` confía en certifi (D26) | Sin entrada propia; `simulador-gpu` llega a PostgreSQL y Redis por IP interna (arquitectura_v3 §8) |
| Carga de archivos en la web | Soporte (D-5) | Falta (D-5): hoy la web no recibe archivos | — | — | — |

- **†, `resultados` en 3.5:** `comparacion` llama a `resultados` y usa su caché (`procesos_v3.md`, 3.5). Hoy el código de `comparacion` lee `simulation_results` directo; el cambio va con D28.
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

La integración de los tres procesos cubre usuario, app, servicios, Redis, PostgreSQL, auditoría y visualización. Faltan el bucket (D-3) y la notificación de P1 (I1).

### 2. Inventario de datos

Una fila por dato de las columnas *Escribe en*, *Lee de* y *Archivo en GCS* de `procesos_v3.md`, más las llaves de Redis, las colecciones de MongoDB y lo que guarda el teléfono. Las reglas de almacén son las de §9.3 de `brechas_v3.md`. «Por definir» quiere decir que ningún documento fija ese plazo o volumen. Por D32, P2 no usa bucket: el XML de intercambio queda como «solo si sobra tiempo».

| Dato | Quién lo crea | Quién lo lee | Almacén | Por qué ahí | Vida (TTL o retención) | Volumen esperado |
|---|---|---|---|---|---|---|
| `users` | `usuarios` (altas). `auth` anota intentos fallidos y último acceso | `auth` (1.1, 2.1); `usuarios`; `escenarios`, `validacion`, `aprobacion`, `corridas`, `simulador`, `resultados` y `pareto` (nombre del autor) | PostgreSQL | Integridad y relaciones (§9.3) | Por definir | Por definir |
| `user_roles` | `roles` (asignación) | `auth` (1.1, 2.1); `usuarios` | PostgreSQL | Integridad y relaciones (§9.3) | Por definir | Por definir |
| `devices` | `dispositivos` (alta, versión, última conexión y revocación) | `casos` (valida el dispositivo en 1.6); `dispositivos` | PostgreSQL | Relación con la cuenta (§9.3) | Por definir (la revocación es permanente, `microservicios.md`) | Uno por cuenta (1.2) |
| `diseases` (con `default_params`) | `enfermedades` (alta, edición, baja lógica). `parametros` (`default_params`) | Móvil (1.3); escritorio (2.2); `casos`, `escenarios`, `validacion`, `simulador` | PostgreSQL | Catálogo con integridad. Las versiones copian sus parámetros (D5) | Baja lógica; no se borra (`microservicios.md`) | Por definir |
| `regions` | Nadie: catálogo de solo lectura (`regiones`). `poblacion` cambia la población y las bandas de edad | Móvil (1.3); escritorio (2.2); web (1.9); `zonas`, `indicadores`, `escenarios` | PostgreSQL | Catálogo con integridad. La población se congela en cada versión (D5) | Por definir | 51 municipios de Nuevo León (`microservicios.md`) |
| `cases` | `casos`, al recibir el lote de 1.6. Solo CAPTURISTA, desde la móvil (D1) | Web (1.9); `enfermedades`, `evidencias`, `indicadores`, `series`, `zonas` | PostgreSQL | Integridad. `local_uuid` evita duplicados (1.6, D19) | Por definir | Cientos de miles en la demostración (D29) |
| `case_attachments` | `evidencias` (1.7) | `evidencias`; la web para ver la foto (1.9), con la URL firmada de `evidencias` (D2) | PostgreSQL (solo metadatos) | Relación con el caso. El archivo va a GCS (D30) | La del caso: borrar el caso borra sus filas (`ON DELETE CASCADE`); un ADMINISTRADOR borra una por error | Unas cuantas por caso, de hasta 20 MB cada una |
| `comparison_reports` (039) | `evidencias`, cuando el ANALISTA o el ADMINISTRADOR sube el reporte desde el escritorio (3.6) o la web (D35) | `evidencias` (lista, datos y URL firmada) para el escritorio y la web (3.7) | PostgreSQL (solo metadatos) | Relación con las corridas que compara (`run_ids`) y auditoría; el PDF va a GCS (D30) | Sin fecha: un ADMINISTRADOR lo borra por error | Uno por comparación exportada, de hasta 20 MB |
| `vaccine_lots` | `vacunas` (alta; `doses_used` con actualización condicionada) | `vacunas` (consulta, 1.8) | PostgreSQL | Integridad: nunca más dosis que las que quedan (`microservicios.md`) | Por definir | Por definir |
| `scenarios` | `escenarios` (2.3; 2.6 al importar) | `escenarios` (2.2, 2.9, 3.1); la web, solo lectura (D4) | PostgreSQL | Integridad y relaciones (§9.3) | Por definir | Por definir |
| `scenario_versions` | `escenarios` (2.3, versiones y duplicados). `aprobacion` (2.7: pasa a `en_revision` y congela `disease_params`, D5). Web (2.8) | `escenarios` (2.2); `validacion` (2.5); `corridas` (3.1, solo `aprobado`); web (2.8) | PostgreSQL | Estado y congelado de la versión. La base impone las reglas (D5) | Por definir | Por definir |
| `scenario_interventions` | `intervenciones` (2.4). `escenarios` (al versionar o duplicar). `escenarios-xml` (2.6, vía `intervenciones`) | `escenarios` (2.2); `validacion`; `aprobacion`; `simulador`; `pareto` | PostgreSQL | Relación con la versión; altas, bajas y movimientos | Por definir | Por definir |
| `intervention_types` | Nadie: catálogo de solo lectura (`tipos-intervencion`). `intervenciones` cambia el costo (`PUT .../cost`), fuera de los procesos; el costo se calcula en 3.5 | `tipos-intervencion` (2.2); `intervenciones` (2.4); `pareto` (costo, 3.5); `validacion`; `simulador` | PostgreSQL | Catálogo con integridad. El costo alimenta la frontera (3.5) | Por definir | Por definir |
| `simulation_batches` | `corridas` (3.1, `encolado`). `corridas` y `simulador` actualizan el estado junto con la corrida | `corridas` (3.3); `simulador` | PostgreSQL | Fuente de verdad del lote (D19) | Por definir | Un registro por lote lanzado (3.1) |
| `simulation_runs` | `corridas` (3.1 `encolado`; 3.3 `cancelada`). `simulador` (3.2 `ejecutando`, `completado` o `fallido`) | `corridas`; `simulador`; `resultados`, `comparacion`, `pareto` (3.5); web (3.7) | PostgreSQL | Estado de cada corrida. La base manda si Redis se pierde (D19). Lleva también el resumen, la huella y la trazabilidad, que la web lee de aquí (D28, migración 038) | Por definir | Una por réplica; 30 por versión por omisión (D8) |
| `simulation_results` | Nadie: retirada con la migración 041 | Nadie | — | El resumen pasó a `simulation_runs` (038) y la serie a `series_corridas` (D-1, D28) | — | — |
| `notifications` | `notificaciones` con token de servicio: `aprobacion` (al aprobar) y `simulador` (al terminar o fallar). **Falta (I1):** el aviso por lote de 1.6 no tiene tipo en el CHECK `ck_notifications_type` (migración 029, D32) | `notificaciones` (lista y marca leído); ANALISTA (2.9, 3.4); la app móvil (D32) | PostgreSQL | Integridad y relaciones (§9.3); el aviso tiene estado (leído o no) | Por definir | Por definir |
| `audit_log` | Cada escritura de servicios y web, en la misma transacción (`log_audit`). `sincronizacion` anota `SYNC` | ADMINISTRADOR (D1). **Falta:** quitar la lectura al EPIDEMIOLOGO (migración 010; se corrige en la 034) | PostgreSQL | Va en la misma transacción que la escritura. Solo se inserta (`microservicios.md`) | Por definir | Por definir |
| Captcha `captcha:<id>` | `auth` (1.1, 2.1) | `auth` | Redis | Temporal (D19). Sirve para un solo intento | 5 min; se borra al usarlo | Uno por intento de inicio de sesión |
| Sesión: `session:<h(sid)>`, `user:<id>:sessions`, `refresh:<h(rt)>`, `refresh:usado:<h(rt)>`, `jwt:revoked:<jti>` | `auth` (abre); `sesiones` (renueva y revoca) | Todas las rutas protegidas. La web no la usa (I3) | Redis | Temporal, con TTL y reconstruible (D19) | Sesión: 8 h desde el login; renovar no la alarga (`arquitectura_v2.md` §4.4). Token de acceso: 20 min (v2 §4.4). Revocado: lo que le quede al token, más 60 s | Una por sesión abierta |
| Candados: `lock:corrida:<version>`, `sync:lote:<id>:candado` | `corridas` (3.1); `sincronizacion` (1.6) | Los mismos servicios | Redis | Temporal. Vence solo (D19) | `lock:`: unos segundos. Candado de lote: 300 s | Uno por versión o lote en proceso |
| Resultado de lote: `sync:lote:<id>` | `sincronizacion` (1.6) | `sincronizacion` (responde «duplicado»); la app reenvía el mismo lote | Redis | Temporal. Si se pierde, `casos` evita duplicados por `local_uuid` (D19) | 7 días (`SYNC_LOTE_TTL_SECONDS`, 604 800 s) | Uno por lote recibido. Un lote trae hasta 100 casos |
| Cola: `queue:simulaciones:<motor>` | `corridas` (3.1) | `simulador` del mismo motor (3.2) | Redis | Temporal y reconstruible (D19). **Falta:** reencolar al arrancar las `encolado` (D19) | Sin TTL; la vacía `simulador` | Una entrada por corrida pendiente; 30 réplicas por versión por omisión (D8) |
| Avance: `job:<id>:progress` | `simulador` (3.2) | `corridas` (3.3) | Redis | Temporal (§9.3) | 24 h desde el último avance | Una por corrida en curso |
| Caché: `cache:<servicio>:<clave>` | `resultados` (300 s); `indicadores`, `series` y `zonas` | Los mismos servicios | Redis | Temporal. Perderla solo cuesta tiempo (D19) | `resultados`: 300 s. Analítica: «corto; lo fija cada servicio» (`microservicios.md`). `arquitectura_v2.md` §5.2 dice 60 s, sin confirmar | Por definir |
| Límite: `ratelimit:<usuario>:<ruta>` | `epidemia_comun`, en los 29 servicios (D31). **Falta** (S2) | Los mismos servicios | Redis | Contador temporal (§9.3, D31) | Ventana fija; su duración no está escrita | Un contador por usuario y ruta. Sin sesión, por IP (`arquitectura_v3.md` §5) |
| Salud: `health:<servicio>` y `health:history:<servicio>` | `estado-servicios` | `estado-servicios` (panel) | Redis hoy. **Falta:** pasa a MongoDB (`historial_servicios`, D28) | Hoy temporal. D19 dice que es el único dato que se pierde | `health:history`: una hora desde el último sondeo. `health:<servicio>`: lo fija el intervalo de sondeo (`microservicios.md`) | 29 servicios; 30 sondeos por servicio en `health:history` |
| `historial_servicios` (MongoDB) | `estado-servicios` (un documento por sondeo) | `estado-servicios` (panel: disponibilidad, latencia, último error) | MongoDB (D-1, D28) | Alta frecuencia y se agrega (§9.3, D28) | 30 días (TTL sobre `fecha`, `epidemia_comun/mongo.py`) | 29 servicios cada 10 s: unos 250 000 documentos al día y 7.5 millones con el TTL lleno |
| `series_corridas` (MongoDB) | `simulador` (3.2): un documento por día y corrida | `resultados`, para el escritorio (3.5) y para la web (3.7) | MongoDB | Alta frecuencia y se agrega (§9.3, D28) | Sin TTL: lo que viva su corrida en `simulation_runs`, que no se borra. La serie de una corrida cerrada como fallida se borra (D38) | 1.81 millones de documentos con 10 000 corridas de 180 días (D29; medido en `docs/pruebas/volumen/2026-11-18`) |
| Lote crudo de `sincronizacion` (MongoDB) | `sincronizacion` (1.6) | Por definir | MongoDB. **Solo si sobra tiempo** (D28, §9.3) | Semiestructurado (§9.3) | Por definir | Por definir |
| Fotos de casos (`evidencias`) | `evidencias` (1.7); la app sube el archivo | `evidencias` (con token) o quien reciba su URL firmada de 15 minutos; la web (1.9) | GCS, prefijo `evidencias/` (D2; en local, el emulador) | Archivo binario (§9.3, D30) | La de su fila: al borrarla se borra el objeto; si el caso se borra, el objeto queda huérfano | Máximo 20 MB por archivo (`microservicios.md`) |
| Reportes de P3 (PDF) | ANALISTA o ADMINISTRADOR desde el escritorio (3.6) o la web, por `POST /api/v1/reports` de `evidencias` (D2, D35) | Los roles con `reports.read`, con URL firmada de 15 minutos | GCS, prefijo `reportes/` | Archivo grande (§9.3, D30). Sus metadatos, en `comparison_reports` (039) | La de su fila | Máximo 20 MB por archivo |
| XML de intercambio (2.6) | ANALISTA desde el escritorio (2.6) | Por definir | GCS, **solo si sobra tiempo** (D32) | Archivo (§9.3). Se puede regenerar desde la versión en PostgreSQL (D32) | Por definir | Por definir |
| Salida cruda del motor (3.2) | `simulador` | Por definir | GCS, propuesta sin decidir | Archivo grande (§9.3). `procesos_v3.md` la cita en «§10.3», que no existe | Por definir | Por definir |
| Tokens de sesión (cifrados) | La app, al iniciar sesión (1.1) | La app (renovación y cierre) | Teléfono, cifrado con llave del Keystore | Hace falta sin red, y la llave protege el token (C3) | Hasta cerrar o perder la sesión (C3) | Uno por sesión activa |
| `device_id` | La app (1.2). Se llama `device_uid` en `microservicios.md` | La app; viaja con cada caso (D27) | Teléfono | Sin él no se manda el dispositivo (D27) | Por definir | Uno por cuenta (1.2) |
| Catálogos en Room (`enfermedades`, `regiones`) | La app (1.3) | La app, en el formulario (1.4) | Teléfono (Room) | Captura sin red (1.4) | Por definir | 51 municipios (`regiones`) |
| Casos pendientes (con `local_uuid`) | La app (1.4) | La app, al enviar (1.6) | Teléfono (Room) | Captura sin red (1.4) | Hasta que se envían (1.6). Al cerrar sesión se quedan (D19) | Por definir |
| Fotos por subir | La app (1.5): 1600 px, sin EXIF | La app (1.7) | Teléfono (Room) | Captura sin red. Se sube después (1.7) | Hasta que se suben (1.7) | Por definir |

- **Retención de PostgreSQL:** ningún documento fija plazo para las tablas. Por eso sus filas dicen «Por definir».
- **`sync_batches`:** no es una tabla. Es la entidad con que `SYNC` se anota en `audit_log` (`microservicios.md`, línea 79).
- **Sesión:** las 8 h y los 20 min vienen de `arquitectura_v2.md` §4.4. La v3 no los repite.
- **`series_corridas` y `simulation_results`:** `series_corridas` sustituye a `simulation_results` (D28, confirmado el 2026-11-16). El resumen de la corrida queda en `simulation_runs`, y la web lo lee de ahí; las curvas las pide a `resultados`, que lee MongoDB (excepción a D20). `simulation_results` sigue en uso hasta que MongoDB esté en operación.
- **Caché de analítica:** `microservicios.md` dice «corto; lo fija cada servicio». `arquitectura_v2.md` §5.2 dice 60 s. Falta confirmarlo.
- **Casos pendientes al cerrar sesión:** se quedan en el teléfono y se mandan cuando vuelve la conexión (D19). Al cerrar sesión solo se borran los tokens.

### 3. Mapa de servicios

Los 29 servicios del catálogo. En P1, P2 y P3 van los pasos que los usan (según la columna *Servicio* de `procesos_v3.md`).

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
| `aprobacion` | — | 2.7 (alterno a 2.8) | — | — |
| `validacion` | — | 2.5 | — | — |
| `escenarios-xml` | — | 2.6 | — | — |
| `corridas` | — | — | 3.1, 3.3 | — |
| `simulador` | — | — | 3.2 | — |
| `resultados` | — | — | 3.5 (†), 3.7 (curvas para la web, con D28) | — |
| `comparacion` | — | — | 3.5 | — |
| `pareto` | — | — | 3.5 | — |
| `indicadores` | — | — | — | Tablero e indicadores |
| `series` | — | — | — | Tablero e indicadores |
| `zonas` | — | — | — | Tablero e indicadores |
| `notificaciones` | — | 2.9 | 3.4 | Notificaciones |
| `estado-servicios` | 1.1 (directorio) | 2.1 (directorio) | — | Monitoreo y directorio |
| `dispositivos` | 1.2 | — | — | — |
| `evidencias` | 1.7 | — | — | — |
| `vacunas` | 1.8 | — | — | — |

- **Servicios que ningún proceso usa (6):** `roles`, `parametros` y `poblacion` son de soporte (administración y catálogos). `indicadores`, `series` y `zonas` son de soporte del tablero, y la web no los llama (D20), así que son candidatos a recorte.
- **Pasos sin servicio:**
  - Web, directo a PostgreSQL (D20): 1.9, 2.8 y 3.7.
  - Teléfono, local: 1.4 y 1.5.
  - Escritorio, sin servicio que lo cubra: 3.6. Exporta a un archivo local. Según §9.2, un paso sin servicio pide uno nuevo.
- **Avisos en la app:** `notificaciones` aparece en P2 y P3, pero la app móvil también lee avisos (arquitectura_v3 §4, D32) y ningún paso de P1 lo tiene.
- **Opcionales:** `recuperacion` y `configuracion` (`microservicios.md`) no están entre los 29 y no aparecen aquí.
