Estado: revisar. Reglas sacadas del plan del primer parcial.

# **Reglas de negocio.**

#### Roles y permisos

| ID    | Regla                                                                                                                                                                    | Módulo afectado        |
| :---- | :----                                                                                                                                                                    | :----                  |
| RN-01 | Todo usuario debe tener asignado exactamente un rol activo (administrador, epidemiólogo, analista o capturista); no se permiten usuarios sin rol.                        | Usuario, Rol           |
| RN-02 | Solo el administrador puede crear, desactivar o reasignar el rol de otros usuarios.                                                                                      | Usuario                |
| RN-03 | Solo un epidemiólogo puede aprobar o rechazar un escenario; el analista que lo creó nopuede autoaprobarlo.                                                               | Escenario              |
| RN-04 | El capturista opera exclusivamente desde la app Android y solo tiene acceso a vigilancia de campo y aplicación de vacunas; no tiene acceso a escenarios ni experimentos. | Caso, AplicacionVacuna |
| RN-05 | Solo el analista crea/edita escenarios y lanza experimentos, desde la app de escritorio.                                                                                 | Escenario, Experimento |
| RN-06 | Un usuario inactivo (baja lógica) no puede autenticarse ni ejecutar ninguna acción, aunque sus credenciales sigan siendo válidas.                                        | Usuario                |

#### Catálogos

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-07 | Un registro de catálogo (enfermedad, zona, tipo de intervención, vacuna) que ya esté referenciado por un escenario, caso o aplicación de vacuna no puede eliminarse físicamente; solo puede desactivarse. | Enfermedad, Zona, TipoIntervencion, Vacuna |
| RN-08 | El nombre de cada enfermedad, el nombre de cada tipo de intervención y el correo de cada usuario deben ser únicos en el sistema. | Enfermedad, TipoIntervencion, Usuario |
| RN-09 | Los parámetros epidemiológicos de referencia de una enfermedad (R0, letalidad, periodo de incubación) deben ser valores no negativos. | Enfermedad |
| RN-10 | No se puede registrar un lote de vacuna cuya fecha de caducidadya hayapasado. | LoteVacuna |
| RN-11 | No se puede escanear ni aplicar un lote de vacuna caducado, aunque el lote se conserve en el catálogo por trazabilidad histórica. | LoteVacuna, AplicacionVacuna |

#### Escenarios

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-12 | Un escenario nace siempre en estado "borrador" y solo pasa a "aprobado" mediante revisión explícita de un epidemiólogo. | Escenario |
| RN-13 | Un escenario debe estar "aprobado" para poder usarse como base de un experimento; en "borrador" o "archivado" no puede lanzar corridas. | Escenario, Experimento |
| RN-14 | Toda nueva versión de un escenario conserva la referencia a la versión de la que partió; las versiones anteriores no se eliminan, se archivan. | Escenario |
| RN-15 | El contenido XML de un escenario debe validar contra el esquema definido antes de poder guardarse, tanto al crear como al editar. | Escenario |
| RN-16 | Un escenario debe estar asociado exactamente a una enfermedad y una zona del catálogo; no se permiten escenarios sin estos dos datos. | Escenario |
| RN-17 | Cuando una intervención dentro de un escenario especifica día de inicio y día de fin, el día de inicio debe ser menor o igual al día de fin. | EscenarioIntervencion |

#### Experimentos y corridas de simulación

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-18 | Todo experimento se genera a partir de un único escenario base, y ese escenario debe estar aprobado. | Experimento |
| RN-19 | Cada combinación de parámetros del barrido definido en un experimento produce exactamente una corrida de simulación. | Experimento, SimulacionCorrida |
| RN-20 | El resultado detallado de una corrida (series, estados de agentes) nunca se almacena en la base relacional; solo se conserva la referencia al documento correspondiente en MongoDB. | SimulacionCorrida |
| RN-21 | Una corrida solo puede transitar en el orden pendiente → ejecutando → completada, o pendiente → ejecutando → error; no puede pasar directamente de pendiente a completada. | SimulacionCorrida |
| RN-22 | Un reporte solo puede generarse sobre un experimento que tenga al menos una corrida en estado "completada". | Reporte, Experimento |

#### Vigilancia epidemiológica del campo

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-23 | Todo caso debe registrarse con enfermedad y zona obligatorias; un caso sin estos datos no puede guardarse ni sincronizarse. | Caso |
| RN-24 | Un caso nace siempre en estado "sospechoso"; su cambio a "confirmado" o "descartado" requiere una acción explícita de un rol distinto al capturista. | Caso |
| RN-25 | El origen de un caso (campovs. histórico de calibración con datos abiertos) debe quedar registrado explícitamente; ambos comparten la misma estructura pero nunca se mezclan sin dejar constancia del origen. | Caso |
| RN-26 | Toda evidencia fotográfica debe estar asociada a un caso existente; no se permiten evidencias huérfanas. | Evidencia, Caso |
| RN-27 | Un registro capturado sin conexión se marca como "no sincronizado" hasta que el servidor confirme su recepción; el capturista puede seguir trabajando offline sin límite de tiempo. | Caso, AplicacionVacuna |
| RN-28 | Al sincronizar, el sistema debe deduplicar los registros entrantes antes de insertarlos de forma definitiva, para evitar duplicados por reintentos de sincronización. | Caso, AplicacionVacuna |

#### Vacunación

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-29 | Toda aplicación de vacuna debe referenciar un lote vigente (no caducado) y una zona del catálogo. | AplicacionVacuna, LoteVacuna |
| RN-30 | La cantidad acumulada de dosis aplicadas de un lote no puede exceder su cantidad inicial disponible. | AplicacionVacuna, LoteVacuna |

#### Auditoría

| ID | Regla | Entidad / módulo afectado |
| :---- | :---- | :---- |
| RN-31 | Toda creación, modificación, eliminación o cambio de estado sobre una entidad relevante del dominio (usuarios, escenarios, casos, aplicaciones de vacuna, reportes) debe registrarse automáticamente en la bitácora de auditoría, sin depender de un registro manual. | BitacoraAuditoria |

Un registro de la bitácora de auditoría es inmutable: no RN-32 BitacoraAuditoria puede editarse ni eliminarse una vez creado.
