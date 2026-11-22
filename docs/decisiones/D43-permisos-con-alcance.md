# D43 - Permisos con alcance por región o institución, e historial de una entidad

Fecha: 2026-11-20 · Estado: Aceptada · Amplía D1 y D42

## Contexto
La retroalimentación pide permisos «por recurso, región, institución y operación». Hoy el permiso es (recurso, operación) en `role_permissions` y no hay forma de limitar a una cuenta a los datos de una región o de una institución. Además, el escritorio necesita el historial de un escenario (quién lo creó, modificó, revisó o aprobó) y D1 deja la bitácora solo al ADMINISTRADOR.

## Opciones consideradas
- Opción A: una tabla de permisos por (rol, recurso, operación, región).
- Opción B: el permiso sigue siendo (recurso, operación) por rol, y el alcance es una asignación por cuenta.

## Decisión
Opción B, para no multiplicar la matriz por rol y región.

- **Permiso** = (recurso, operación), como hoy.
- **Alcance** (migración 053, `user_scopes`): las regiones o instituciones a las que se limita una cuenta. **Sin alcance, la cuenta es nacional.** Con alcance, solo ve y actúa sobre los datos de esas regiones (y sus hijas, vía `regions.parent_region_id`) o de esas instituciones. Si tiene de las dos, basta con cumplir una.
- **Dueño:** `roles`. `GET /api/v1/scopes/me` (cualquier rol) regresa el alcance de la cuenta del token, con `regiones_cubiertas` ya expandidas; `GET` y `PUT /api/v1/scopes/{user_id}` son del ADMINISTRADOR (el `PUT` reemplaza todo y audita `UPDATE` sobre `user_scopes`). Los demás servicios piden el alcance a `roles` por HTTP con `llamar()` y el token de la persona (D37); no leen `user_scopes`.
- **Aplicarlo es de cada servicio dueño de los datos**, porque el filtro depende de cada tabla: `region_id` en `cases`, `scenarios`, `vaccine_lots` y las corridas (por su escenario); para la institución, los datos que capturaron o crearon cuentas de esa institución (`users.institution_id`). Esta decisión no filtra nada todavía: deja el alcance consultable y auditado, y la lista de servicios por cubrir está en el README de `roles`.
- **Historial de una entidad:** `GET /api/v1/audit/history/{entity_type}/{entity_id}` (solo `scenarios`, `scenario_versions` y `scenario_interventions`) lo consultan ADMINISTRADOR, EPIDEMIOLOGO y ANALISTA y no trae la IP; para una cuenta con alcance por región, solo el de escenarios de esas regiones (migración 055: `svc_roles` lee la región). La bitácora completa (`/api/v1/audit`, con filtros, rango de fechas y paginación) sigue siendo solo del ADMINISTRADOR (D1).

## Consecuencias
- Un cambio de alcance no cierra sesiones: no va en el token, se consulta en cada petición que lo necesite.
- Amplía D1 en un punto: el historial de escenarios deja de ser solo del ADMINISTRADOR. El líder confirma si se acepta; si no, el escritorio lo arma con los campos de autor y revisor de `escenarios`.
- La institución como alcance depende de definir cuál dato pertenece a una institución; hasta entonces solo el alcance por región se puede aplicar sin ambigüedad.
- **Estado de la institución (E8):** ningún dato de E trae una institución propia (ni `cases`, ni `scenarios`, ni las corridas tienen `institution_id`); solo la tendrían de forma indirecta, por la cuenta que los creó. Por eso el alcance por institución se guarda y se consulta (`GET /scopes/me`), pero **ningún servicio lo aplica todavía** (una cuenta con solo alcance por institución no se limita en los datos regionales: se trata como nacional hasta que se aplique), y no se agregó ninguna migración: los roles `svc_*` solo leen `id` e `is_active` de `users`, y darles `institution_id` solo tiene sentido cuando el equipo decida si «pertenecer a una institución» significa el autor del dato, quien lo revisó o los dos. Cuando se decida, la migración será un `GRANT SELECT (institution_id)` a los servicios que filtren.
