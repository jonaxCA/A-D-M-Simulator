# D59 - Ajustes de los parámetros de la enfermedad en una versión de escenario

Fecha: 2026-11-23 · Estado: Aceptada · Atiende RF-B18 · Amplía D5 y D58 · Aplica D37 y la regla 8 de `AGENTS.md`

## Contexto
La retroalimentación pide, en la configuración del modelo, «seleccionar SEIR u otro modelo implementado, **ajustar parámetros** y visualizar definiciones y unidades» (A4 del checklist).

El escritorio ya elige el motor y muestra definiciones, unidades, rangos, fuentes, intervalos y versiones de los parámetros. Lo que faltaba es ajustarlos:
- Los parámetros de una enfermedad solo se cambian en el **catálogo** (`PUT /api/v1/diseases/{id}/parameters`, de `parametros`), con EPIDEMIOLOGO y ADMINISTRADOR, desde el web (menú Enfermedades). Un cambio mueve todos los escenarios y los borradores.
- El ANALISTA, que arma los escenarios en el escritorio, no podía probar un valor distinto sin cambiar el catálogo de todos.

## Opciones consideradas
- **Dónde viven los ajustes:**
  - A) sobre el borrador de la versión, en una columna nueva;
  - B) solo en el catálogo, sin ajuste por escenario;
  - C) juegos de parámetros con nombre por enfermedad.
- **Qué se puede ajustar:** A) todos los del motor, dentro de sus límites; B) solo dentro del intervalo publicado.
- **Organización:** A) un solo PR en la rama del bloque A; B) dos ramas.

## Decisión
Las tres A, decididas con el líder el 2026-11-23.

- **`scenario_versions.param_overrides` (044):** los parámetros que la versión cambia del catálogo, cada uno con `valor`, `fuente` o `supuesto` y, opcional, su `intervalo`. Vacío si la versión usa el catálogo tal cual. El catálogo no cambia.
- **Parámetros efectivos de una versión:** su fotografía (`disease_params`, D5) si ya salió de borrador; en un borrador, el catálogo vivo con los ajustes encima (`default_params || param_overrides`). Lo calcula `procesamiento.entrada_motor.parametros_efectivos`.
- **Congelar al enviar:** la fotografía de D5 es el catálogo con los ajustes encima. Desde ahí la versión no cambia, y la huella de sus corridas y la firma de D55 ya los reflejan.
- **Solo en borrador:** un ajuste se cambia únicamente en el borrador vigente de un escenario sin archivar, y lo hace su dueño o un ADMINISTRADOR (la regla de las intervenciones). Una versión nueva y un duplicado copian los ajustes; devolver una versión (D55) los conserva.
- **Las reglas son las del catálogo** (`parametros/reglas.py`): valor entre el mínimo y el máximo del motor, fuente o `supuesto: true` (regla 8) e intervalo opcional. Se puede explorar fuera del intervalo publicado: la corrida sigue siendo exploratoria y el ajuste queda marcado.
- **Rutas de `parametros`:** `GET /api/v1/versions/{id}/parameters` (catálogo, ajustes, efectivos y estado de los efectivos; los cinco roles de lectura, con el alcance de D43) y `PUT` (ANALISTA, EPIDEMIOLOGO y ADMINISTRADOR; `null` quita un ajuste). Cada cambio queda en la bitácora con su antes y después.
- **Quien revisa lo ve:** `validacion` agrega un aviso por cada parámetro ajustado y la bandeja de `aprobacion` trae `n_ajustes`.
- **Escritorio:** la pantalla Escenarios agrega **Ajustar parámetros de esta versión**: tabla con el catálogo, el valor de la versión, la incertidumbre y la fuente, y el formulario de ajuste. Las tasas se capturan en %.

## Consecuencias
- Un analista explora un valor distinto sin tocar el catálogo, y el cambio queda auditado, congelado y firmado con la versión.
- Un cambio del catálogo sigue sin llegar a una versión enviada (D5); un ajuste tampoco.
- El monolito, que todavía envía y versiona para el web (D36), aplica lo mismo: su `envia_a_revision`, `crea_version` y `duplica_escenario` copian y congelan los ajustes.
- Fuera de alcance: exportar e importar los ajustes en el XML de `escenarios-xml`, y mostrarlos en el web.
- `simulador` y `pareto` solo corren versiones aprobadas, que ya traen su fotografía; sus consultas leen `param_overrides` para usar el mismo cálculo que la huella.
