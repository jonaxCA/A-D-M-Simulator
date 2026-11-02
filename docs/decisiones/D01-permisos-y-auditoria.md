# D1 - Quién captura casos, aprueba versiones y consulta la auditoría

Fecha: — · Estado: Pendiente

## Contexto
La matriz de permisos (`docs/requerimentos/matriz-permisos.md`) sale del plan del primer parcial y está marcada «revisar». Propone: el capturista registra casos (RN-04), el analista crea escenarios (RN-05, «propuesta»), el epidemiólogo aprueba o rechaza versiones (RN-03 y RN-12) y solo el administrador consulta la auditoría (RF-L05). `AGENTS.md` deja abiertas justo esas tres preguntas. Los permisos viven en `role_permissions` (migración 010) y cada ruta lleva su candado.

## Opciones consideradas
Las opciones de la «Corrección 1» no están en el repositorio, así que no se pueden listar aquí. Hay que recuperarlas o definirlas de nuevo antes de decidir.

Lo único documentado es la asignación de la matriz actual, que sirve de punto de partida.

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Bloquea el menú por rol de la web, de Android y de escritorio, la matriz de permisos y la sección de seguridad de la v3. Cualquier cambio de rol exige una migración nueva sobre `role_permissions`.
