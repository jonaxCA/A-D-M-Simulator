# EPIDEMIA - Servicio usuarios

Administra cuentas: alta, consulta, edición, baja lógica y borrado. Escribe solo `users`; el
rol de cada cuenta lo asigna el servicio `roles`, dueño de `user_roles`.

Puerto externo: 5203; puerto interno en Docker: 8000. Contrato en
`docs/contratos/usuarios/openapi.json`.

## Rutas

Todas piden token con rol `ADMINISTRADOR`, como las pantallas de usuarios del monolito.

| Método | Ruta                                     | Qué hace |
|--------|------------------------------------------|----------|
| GET    | `/api/v1/users`                          | Lista con filtros `q`, `role_id` y `status` (`activo`, `pendiente`, `inactivo`) |
| POST   | `/api/v1/users`                          | Alta con `username`, `email`, `full_name`, `password` e `is_active` (opcional); responde 201 |
| GET    | `/api/v1/users/{id}`                     | Una cuenta con su `role_id` y sus `roles` |
| PUT    | `/api/v1/users/{id}`                     | Edita `email`, `full_name` y, si viene, `password` |
| POST   | `/api/v1/users/{id}/activate` y `/deactivate` | Baja o alta lógica |
| DELETE | `/api/v1/users/{id}`                     | Borra solo si no tiene dependencias |

- Usa las reglas de `backend_web`: `valida_usuario()`, `hash_password()` (bcrypt),
  `get_usuarios_lista()`, `get_usuario()` y `dependencias_usuario()`.
- Nunca regresa ni audita `password_hash`. Cada escritura se audita (`CREATE`, `UPDATE`,
  `DELETE`) en la misma transacción.
- El `username` no se edita, igual que en el monolito. Nadie puede desactivarse ni eliminarse a sí
  mismo (409).
- Desactivar, eliminar o cambiar la contraseña **cierra todas las sesiones** de la cuenta con
  `sesiones.cerrar_todas()` de la biblioteca común, antes de confirmar el cambio: si Redis está
  caído, responde 503 y no guarda nada.
- Con dependencias (casos, escenarios, corridas…), eliminar responde 409: se usa `deactivate`.

| Caso                                  | HTTP | `codigo`                 |
|---------------------------------------|------|--------------------------|
| Datos inválidos o campo no permitido  | 422  | `DATOS_INVALIDOS`        |
| Usuario o correo repetido             | 409  | `CONFLICTO`              |
| Con dependencias o sobre sí mismo     | 409  | `CONFLICTO`              |
| No existe la cuenta                   | 404  | `NO_ENCONTRADO`          |
| Redis caído                           | 503  | `SERVICIO_NO_DISPONIBLE` |

## Variables

`DATABASE_URL`, `JWT_SECRET_KEY` y `REDIS_URL`, las mismas que `auth` y `sesiones`.

## Probarlo

```bash
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios/usuarios -q
python -m microservicios.usuarios.app

# Con el access de una cuenta ADMINISTRADOR (POST /api/v1/auth/login):
curl -H "Authorization: Bearer <access>" "http://127.0.0.1:5203/api/v1/users?format=json"
curl -X POST -H "Authorization: Bearer <access>" "http://127.0.0.1:5203/api/v1/users/9/deactivate?format=json"
```

Pendiente: entrada en el compose (bloque J). Hoy cierra las sesiones con la biblioteca común,
sobre el mismo Redis; cuando exista el token de servicio (bloque L) puede hacerlo por HTTP con la
ruta interna de `sesiones`.
