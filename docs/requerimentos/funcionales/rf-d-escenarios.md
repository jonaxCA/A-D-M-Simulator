> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-D: Gestión de escenarios

Es el proceso **P2** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md): el ANALISTA arma un escenario en la app de escritorio, lo valida, lo intercambia en XML y lo envía a revisión; un EPIDEMIOLOGO lo aprueba o lo rechaza en la web (D4). Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles), RF-B (catálogos) y RF-H (la app de escritorio).
- PostgreSQL: `scenarios`, `scenario_versions`, `scenario_interventions`, `research_projects`, `notifications`.
- Servicios: `escenarios`, `intervenciones`, `validacion`, `escenarios-xml`, `aprobacion`, `notificaciones`.
- Contrato del XML: [`escenario.xsd`](../../contratos/escenarios-xml/escenario.xsd).

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-D01 | El ANALISTA crea un escenario con su enfermedad, su región y su población | El escenario y su primera versión nacen en `borrador` (RN-12); queda `CREATE` de `scenarios` en la auditoría | 2.3 | Escritorio, Microservicios | Alta | Hecho |
| RF-D02 | El ANALISTA agrega, quita y mueve intervenciones de una versión en borrador | Cada intervención lleva su tipo, su día de inicio y de fin, y los parámetros que pide su `param_schema`. El inicio no pasa del fin (RN-17). Quedan `CREATE`, `DELETE` y `UPDATE` de `scenario_interventions` en la auditoría | 2.4 | Escritorio, Microservicios | Alta | Hecho |
| RF-D03 | La versión se valida contra el motor antes de enviarla | `validacion` responde la lista de errores, o que no hay; no guarda nada | 2.5 | Microservicios | Alta | Hecho |
| RF-D04 | Una versión es una fotografía: congela la población y los parámetros (D5). Cambiar un escenario es crear una versión nueva | La versión nueva conserva de cuál partió, y las anteriores no se borran (RN-14); queda `CREATE` de `scenario_versions` en la auditoría | 2.3 | Microservicios, Bases de datos | Alta | Hecho |
| RF-D06 | La versión se exporta a un archivo `.xml` | El archivo valida contra `escenario.xsd` | 2.6 | Escritorio, Microservicios | Alta | Hecho |
| RF-D07 | Un escenario se importa desde un `.xml` | El archivo se valida contra `escenario.xsd` en la app y en el servidor. Si valida, se crean el escenario y sus intervenciones, con `CREATE` en la auditoría; si no, no se crea nada | 2.6 | Escritorio, Microservicios | Alta | Hecho |
| RF-D08 | Un escenario se duplica como punto de partida | El duplicado nace en `borrador`, con las intervenciones del original | 2.3 | Escritorio, Microservicios | Media | Hecho |
| RF-D12 | Un escenario se archiva sin borrarlo, y se restaura (reabierto por la retroalimentación) | Solo quien lo creó o un ADMINISTRADOR, y no con la versión vigente en revisión (409). Archivado es de solo lectura: no recibe versiones, cambios de intervenciones, envíos ni corridas (la base las rechaza), deja de ser público y no sale en la lista salvo con `?archived=true`. Queda `UPDATE` de `scenarios` en la auditoría (D54) | Soporte | Microservicios, Bases de datos | Media | Hecho en `escenarios` (064); falta la pantalla del escritorio (A4) |
| RF-D13 | El reparto por rol: el ANALISTA crea y edita; EPIDEMIOLOGO y ADMINISTRADOR aprueban o rechazan; nadie revisa su propia versión | Un rol sin permiso recibe 403. La base impide que el autor sea el revisor (RN-03) | 2.3 a 2.8 | Seguridad, Bases de datos | Alta | Hecho |
| RF-D15 | El ANALISTA envía la versión a revisión | Solo quien creó el escenario, o un ADMINISTRADOR. La versión pasa a `en_revision`; queda `UPDATE` de `scenario_versions` en la auditoría. Se avisa a los EPIDEMIOLOGO | 2.7 | Escritorio, Microservicios | Alta | Hecho |
| RF-D16 | El EPIDEMIOLOGO revisa la bandeja de la web y aprueba, rechaza o devuelve con un comentario | La versión pasa a `aprobado` o `rechazado` con quién, cuándo y el comentario, o vuelve a `borrador` con el motivo para que su autor la corrija y la reenvíe (D55); queda `UPDATE` en la auditoría. Se avisa al autor en los tres casos | 2.8 | Web, Microservicios | Alta | En parte: `aprobacion` avisa al aprobar, al rechazar y al devolver; la web todavía no ofrece devolver (C) |
| RF-D17 | El ANALISTA ve el aviso y el estado de su versión | El aviso aparece en la app y se marca como leído al abrirlo | 2.9 | Escritorio, Microservicios | Media | Hecho |
| RF-D18 | La web consulta escenarios y versiones, sin editarlos (D4) | ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR ven la lista y el detalle. Un escenario en borrador avisa que se edita en el escritorio | Soporte | Web | Media | Hecho |
| RF-D19 | Un proyecto de investigación agrupa escenarios de una enfermedad y una región, con su objetivo, su periodo de estudio y sus motores (retroalimentación, escritorio) | ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR lo crean y lo cambian (solo su dueño o un ADMINISTRADOR); INVESTIGADOR y AUTORIDAD_SANITARIA lo leen; el alcance por región aplica (D43). Un escenario solo entra a un proyecto activo de su misma enfermedad y región (la base lo impide). No se borra: se archiva. Queda `CREATE`/`UPDATE` de `research_projects` en la auditoría (D54) | 2.3 | Escritorio, Microservicios, Bases de datos | Media | Hecho en `escenarios` (064); falta la pantalla del escritorio (A4) |
| RF-D20 | La versión aprobada queda firmada | Al aprobar se guarda la SHA-256 de la entrada canónica del motor (`approval_sha256`), la misma huella que guarda cada corrida; `GET /versions/{id}/signature` la verifica y cuenta las corridas que simularon exactamente lo firmado (D55) | 2.8 | Microservicios, Bases de datos | Media | Hecho en `aprobacion` y `validacion` (064) |

El XML de intercambio no se guarda en Cloud Storage: P2 queda sin bucket (D32). Guardarlo es opcional, si sobra tiempo.

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-D05 | Mostrar las diferencias entre dos versiones | Ningún proceso lo pide |
| RF-D09 | Marcar un escenario como publicado para el sitio público | El permiso `scenarios.publish` existe, pero ninguna pantalla ni servicio publica. Aprobar autoriza simular; publicar es aparte (D1) |
| RF-D10 | Etiquetar escenarios | Ningún proceso lo pide |
| RF-D11 | Pasar un escenario de pruebas a producción | Se cubre con exportar e importar el XML (RF-D06 y RF-D07) |
| RF-D14 | Plantillas de escenarios | Se cubre con duplicar (RF-D08) |
