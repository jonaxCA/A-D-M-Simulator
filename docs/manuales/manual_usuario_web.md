# Manual de usuario · Sistema web EPIDEMIA

> **Estado: Vigente** · 2026-11-22 · Corresponde a `frontend_web/` del tercer parcial (bloque C, RNF-E08).

## 1. Para qué sirve

El sistema web sirve para **seguir la situación epidemiológica de Nuevo León y revisar los
escenarios simulados**. En él se consultan:

- el tablero y el mapa;
- los casos que llegan de campo;
- las campañas de salud;
- los escenarios, las corridas y su comparación de costo contra impacto.

El epidemiólogo, además, aprueba o rechaza las versiones de escenario.

Hay cosas que se hacen en otra aplicación:

- Los escenarios se crean y se editan en la **app de escritorio**, y desde ahí se lanzan las
  corridas.
- Los casos se capturan en la **app móvil**.

> **Aviso.** Los resultados de las simulaciones son escenarios con parámetros y supuestos. **No
> son una predicción epidemiológica ni una recomendación sanitaria.** El aviso aparece en todas
> las pantallas de resultados, junto con la categoría de la corrida (exploratoria, mientras no
> haya calibración). Elegir entre las opciones es una decisión humana.

### Quién entra y a qué

| Pantalla | Administrador | Epidemiólogo | Analista | Capturista |
|---|---|---|---|---|
| Tablero y mapa | ✓ | ✓ | ✓ | ✓ |
| Vigilancia y campañas (consulta) | ✓ | ✓ | ✓ | — |
| Validar, descartar o marcar duplicado un caso | — | ✓ | — | — |
| Crear y cancelar campañas | ✓ | ✓ | — | — |
| Monitoreo, reportes y descargas CSV | ✓ | ✓ | ✓ | — |
| Enfermedades y regiones (consulta) | ✓ | ✓ | ✓ | — |
| Dar de alta o editar enfermedades y sus parámetros | ✓ | ✓ | — | — |
| Corregir la población y las bandas de edad de un municipio | ✓ | — | — | — |
| Escenarios, seguimiento de intervenciones, simulaciones y comparación | ✓ | ✓ | ✓ | — |
| Aprobar o rechazar una versión (nunca la propia) | ✓ | ✓ | — | — |
| Costos y personas-día de las intervenciones | ✓ | ✓ | — | — |
| Usuarios y bitácora de auditoría | ✓ | — | — | — |
| Avisos | ✓ | ✓ | ✓ | — |

Si entras a una pantalla que tu rol no tiene, verás **«No tienes acceso a esta sección»**. El
intento queda en la bitácora. El capturista solo ve el tablero y el mapa: captura en la app móvil.

## 2. Entrar y salir

1. Abre la dirección del sitio (en la nube, `https://epidemos.app`; en local,
   `http://127.0.0.1:5000`).
2. Pulsa **Iniciar sesión**. Escribe tu usuario y tu contraseña, y responde el captcha.
3. Para salir, abre el menú de tu inicial (arriba a la derecha) y pulsa **Cerrar sesión**. La
   sesión queda cerrada en el servidor: el enlace ya no sirve aunque alguien lo copie.

La sesión dura hasta 8 horas y se renueva sola mientras la usas. Si dice que la sesión venció,
entra de nuevo.

### Verificación en dos pasos

Cuando el MFA está prendido (D40), el administrador, el epidemiólogo y la autoridad sanitaria dan un
segundo paso después de la contraseña:

- **Si ya tienes el segundo factor:** escribe los 6 dígitos de tu app autenticadora, o uno de tus
  códigos de respaldo.
- **La primera vez:**
  1. Pide a un administrador tu **código de alta**.
  2. Escríbelo y agrega a tu app autenticadora la clave que te muestra la pantalla.
  3. Escribe el código de 6 dígitos que te dé la app.
  4. La pantalla te muestra tus **códigos de respaldo** una sola vez: guárdalos.
- **El paso vence en 5 minutos.** Si vence, inicia sesión otra vez.
- **Varios códigos incorrectos bloquean el segundo paso** durante 15 minutos.

## 3. Tablero y mapa

- **Tablero:** casos activos, tasa de incidencia, zonas en riesgo y simulaciones en curso. Lo
  acompañan la curva de los últimos 30 días y el resumen por enfermedad.
- **Mapa epidemiológico:** la incidencia por cada 100 mil habitantes en los 51 municipios. Elige
  el periodo (7, 30 o 60 días) y la enfermedad. La línea de tiempo recorre el periodo día por
  día, y al pulsar un municipio se ven sus cifras y su tendencia de 14 días.

Ambas pantallas se leen en un teléfono: el menú pasa a una franja que se desliza de lado.

Cada gráfica dice debajo su fuente, su periodo y sus unidades. En las de resultados dice también
el modelo y la versión del escenario.

## 4. Vigilancia y campañas

- **Vigilancia:** los casos de campo por enfermedad, municipio, estado y rango de fechas. Pulsa
  **Seguimiento** para ver un caso, sus fotos y su historial de cambios.
  - Las fotos y PDF del caso se abren con un enlace que vence en 15 minutos. Si abres una
    después de ese tiempo, la web pide uno nuevo.
- **El epidemiólogo** cambia el estado de un caso: lo valida, lo descarta, lo marca duplicado
  de otro o lo reabre.
  - Descartar y marcar duplicado piden un motivo. Quien capturó el caso recibe el aviso.
  - Si otra persona cambió el caso mientras lo veías, la pantalla te lo dice y no guarda nada.
    Recarga y vuelve a intentarlo.
