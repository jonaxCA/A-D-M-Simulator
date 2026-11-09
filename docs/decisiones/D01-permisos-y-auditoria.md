# D1 - Quién captura casos, aprueba versiones y consulta la auditoría

Fecha: 2026-11-07 · Estado: Aceptada

## Contexto
La matriz de permisos (`docs/requerimentos/matriz-permisos.md`) sale del plan del primer parcial y está marcada «revisar». Propone: el capturista registra casos (RN-04), el analista crea escenarios (RN-05, «propuesta»), el epidemiólogo aprueba o rechaza versiones (RN-03 y RN-12) y solo el administrador consulta la auditoría (RF-L05). `AGENTS.md` deja abiertas justo esas tres preguntas. Los permisos viven en `role_permissions` (migración 010) y cada ruta lleva su candado.

## Opciones consideradas
Las preguntas, la tabla de desajustes entre el código y la matriz, y la propuesta de cambio están en la sección D1 de [`propuesta_correcciones_primer_parcial.md`](../propuesta_correcciones_primer_parcial.md).

La asignación de la matriz actual, que sirve de punto de partida, está en esa misma sección.

## Decisión
Respuestas del equipo a las preguntas de la sección D1 de la propuesta, más la aprobación de versiones:

- **Captura de casos (`cases.create`):** solo CAPTURISTA, desde la app móvil. Se quita la captura desde la web.
- **Alta de enfermedades (`catalogs.create`):** EPIDEMIOLOGO y ADMINISTRADOR.
- **Auditoría (`audit.read`):** solo ADMINISTRADOR.
- **CAPTURISTA en la web:** no entra. Solo usa la app móvil.
- **Aprobar o rechazar versiones (`scenarios.approve`):** EPIDEMIOLOGO y ADMINISTRADOR. Aprobar autoriza simular; publicar (`scenarios.publish`) es un permiso aparte.

## Consecuencias
Bloquea el menú por rol de la web, de Android y de escritorio, la matriz de permisos y la sección de seguridad de la v3. Cualquier cambio de rol exige una migración nueva sobre `role_permissions`.

- La migración 010 da `audit.read` al EPIDEMIOLOGO. Se quita con una migración nueva (034, porque la 031 a la 033 son de D27), no editando la 010. La 034 también crea `scenarios.approve`.
- `catalogs.create` coincide con la migración 010.
- La app móvil se entrega en el tercer parcial (D10). Hasta entonces el CAPTURISTA no tiene pantalla en el segundo parcial: su captura se prueba por la API o la consola de pruebas.
- El paso 22 de la prueba de aceptación (auditoría del flujo completo) lo revisa el ADMINISTRADOR.
- Sin responder: si el ADMINISTRADOR también captura casos. La respuesta 1 dice solo CAPTURISTA; la matriz tampoco le da captura, pero la migración 010 le da todos los permisos.
- Los cambios de código y de documentos que se siguen de esta decisión están en [`todo.md`](todo.md), sección «Cambios pendientes por D1». No están implementados.
