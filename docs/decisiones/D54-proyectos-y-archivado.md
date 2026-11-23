# D54 - Proyectos de investigación y archivado de escenarios

Fecha: 2026-11-23 · Estado: Aceptada · Atiende RF-D12 (reabierto) y RF-D19 · Amplía D5 · Aplica D42, D43 y D52

## Contexto
- La retroalimentación pide para el escritorio una «administración de proyectos: crear
  investigaciones, seleccionar región, enfermedad, periodo y modelos», y para `escenarios`
  «archivado». El bloque 0 delegó la definición del proyecto a A y D el 2026-11-22 (checklist, D7 y
  A4, l. 311).
- `scenarios.status` ya admite `archivado` desde la 006, pero nada lo escribe y `svc_escenarios`
  no tiene UPDATE sobre `scenarios` (027). RF-D12 («desactivar un escenario sin borrarlo») estaba
  fuera de alcance.
- No hay ninguna tabla de proyectos. El escritorio ya elige región, enfermedad, horizonte y motor
  por escenario y por corrida.

## Opciones consideradas
- **Qué es un proyecto:** A) un agrupador de escenarios en `escenarios`; B) lo mismo, más una lista
  de miembros que da acceso a sus escenarios; C) un servicio nuevo `proyectos`.
- **Archivar:** A) usar `scenarios.status = 'archivado'`, que ya existe; B) una columna aparte
  (`archived_at`).

## Decisión
Proyecto A y archivar A, decididas con el líder el 2026-11-23. Van en la migración 064.

**Un proyecto de investigación** (`research_projects`):
- Agrupa escenarios de **una enfermedad y una región**. Lleva su nombre (único por dueño), su
  objetivo, su periodo de estudio (`period_start` a `period_end`), los motores que contempla
  (`seir-ref`, `abm-ref` o `abm-gpu`) y su estado (`activo` o `archivado`).
- Cada escenario puede pertenecer a uno (`scenarios.project_id`, opcional). Solo entra a un
  proyecto **activo** de su misma enfermedad y región. `escenarios` lo revisa y la base también
  (trigger `fn_escenario_en_proyecto`).
- Lo crean y lo cambian ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR. Cambiarlo, archivarlo o
  restaurarlo es de su dueño o de un ADMINISTRADOR, igual que versionar un escenario.
- La enfermedad y la región no cambian si el proyecto ya tiene escenarios. Un proyecto archivado no
  recibe escenarios ni cambios.
- No se borra (D52): se archiva, y los escenarios lo referencian (`ON DELETE RESTRICT`).
- El periodo y los motores son informativos: el escritorio los usa para ofrecer opciones.
  `corridas` no los exige.

**Archivar un escenario** (RF-D12):
- `POST /api/v1/scenarios/{id}/archive` y `/restore`, por su dueño o un ADMINISTRADOR. Responde
  409 si la versión vigente está en revisión: primero el dictamen.
- Un escenario archivado es **de solo lectura**:
  - `escenarios` no le crea versiones;
  - `intervenciones` no cambia las suyas;
  - `aprobacion` no lo envía a revisión;
  - la base rechaza sus corridas (`fn_version_aprobada`, rehecha en la 064).
- Sus corridas y resultados se siguen consultando, y se puede duplicar.
- Deja de salir en `GET /scenarios` salvo con `?archived=true`.
- Deja de ser público: `ck_scenarios_publico` solo admite `is_public` en uno `publicado`. Al
  restaurarlo vuelve a `borrador` y no se vuelve a publicar, porque ninguna ruta publica (RF-D09
  está fuera).

**El historial con responsables:**
- `GET /scenarios/{id}/versions` da por versión quién la creó, cuándo se envió, quién la revisó y
  cuándo, el comentario, si se devolvió (`devuelta`) y su firma (D55).
- Lo que pasó entre medio está en `roles` (`/audit/history`, D43).
- Archivar, restaurar y mover de proyecto quedan como `UPDATE` de `scenarios`, con su antes y
  después.

**Lectores y alcance:**
- Las lecturas de `escenarios` (escenarios, versiones y proyectos) aceptan también a INVESTIGADOR
  y AUTORIDAD_SANITARIA, que tienen `scenarios.read` (D42).
- Todo `escenarios` aplica el alcance por región de D43: las listas solo traen sus regiones, y lo
  de fuera es 403.

## Consecuencias
- RF-D12 y RF-D19 quedan hechos del lado del servidor. Falta la pantalla del escritorio (A4).
- Duplicar deja la copia en el proyecto del original, si sigue activo.
- **Para E:** `roles` no muestra el historial de `research_projects` (solo acepta escenarios,
  versiones e intervenciones); los asientos están en `audit_log`. `intervenciones`, `aprobacion`
  y `escenarios-xml` todavía no aplican el alcance de D43 (`revision_d7.md`).
- **Para quien rehaga `fn_version_aprobada`:** tiene que conservar el rechazo de los escenarios
  archivados.

Depende de: D5, D42, D43, D52

## Fuentes
- `docs/parciales/parcial-3/RETROALIMENTACION_SEGUNDO_PARCIAL.txt` (l. 83 y 179) y el checklist
  (D7, A4).
- Migraciones 006 (`ck_scenarios_status` y `ck_scenarios_publico`), 014 (`fn_version_aprobada`) y
  027 (permisos de `svc_escenarios`).