- **Campañas:** las campañas de salud por enfermedad y municipio, con su periodo y su estado.
  - El epidemiólogo y el administrador las registran y las cancelan.
  - Al registrar una, los capturistas reciben el aviso en la app móvil.

## 5. Monitoreo y reportes

- **Monitoreo:** la evolución de los casos, la distribución por edad y sexo, y la tabla por zona.
  La tabla se ordena por incidencia o por casos. **Exportar CSV** baja la tabla con los mismos
  filtros.
- **Reportes:** reúne las descargas: el resumen de situación, el monitoreo por zona y el
  catálogo de enfermedades. Cada descarga queda en la bitácora con quien la pidió.
  - Abajo se listan los reportes de comparaciones que ya están guardados. **Abrir** descarga el
    PDF con un enlace que vence en 15 minutos.

## 6. Catálogos

- **Enfermedades:** buscar, filtrar por estado y exportar.
  - El epidemiólogo y el administrador dan de alta una enfermedad, la editan, y la activan o
    desactivan (nunca se borra).
  - Cada parámetro (R0, letalidad, etc.) lleva su **fuente** o la casilla **Es supuesto**. Sin
    una de las dos, no se guarda.
  - Si falta un parámetro, la enfermedad no se puede simular.
- **Regiones:** la población de Nuevo León y de sus municipios, con su fuente.
  - El administrador corrige la población total o las bandas de edad de un municipio, siempre
    con un motivo.
  - El total del estado y la población de 60 años o más se recalculan solos.

## 7. Escenarios, simulaciones y comparación

- **Escenarios:** la lista y el detalle de cada versión. El detalle muestra:
  - la población, las intervenciones en una línea de tiempo y el historial de versiones;
  - lo que dice el motor de esa versión.
- **Revisiones** (epidemiólogo y administrador): las versiones que esperan dictamen.
  - En el detalle de la versión, escribe el motivo y pulsa **Aprobar** o **Rechazar**.
  - Rechazar exige motivo. Nadie revisa una versión que escribió.
  - En los dos casos quien la armó recibe el aviso.
- **Simulaciones:** las corridas recientes y su estado. La pantalla de una corrida se actualiza
  sola mientras está en curso y, al terminar, muestra:
  - sus indicadores y sus curvas;
  - los parámetros que usó, con su fuente;
  - si otra corrida con la misma semilla dio lo mismo (reproducibilidad).
- **Comparación:** marca dos o más corridas completadas y pulsa **Comparar seleccionadas**.
  - Se ven sus curvas y la gráfica de costo contra fallecimientos, con la frontera de Pareto.
  - El costo de la frontera está en **personas-día**. El costo en pesos se muestra aparte y no
    entra en la frontera.
  - El sistema no elige una alternativa.
  - Abajo de las curvas, **Reporte de esta comparación** lista los PDF guardados de esas corridas.
    El analista y el administrador suben uno: elige el PDF (hasta 20 MB), pon un título si
    quieres y pulsa **Subir reporte**. Se revisa su contenido y su huella antes de guardarlo; si
    ya estaba subido, se queda el mismo.
- **Intervenciones** (seguimiento, D51): por cada versión aprobada se ve:
  - lo que se programó: tipo, días del horizonte, cobertura y cumplimiento;
  - su costo en pesos y, para la vacunación, sus personas-día por dosis;
  - las corridas que la simularon, con un enlace para compararlas;
  - para la vacunación, las campañas de su enfermedad.
  - Los días son del horizonte simulado, no fechas de calendario.
- **Editar costos** (epidemiólogo y administrador): el costo en pesos de cada tipo de
  intervención y las **personas-día por dosis** de la vacunación, cada uno con su fuente o su
  marca de supuesto. Sin ese factor, la comparación de escenarios con vacunación se niega.

## 8. Avisos

La campana de arriba muestra cuántos avisos tienes sin leer. En **Avisos** ves:

- las versiones por revisar;
- los casos nuevos, descartados o incompletos;
- las campañas;
- los dictámenes de tus versiones;
- las alertas del sistema.

Cada aviso lleva a su escenario, corrida o caso. Pulsa **Marcar como leído** cuando lo atiendas.

## 9. Administración (solo administrador)

- **Usuarios:**
  - dar de alta, editar, desactivar o eliminar cuentas;
  - asignar el rol, la institución y la región de cada cuenta.
  - Desactivar cierra sus sesiones.
  - Una cuenta con registros no se elimina: se desactiva.
- **Auditoría:** la bitácora de todo el sistema (quién hizo qué, cuándo y desde dónde), con
  filtros por usuario, módulo y acción.

## 10. Cuando algo falla

- **«Este dato no está disponible por ahora (servicio …)»:** ese servicio no respondió. Lo demás
  de la página sí está al día. Intenta en unos minutos.
- **«El cambio no se guardó»:** el formulario no llegó a guardarse. Vuelve a enviarlo cuando el
  servicio responda.
- **«La página venció o el formulario no es de este sitio»:** recarga la página y vuelve a
  enviar el formulario. Es la protección contra formularios falsos (CSRF).
- **«Algo salió mal»:** el error quedó registrado. Si se repite, avisa al administrador con la
  hora. La pantalla nunca muestra detalles técnicos.
- **Sin el servicio de sesiones no se puede entrar.** Es a propósito: la web no deja pasar si no
  puede revisar tu sesión.
