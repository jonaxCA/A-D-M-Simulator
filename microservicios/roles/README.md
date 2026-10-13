# EPIDEMIA - Servicio roles

Consulta los roles y sus permisos, y asigna el rol de una cuenta. Escribe solo `user_roles`;
lee `roles`, `permissions` y `role_permissions`.

Puerto externo: 5204; puerto interno en Docker: 8000. Contrato en
`docs/contratos/roles/openapi.json`.

## Rutas

Todas piden token con rol `ADMINISTRADOR`, como las pantallas de usuarios del monolito.

| Método | Ruta                                    | Qué hace |
|--------|-----------------------------------------|----------|
| GET    | `/api/v1/roles`                         | Roles (`id`, `code`, `name`) ordenados por nombre |
| GET    | `/api/v1/roles/{id}/permissions`        | El rol con sus permisos (`code`, `resource`, `action`, `description`) |
| PUT    | `/api/v1/roles/assignments/{user_id}`   | Recibe `role_id` y reemplaza el rol de la cuenta |

- **Un rol por cuenta**, como en el monolito ("un solo rol por usuario en esta versión"): la
  asignación reemplaza el que tenga y guarda quién lo asignó (`assigned_by`).
- Si el rol cambia, se audita `UPDATE` sobre `users` (con `role_ids` antes y después) y se
  **cierran todas las sesiones** de la cuenta: sus access llevan los roles con que se emitieron.
  Si es el mismo rol, no escribe nada.
- Nadie puede quitarse a sí mismo el rol de `ADMINISTRADOR` (409).

| Caso                                    | HTTP | `codigo`                 |
|-----------------------------------------|------|--------------------------|
| Falta `role_id`, no es válido o no existe | 422 | `DATOS_INVALIDOS`       |
| No existe la cuenta o el rol (permisos) | 404  | `NO_ENCONTRADO`          |
| Quitarse el rol de administrador        | 409  | `CONFLICTO`              |
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

Pendiente: entrada en el compose (bloque J). Hoy cierra las sesiones con la biblioteca común,
sobre el mismo Redis; cuando exista el token de servicio (bloque L) puede hacerlo por HTTP con la
ruta interna de `sesiones`.
