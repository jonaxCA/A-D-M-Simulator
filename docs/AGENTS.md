> **Estado: Vigente** · 2026-11-01

## Qué hay aquí

- `arquitectura/`: arquitectura (v1 obsoleta, v2 vigente), contexto, catálogo de microservicios y modelo de datos.
- `contratos/`: contratos por servicio (OpenAPI, XSD, ejemplos) y colección de Postman. Tiene su propio `AGENTS.md`.
- `decisiones/`: ADRs (`decisiones.md`), plantilla (`plantilla_ADR.md`) y pendientes.
- `desarrollo/`: guías para desarrollar (por escribir).
- `parciales/`: planes de desarrollo por parcial.
- `requerimentos/`: requerimientos funcionales y no funcionales, reglas, matriz de permisos y trazabilidad. Obsoletos: piden actualización.
- `rubrica/`: textos de la materia. No se edita.
- `INSTALACION.md`: instalación y base de pruebas.
- `todo.md`: pendientes generales de la documentación.

## Reglas

1. No tomes como fuente un documento que en su encabezado diga **Obsoleto**.
2. Si un documento contradice `decisiones/decisiones.md`, ganan las decisiones.
3. El esquema de la base son las migraciones de `datos/postgres/migraciones/`, no estos documentos.
4. Las decisiones abiertas (D1 a D8) no se implementan sin preguntar; marca su estado en `decisiones/decisiones.md` cuando se tomen.
7. Mantén los cambios pequeños y en español; no dupliques contenido entre carpetas, enlaza.

## Al editar

- Actualiza el índice de esta carpeta (la lista de arriba) si agregas o quitas un directorio.
- Revisa los enlaces relativos después de mover archivos.
