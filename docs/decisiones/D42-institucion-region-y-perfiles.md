# D42 - Institución, región y perfiles de cada cuenta

Fecha: 2026-11-20 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del líder) · Amplía D1

## Contexto
La retroalimentación pide para `usuarios` «asignación institucional y regional, perfiles de epidemiólogo, capturista, analista, investigador, administrador y autoridad sanitaria». Hoy una cuenta solo tiene un rol (D1: cuatro). Faltan la institución y la región de la cuenta, y dos perfiles: INVESTIGADOR y AUTORIDAD SANITARIA. El checklist (bloque 0) y el perfil de Android (B) y de la web (C) esperan esto.

## Opciones consideradas
- Opción A: institución y región como texto libre en `users`.
- Opción B: un catálogo de instituciones y la región con llave foránea a `regions`, las dos opcionales.

## Decisión
Opción B.

- `institutions` (migración 052): `code` y `name` únicos, `is_active`. Empieza vacío: no se inventan instituciones; el ADMINISTRADOR las da de alta (`POST /api/v1/institutions` en `usuarios`, que es su dueño).
- `users.institution_id` y `users.region_id`, opcionales (`ON DELETE SET NULL`). Se fijan al crear o editar la cuenta en `usuarios` y salen en `/users/me` y `/users/{id}` con el nombre de cada una. **Son datos del perfil: por sí solos no limitan lo que la cuenta ve** (eso es el alcance de D43).
- Perfiles nuevos, como filas de `roles`: `INVESTIGADOR` y `AUTORIDAD_SANITARIA`. Los seis perfiles son los que nombra la retroalimentación; los roles existentes no cambian.
- Permisos de los perfiles nuevos en `role_permissions`, **como supuesto de solo lectura**: ambos `catalogs.read`, `scenarios.read`, `simulations.read`, `cases.read`, `reports.read` y `reports.export`; el INVESTIGADOR además `scenarios.export`. Ninguno escribe, aprueba ni lee la bitácora. El líder los confirma.

## Consecuencias
- Los candados de cada servicio listan roles (`@requiere_token(roles=...)`): hasta que cada dueño agregue INVESTIGADOR o AUTORIDAD_SANITARIA a las rutas de lectura que les correspondan, ambos entran, ven su perfil (`/users/me`) y nada más. Es una decisión de cada bloque dueño, con la matriz de permisos a la vista.
- La app móvil y la web muestran institución y región en el perfil con `GET /api/v1/users/me`, y llenan los selectores con `GET /api/v1/institutions`.
- El menú por perfil de campo (B) y el de la web (C) dependen de los dos perfiles nuevos.
- Una institución se desactiva (`is_active`), no se borra.
