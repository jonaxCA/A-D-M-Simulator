> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-L: Administración del sistema

Función de soporte: lo que solo hace el ADMINISTRADOR. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A (sesión y roles).
- PostgreSQL: `users`, `user_roles`, `devices`, `audit_log`.
- PostgreSQL: también `institutions` y `user_scopes`.
- Servicios: `usuarios`, `roles`, `sesiones`, `dispositivos`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-L01 | El ADMINISTRADOR crea, edita, activa, desactiva y elimina cuentas | Otro rol recibe 403 (RN-02). Una cuenta inactiva no inicia sesión (RN-06). La contraseña tiene al menos 8 caracteres. Cada cambio queda en la auditoría | Soporte | Web, Microservicios | Alta | Hecho |
| RF-L02 | El ADMINISTRADOR asigna el rol de cada cuenta | Toda cuenta queda con un rol (RN-01). El cambio queda en la auditoría | Soporte | Web, Microservicios | Alta | Hecho |
| RF-L03 | Se puede revocar un teléfono | `dispositivos` marca el teléfono como revocado; desde entonces no sincroniza (RF-C21) | Soporte | Microservicios | Media | Hecho |
| RF-L04 | Se pueden cerrar todas las sesiones de un usuario | `sesiones` revoca las sesiones de esa cuenta; su siguiente petición responde 401 | Soporte | Microservicios, Seguridad | Media | Hecho |
| RF-L05 | El ADMINISTRADOR consulta la bitácora de auditoría | Solo el ADMINISTRADOR la ve (D1). Se ve quién hizo qué, sobre qué y cuándo | Soporte | Web, Seguridad | Alta | En parte: la web ya la limita al ADMINISTRADOR; falta la migración 034, que quita `audit.read` al EPIDEMIOLOGO. `roles` la consulta con filtros por entidad, usuario, acción y fechas, y paginada (`GET /api/v1/audit`) |
| RF-L11 | Cada cuenta tiene institución y región opcionales, y existen los perfiles INVESTIGADOR y AUTORIDAD_SANITARIA (D42) | El ADMINISTRADOR las fija al crear o editar la cuenta y salen en `/users/me`. El catálogo de instituciones lo administra el ADMINISTRADOR y lo lee cualquier rol. Cada cambio queda en la auditoría | Soporte | Microservicios | Alta | Hecho en `usuarios` (migración 052); los permisos de los perfiles nuevos son un supuesto por validar |
| RF-L12 | Una cuenta puede limitarse a regiones o instituciones (D43) | Sin alcance es nacional. Solo el ADMINISTRADOR lo asigna; cada cuenta consulta el suyo. Cada cambio queda en la auditoría | Soporte | Microservicios | Media | En parte: `roles` guarda y expone el alcance (migración 053); falta que cada servicio lo aplique a sus datos |
| RF-L13 | El historial de un escenario muestra quién lo creó, modificó, revisó o aprobó (D43) | `GET /api/v1/audit/history/...` para ADMINISTRADOR, EPIDEMIOLOGO y ANALISTA, sin la IP | Soporte | Microservicios, Escritorio | Media | Hecho en `roles`; el escritorio lo consume (A4). `escenarios` da además los responsables de cada versión (`GET /scenarios/{id}/versions`: autor, envío, revisor, devolución y firma; D54) |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-L06 | Cambiar parámetros del sistema (umbrales, límites) | `system_settings` existe, pero ningún código la lee ni hay pantalla. Los límites se fijan por variables de entorno |
| RF-L07 | Administrar los archivos de Cloud Storage | Cada servicio es dueño de sus archivos (D30) |
| RF-L08 | Respaldos automáticos de PostgreSQL | No lo pide la rúbrica ni ninguna decisión |
| RF-L09 | Restaurar desde un respaldo | Igual que RF-L08 |
| RF-L10 | Modo de mantenimiento | Ningún proceso lo pide |
