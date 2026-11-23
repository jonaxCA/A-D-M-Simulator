# D51 - Seguimiento de intervenciones en la web

Fecha: 2026-11-22 · Estado: Propuesta (bloque C; falta que la valide E, como delegó el bloque 0 en #176) · Amplía D4 y D49

## Contexto
La retroalimentación pide para la aplicación web «seguimiento de intervenciones» y no dice qué es.
El bloque 0 lo delegó a C y E el 2026-11-22. Hoy una intervención solo existe dentro de una versión
de escenario (`scenario_interventions`):

- tiene tipo, días de inicio y fin dentro del horizonte simulado, cobertura, cumplimiento y
  parámetros;
- su costo y sus personas-día por dosis viven en el tipo (`intervention_types`, D3);
- no tiene fechas de calendario ni registro de cómo se aplicó en la realidad.

Lo único de la vida real que se le parece son las campañas de D49.

## Opciones consideradas
- A) Consulta con lo que ya existe. Por cada versión aprobada: sus intervenciones programadas, su
  costo, las corridas que la simularon y, para las de vacunación, las campañas de su enfermedad.
- B) Ejecución real contra el plan. Una tabla nueva con fechas reales, cobertura lograda y
  responsable de cada intervención, comparada con lo programado. Pide una migración, un servicio
  de E y que alguien capture esos datos.
- C) Dejarlo fuera.

## Decisión
**Opción A.** «Seguimiento de intervenciones» en la web es la pantalla `/intervenciones`, de solo
lectura y con el permiso `scenarios.read` (ADMINISTRADOR, EPIDEMIOLOGO y ANALISTA). Por cada versión
aprobada muestra:

- **Lo programado:** cada intervención con su tipo, capa, días de inicio y fin, cobertura y
  cumplimiento (servicio `intervenciones`).
- **Su costo:**
  - el unitario en pesos, con su unidad, su fuente o su marca de supuesto;
  - para los tipos por dosis, las personas-día por dosis (`tipos-intervencion`, D3).
  - Sin costo capturado, lo dice.
- **Lo simulado:** las corridas de esa versión, con su estado y un enlace a cada una (`corridas`).
  Con dos o más completadas, un enlace para compararlas.
- **Lo aplicado:**
  - para las intervenciones por dosis (vacunación), las campañas de la misma enfermedad (`vacunas`,
    D49);
  - las demás no tienen todavía registro de aplicación.

No se crea tabla ni ruta nueva: la pantalla solo junta lo que ya dan cinco servicios.

## Consecuencias
- Cubre el punto «Seguimiento de intervenciones» de C7 sin esperar a otro bloque.
- No compara lo planeado con lo aplicado, salvo para la vacunación a través de las campañas. Si se
  necesita esa comparación (opción B), es una decisión nueva con su migración (número del líder) y
  su servicio (E).
- La pantalla hace una llamada a `intervenciones` por cada versión aprobada. Con las versiones de la
  demostración basta; si crecen, `intervenciones` necesitaría una consulta de varias versiones a la
  vez.
- Las campañas se relacionan por el nombre de la enfermedad, porque la lista de versiones no trae su
  `disease_id`.

Depende de: D3, D4, D36, D49
