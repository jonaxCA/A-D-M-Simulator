# AGENTS.md — docs/contratos

> **Estado: Vigente** · 2026-10-12 · Complementa `microservicios/AGENTS.md`. Las tareas son
> el bloque M del checklist (`docs/CHECKLIST_SEGUNDO_PARCIAL.md`).

Aquí está el contrato de cada microservicio, en una carpeta por servicio:
`docs/contratos/<servicio>/`. Las apps de escritorio y móvil se construyen a partir de estos
archivos, así que un contrato que no coincide con el servicio es un error del servicio.

## Qué lleva cada carpeta

- `openapi.json` (OpenAPI 3): idéntico al que sirve el servicio en `/openapi.json`. Una
  prueba los compara.
- Un ejemplo de respuesta en JSON y otro en XML por ruta; en las rutas que reciben cuerpo,
  también un ejemplo de petición.
- Un `.xsd` cuando el recurso viaja en XML como documento propio: escenario, resultado de
  una corrida, enfermedad con sus parámetros, caso, lote de sincronización, el error
  (`problem+xml`) y, para la app de escritorio, las respuestas de corridas, intervenciones,
  aprobación, comparación y Pareto. Los tipos compartidos están en `comun/tipos.xsd` y la
  serie diaria de una corrida, en `comun/serie.xsd`.

## Reglas

1. El contrato cambia en el **mismo PR** que la ruta. Una ruta sin contrato no está
   terminada.
2. Todo va bajo `/api/v1/`. Un cambio incompatible (quitar un campo, cambiar un tipo o un
   nombre) crea `/api/v2/`, y `v1` sigue funcionando.
3. Los nombres de campos, las claves y los códigos de error son los de la biblioteca común
   y del catálogo. No inventes otros para un solo servicio.
4. Los ejemplos XML validan contra su `.xsd` con `xmlschema`, y los JSON contra el esquema
   del `openapi.json`. Una prueba de `pytest` lo revisa.
5. En los ejemplos no hay datos reales de personas, tokens ni contraseñas.
6. `README.md` de esta carpeta: cómo leer los contratos y dónde está cada uno.
