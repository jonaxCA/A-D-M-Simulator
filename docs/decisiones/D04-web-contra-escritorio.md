# D4 - Reparto del trabajo con escenarios entre la web y la app de escritorio

Fecha: — · Estado: Pendiente

## Contexto
La rúbrica pide que la app de escritorio consuma solo XML, atienda un proceso distinto al de la móvil y no sea una copia de la web. Hoy la web hace todo el trabajo con escenarios. `escenarios-xml` ya exporta e importa escenarios en XML validado con XSD.

## Opciones consideradas
Propuestas por validar (no hay opciones registradas):
- Opción A: el escritorio concentra el diseño, la importación y exportación en XML y el envío a revisión (proceso P2 de `brechas_v3.md`); la web conserva consulta, tablero y resultados.
- Opción B: la web conserva todo lo de escenarios y el escritorio se dedica a simulación, comparación y reportes (proceso P3).

## Decisión
Pendiente. Se registra aquí cuando se tome.

## Consecuencias
Define el proceso de la app de escritorio, sus cuatro microservicios mínimos y qué se quita de la web, si algo. Depende de D1 para saber qué rol usa cada app.

Depende de: D1
