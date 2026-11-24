> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# Reglas de negocio

Las restricciones que valen para todo el sistema, sin importar la pantalla o el servicio. Salen de las decisiones ([`decisiones.md`](../decisiones/decisiones.md)), de las reglas de `AGENTS.md` y de los procesos ([`procesos_v3.md`](../arquitectura/procesos_v3.md)). La última columna dice qué requerimiento la cumple.

Los estados son los de la base; el esquema son las migraciones de `datos/postgres/migraciones/`.

## Roles y permisos

| ID | Regla | Requerimiento |
|---|---|---|
| RN-01 | Toda cuenta tiene un rol: ADMINISTRADOR, EPIDEMIOLOGO, ANALISTA o CAPTURISTA. No hay cuentas sin rol | RF-A04, RF-L02 |
| RN-02 | Solo el ADMINISTRADOR crea, desactiva o cambia el rol de otras cuentas | RF-L01, RF-L02 |
| RN-03 | Una versión la aprueban o la rechazan el EPIDEMIOLOGO o el ADMINISTRADOR (D1). Nadie revisa su propia versión; la base lo impide | RF-D13, RF-D16 |
| RN-04 | El CAPTURISTA captura solo desde la app Android. En la web entra únicamente al tablero y al mapa (D1) | RF-C01, RF-G11 |
| RN-05 | Crear y editar escenarios, enviarlos a revisión y lanzar corridas se hace solo en la app de escritorio, por un ANALISTA o un ADMINISTRADOR (D4) | RF-D01, RF-E01, RF-H01 |
| RN-06 | Una cuenta inactiva no inicia sesión ni hace nada, aunque su contraseña sea correcta | RF-A01, RF-L01 |
| RN-37 | Una cuenta usa un solo teléfono. Un teléfono revocado no sincroniza | RF-A09, RF-C21 |

## Catálogos

| ID | Regla | Requerimiento |
|---|---|---|
| RN-07 | Una enfermedad, una región, un tipo de intervención o un lote de vacuna que ya se usó no se borra: se da de baja | RF-B01 |
| RN-08 | El nombre de cada enfermedad, el de cada tipo de intervención y el usuario de cada cuenta son únicos | RF-B01, RF-L01 |
| RN-09 | Los parámetros de una enfermedad no son negativos y caben en lo que acepta el motor | RF-B10 |
| RN-10 | No se registra un lote de vacuna caducado | RF-C04 |
| RN-11 | No se aplican dosis de un lote caducado, aunque el lote se conserve | RF-C13 |
| RN-33 | Todo parámetro de enfermedad y todo costo lleva su fuente o la marca de supuesto. Si falta un dato, el sistema se niega a simular | RF-B09 |

## Escenarios

| ID | Regla | Requerimiento |
|---|---|---|
| RN-12 | Una versión nace en `borrador`. Sus estados son `borrador`, `en_revision`, `aprobado` y `rechazado`, y solo se aprueba con una revisión explícita | RF-D01, RF-D15, RF-D16 |
| RN-13 | Solo una versión `aprobado` puede lanzar corridas (D5) | RF-E01 |
| RN-14 | Una versión nueva conserva de cuál partió, y las anteriores no se borran | RF-D04 |
| RN-15 | El XML de un escenario valida contra `escenario.xsd` antes de exportarse o importarse | RF-D06, RF-D07 |
| RN-16 | Un escenario tiene exactamente una enfermedad y una región del catálogo | RF-D01 |
| RN-17 | En una intervención, el día de inicio no pasa del día de fin | RF-D02 |
| RN-34 | Una versión es una fotografía: congela la población y los parámetros con los que se creó (D5). Cambiar el catálogo después no la cambia | RF-D04 |
| RN-38 | Solo quien creó el escenario, o un ADMINISTRADOR, lo envía a revisión | RF-D15 |

## Corridas y resultados

| ID | Regla | Requerimiento |
|---|---|---|
| RN-18 | Un lote se lanza sobre versiones aprobadas, con el mismo número de réplicas y las mismas semillas (1 a N) en todas (D8) | RF-E04, RF-E09 |
| RN-19 | Cada réplica es una corrida, con su semilla. Son 30 por omisión y 100 como máximo; con menos de 30, la app pide confirmación (D8) | RF-E03 |
| RN-20 | La serie diaria de una corrida va a MongoDB (`series_corridas`) y su resumen a `simulation_runs` (D28). Si MongoDB no responde, la corrida termina con su resumen y la serie se reintenta (RNF-C08) | RF-E20 |
| RN-21 | Una corrida pasa de `encolado` a `ejecutando`, y de ahí a `completado` o a `fallido`. Se puede cancelar (`cancelado`). No pasa de `encolado` a `completado` | RF-E02, RF-E06 |
| RN-22 | Una comparación usa solo corridas completadas, y solo las semillas comunes a todas las versiones | RF-F06 |
| RN-35 | Toda pantalla de resultados muestra el aviso de que no es una predicción (`AVISO_SIMULACION`) | RF-F19 |
| RN-36 | La comparación muestra opciones y costos; no recomienda un escenario | RF-F07 |
| RN-40 | La frontera de Pareto usa personas-día. El costo en pesos va aparte y no entra a la frontera (D3) | RF-F05 |

## Vigilancia en campo

| ID | Regla | Requerimiento |
|---|---|---|
| RN-23 | Un caso lleva enfermedad y municipio; sin ellos no se guarda ni se sincroniza | RF-C01, RF-C06 |
| RN-24 | Un caso nace en `pendiente`. Sus estados son `pendiente`, `validado`, `duplicado` y `descartado`; el CAPTURISTA no lo cambia | RF-C08 |
| RN-26 | Toda foto pertenece a un caso que ya existe en el servidor | RF-C03 |
| RN-27 | Un caso capturado sin conexión queda pendiente hasta que el servidor confirma que lo recibió. Se puede trabajar sin conexión sin límite de tiempo, y cerrar sesión no borra lo pendiente (D19) | RF-C07, RF-I21 |
| RN-28 | Al sincronizar, un caso no se repite: el servidor no acepta dos veces el mismo `local_uuid` | RF-C09 |
| RN-39 | Un lote que trae casos nuevos genera un solo aviso a los EPIDEMIOLOGO, no uno por caso. Un reintento no vuelve a avisar (D32) | RF-C19 |

## Vacunación

| ID | Regla | Requerimiento |
|---|---|---|
| RN-29 | Toda dosis se aplica a un lote vigente | RF-C13 |
| RN-30 | Las dosis aplicadas de un lote no pasan de las que tiene | RF-C13 |

## Auditoría

| ID | Regla | Requerimiento |
|---|---|---|
| RN-31 | Todo alta, cambio, baja o cambio de estado se registra en la auditoría, en la misma transacción y sin depender de que alguien lo anote | RF-A06 |
| RN-32 | Un registro de la auditoría no se edita ni se borra | RF-A06 |

## Retiradas

| ID | Qué decía | Por qué sale |
|---|---|---|
| RN-25 | Registrar si un caso es de campo o histórico para calibración | La calibración queda fuera (D24); todos los casos son de campo o de la demostración |
