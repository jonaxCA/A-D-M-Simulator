> **Estado: Vigente** · 2026-11-01

## Qué hay aquí

- `arquitectura/`: arquitectura (v1 y v2 obsoletas, v3 del tercer parcial), procesos, matrices, catálogo de microservicios (`microservicios.md`) y modelo de datos.
- `contratos/`: contratos por servicio (OpenAPI, XSD, ejemplos) y colección de Postman. Tiene su propio `AGENTS.md`.
- `decisiones/`: una decisión por archivo (D1 a D60), el índice con su estado (`decisiones.md`), la plantilla (`plantilla_ADR.md`) y pendientes (`todo.md`).
- `desarrollo/`: guías para desarrollar (por escribir).
- `manuales/`: manuales de usuario de cada aplicación; las capturas van en `manuales/img/`.
- `parciales/`: el checklist de cada parcial y, en el tercero, la retroalimentación y las revisiones.
- `requerimientos/`: requerimientos funcionales y no funcionales, historias de usuario, reglas, matriz de permisos y trazabilidad de la v3. Borrador del 2026-11-16, por validar en equipo; empieza por su `README.md`.
- `pruebas/`: resultados de las pruebas (carga con Locust, volumen, fallos, validación, calibración, despliegue) y cómo repetirlas; empieza por su `README.md`.
- `rubrica/`: textos de la materia. No se edita.
- `README.md`: índice de la carpeta para quien llega nuevo.
- `INSTALACION.md`: instalación y base de pruebas.
- `DESPLIEGUE_GCP.md`: despliegue en la nube.
- `todo.md`: pendientes generales de la documentación.

## Reglas

1. No tomes como fuente un documento que en su encabezado diga **Obsoleto**.
2. Si un documento contradice `decisiones/decisiones.md`, ganan las decisiones.
3. El esquema de la base son las migraciones de `datos/postgres/migraciones/`, no estos documentos.
4. Las decisiones abiertas no se implementan sin preguntar; marca su estado en `decisiones/decisiones.md` cuando se tomen.
5. Mantén los cambios pequeños y en español; no dupliques contenido entre carpetas, enlaza.

## Al editar

- Actualiza el índice de esta carpeta (la lista de arriba y la tabla de `README.md`) si agregas o quitas un directorio.
- Revisa los enlaces relativos después de mover archivos.
