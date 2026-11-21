# EPIDEMIA - Servicio usuarios

Administra cuentas: alta, consulta, edición, baja lógica y borrado, con su institución y región
opcionales (D42), y el catálogo de instituciones. Escribe `users` e `institutions`; el
rol de cada cuenta lo asigna el servicio `roles`, dueño de `user_roles`.

Puerto externo: 5203; puerto interno en Docker: 8000. Contrato en
`docs/contratos/usuarios/openapi.json`.

## Rutas

Todas piden token con rol `ADMINISTRADOR`, como las pantallas de usuarios del monolito, salvo
`/users/me` (cualquier cuenta consulta la suya: el perfil de la app móvil) y `GET /institutions`.

| Método | Ruta                                     | Qué hace |
|--------|------------------------------------------|----------|
| GET    | `/api/v1/users/me`                       | La cuenta del token, con los mismos campos que `/users/{id}`, incluidas la `institucion` y la `region` (nombre). Cualquier rol |
| GET    | `/api/v1/users`                          | Lista con filtros `q`, `role_id` y `status` (`activo`, `pendiente`, `inactivo`) |
| GET    | `/api/v1/users/summary`                  | Total, `activos`, `pendientes` e `inactivos`, con los estados de la lista (pantalla de usuarios de la web) |
| POST   | `/api/v1/users`                          | Alta con `username`, `email`, `full_name`, `password`, `is_active`, `institution_id` y `region_id` (los tres últimos opcionales); responde 201 |
| GET    | `/api/v1/users/{id}`                     | Una cuenta con su `role_id` y sus `roles` |
| PUT    | `/api/v1/users/{id}`                     | Edita `email`, `full_name` y, si vienen, `password`, `institution_id` y `region_id` (`null` los quita) |
| POST   | `/api/v1/users/{id}/activate` y `/deactivate` | Baja o alta lógica |
| DELETE | `/api/v1/users/{id}`                     | Borra solo si no tiene dependencias |
| GET    | `/api/v1/institutions`                   | El catálogo de instituciones (`id`, `code`, `name`, `is_active`). Cualquier rol |
| POST   | `/api/v1/institutions`                   | Alta con `code` (se guarda en mayúsculas) y `name`; responde 201 |
| PUT    | `/api/v1/institutions/{id}`              | Edita `name` e `is_active` |

- Usa sus reglas en `usuarios/datos.py`: `valida_usuario()`, `hash_password()` (bcrypt),
  `get_usuarios_lista()`, `get_usuario()` y `dependencias_usuario()`.
- Nunca regresa ni audita `password_hash`. Cada escritura se audita (`CREATE`, `UPDATE`,
  `DELETE`) en la misma transacción.
- El `username` no se edita, igual que en el monolito. Nadie puede desactivarse ni eliminarse a sí
  mismo (409).
- Desactivar, eliminar o cambiar la contraseña **cierra todas las sesiones** de la cuenta con
  `sesiones.cerrar_de_usuario()` (ruta interna de `sesiones`, `SERVICIO_SESIONES_URL`), antes de confirmar el cambio: si Redis está
  caído, responde 503 y no guarda nada.
- Con dependencias (casos, escenarios, corridas…), eliminar responde 409: se usa `deactivate`.
- La institución y la región son datos del perfil (D42): no limitan lo que la cuenta ve. Eso es el alcance,
  que guarda el servicio `roles` (D43). Un id que no existe es 422. Los perfiles INVESTIGADOR y
  AUTORIDAD_SANITARIA son roles nuevos que asigna `roles`.

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

Corre en `infra/docker-compose.yml`. Cierra las sesiones llamando a la ruta interna de `sesiones`
con un token de servicio (`SERVICIO_SESIONES_URL`).
