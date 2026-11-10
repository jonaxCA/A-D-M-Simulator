# D18 - Una sola instancia de PostgreSQL con un rol por servicio

Fecha: 2026-09-24 (migración 009); roles por servicio desde la 026 · Estado: Aceptada (2026-11-08)

## Contexto
Los servicios comparten una instancia de PostgreSQL. Sin separación de privilegios, cualquiera escribiría en cualquier tabla. La migración 009 creó los primeros roles (`app_*`), que leen todas las tablas. La 026 creó un rol `svc_<servicio>` por microservicio con permisos acotados, y de la 027 a la 033 se agregan los demás.

## Opciones consideradas
- Opción A: una instancia, un rol por servicio.
- Opción B: una base por servicio.

## Decisión
Opción A. Cada servicio lee solo las tablas que consultan sus funciones y escribe solo en las de su dominio (mínimo privilegio). Cada migración de roles revoca todo y vuelve a otorgar exactamente eso.

Se eligió porque los servicios reutilizan las funciones de `backend_web`, que consultan tablas de varios dominios; con una base por servicio habría que reescribirlas.

## Consecuencias
- La responsabilidad se vuelve un permiso de la base.
- Cada servicio nuevo pide un rol y una migración (de la 026 a la 033 ya hay roles).
- Una tabla nueva no la lee ningún servicio hasta que una migración se la otorgue al rol que la necesita. Los roles `svc_*` no tienen privilegios por omisión; los de la 009 (`ALTER DEFAULT PRIVILEGES`) solo aplican a los `app_*`.
- El monolito (`epidemia_app`) y los roles `app_*` quedan fuera de esta regla. Ver las preguntas abiertas en `todo.md`.
- En GCP las contraseñas se inyectan como variables de entorno.
