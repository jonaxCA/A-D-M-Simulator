# D18 - Una sola instancia de PostgreSQL con un rol por servicio

Fecha: 2026-09-24 (migración 009) · Estado: Aceptada (2026-11-08)

## Contexto
Los servicios comparten una instancia de PostgreSQL. Sin separación de privilegios, cualquiera escribiría en cualquier tabla (migración 009).

## Opciones consideradas
- Opción A: una instancia, un rol por servicio.
- Opción B: una base por servicio.

## Decisión
Opción A. Cada servicio lee todo y escribe solo en las tablas de su dominio.

## Consecuencias
- La responsabilidad se vuelve un permiso de la base.
- Cada servicio nuevo pide un rol y una migración (026 a 030 ya agregan roles).
- En GCP las contraseñas se inyectan como variables de entorno.
