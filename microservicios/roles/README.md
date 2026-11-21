# EPIDEMIA - Servicio roles

Consulta los roles y sus permisos, asigna el rol de una cuenta, consulta la bitácora (D37) y guarda
el alcance por región o institución de cada cuenta (D43). Escribe `user_roles` y `user_scopes`
(migración 053); lee `roles`, `permissions`, `role_permissions`, `audit_log` (migración 046),
`regions` e `institutions`.

Puerto externo: 5204; puerto interno en Docker: 8000. Contrato en
`docs/contratos/roles/openapi.json`.

## Rutas

Piden token con rol `ADMINISTRADOR`, como las pantallas de usuarios del monolito, salvo `/audit/history`
(`ADMINISTRADOR`, `EPIDEMIOLOGO` y `ANALISTA`) y `/scopes/me` (cualquier rol).

| Método | Ruta                                    | Qué hace |
|--------|-----------------------------------------|----------|
| GET    | `/api/v1/roles`                         | Roles (`id`, `code`, `name`) ordenados por nombre |
| GET    | `/api/v1/roles/{id}/permissions`        | El rol con sus permisos (`code`, `resource`, `action`, `description`) |
| PUT    | `/api/v1/roles/assignments/{user_id}`   | Recibe `role_id` y reemplaza el rol de la cuenta |
| GET    | `/api/v1/audit`                         | Eventos de la bitácora, del más reciente al más viejo. Filtros `q`, `user_id`, `module`, `entity_id`, `action` (también `RUN::<etapa>`), `from` y `to` (ISO 8601; `to` con solo fecha incluye ese día) y paginación `limit` (1 a 500, 100 por omisión) y `offset`. Regresa `coincidencias` (el total que cumple los filtros) y, por evento, `usuario_id`, `antes` (`data_before`) y `datos` (`data_after`) |
| GET    | `/api/v1/audit/summary`                 | Eventos totales, `criticas` (`PERMISSION_DENIED`), `fallidos` (`LOGIN_FAILED`) y `activos_24h` |
| GET    | `/api/v1/audit/filters`                 | Los `modulos`, `acciones` y `usuarios` que ya aparecen en la bitácora, para los filtros |
| GET    | `/api/v1/audit/history/{tipo}/{id}`     | Historial de una entidad (`scenarios`, `scenario_versions` o `scenario_interventions`; otro tipo es 404) sin la IP, con `limit` y `offset`. Es la vista del escritorio: quién creó, modificó, revisó o aprobó. Una versión tiene su propio `id`, así que el historial de un escenario son el suyo y el de cada versión |
| GET    | `/api/v1/scopes/me`                     | El alcance de la cuenta del token (cualquier rol): `nacional`, `region_ids`, `regiones_cubiertas` (con las hijas) e `institution_ids` |
| GET    | `/api/v1/scopes/{user_id}`              | Igual, de otra cuenta |
| PUT    | `/api/v1/scopes/{user_id}`              | Reemplaza el alcance con `region_ids` e `institution_ids` (listas; vacías = nacional) y audita `UPDATE` sobre `user_scopes` |

- **Un rol por cuenta**, como en el monolito ("un solo rol por usuario en esta versión"): la
  asignación reemplaza el que tenga y guarda quién lo asignó (`assigned_by`).
- Si el rol cambia, se audita `UPDATE` sobre `users` (con `role_ids` antes y después) y se
  **cierran todas las sesiones** de la cuenta: sus access llevan los roles con que se emitieron.
  Si es el mismo rol, no escribe nada.
- Nadie puede quitarse a sí mismo el rol de `ADMINISTRADOR` (409).
- **Bitácora (D1, D43).** `/audit` es solo del `ADMINISTRADOR`: trae la IP de todo el sistema. El historial
  de una entidad es una vista acotada, sin IP y solo de entidades de escenarios; una cuenta con alcance por región (D43) solo ve el de escenarios de sus regiones (403 si no), y `svc_roles` lee la región de `scenarios` por la migración 055.
- **Alcance (D43).** `auth`, `sesiones`, `usuarios` y `roles` no guardan datos por región ni institución, así que no filtran nada: el ADMINISTRADOR administra cuentas, roles e instituciones a nivel nacional. Sin filas en `user_scopes` la cuenta es nacional. No va en el token ni cierra sesiones:
  los servicios lo piden con `llamar()` y el token de la persona (`GET /scopes/me`). **Hoy ningún servicio
  lo aplica**: cada dueño lo agrega a sus consultas de lectura y escritura donde corresponda: `casos` y
  `sincronizacion` (`cases.region_id`), `escenarios`, `intervenciones` y `aprobacion` (`scenarios.region_id`),
  `vacunas` (`vaccine_lots.region_id`), `corridas`, `resultados`, `comparacion` y `pareto` (por el escenario de
  la corrida), `indicadores`, `series` y `zonas`. La institución se aplica por `users.institution_id` de quien
  capturó o creó el dato, una vez que el líder valide D43.

| Caso                                    | HTTP | `codigo`                 |
|-----------------------------------------|------|--------------------------|
| Falta `role_id`, no es válido o no existe | 422 | `DATOS_INVALIDOS`       |
| No existe la cuenta o el rol (permisos) | 404  | `NO_ENCONTRADO`          |
| Quitarse el rol de administrador        | 409  | `CONFLICTO`              |
| Tipo de entidad sin historial           | 404  | `NO_ENCONTRADO`          |
| `from`/`to`/`offset`/`limit` mal formados, o un id de alcance inexistente | 422 | `DATOS_INVALIDOS` |
| Redis caído                             | 503  | `SERVICIO_NO_DISPONIBLE` |

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`, las mismas que `auth` y `sesiones`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/roles -q
python -m microservicios.roles.app

# Con el access de una cuenta ADMINISTRADOR (POST /api/v1/auth/login):
curl -H "Authorization: Bearer <access>" "http://127.0.0.1:5204/api/v1/roles?format=json"
curl -X PUT -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
     -d '{"role_id": 2}' "http://127.0.0.1:5204/api/v1/roles/assignments/9?format=json"
```

Corre en `infra/docker-compose.yml`. Cierra las sesiones llamando a la ruta interna de `sesiones`
con un token de servicio (`SERVICIO_SESIONES_URL`).
