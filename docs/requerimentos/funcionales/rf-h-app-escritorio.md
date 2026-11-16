> **Estado: Borrador** · 2026-11-16 · Por validar en equipo

# RF-H: Aplicación de escritorio

La app de `frontend_desktop/` (PySide6) atiende los procesos **P2** y **P3** de [`procesos_v3.md`](../../arquitectura/procesos_v3.md) para el ANALISTA y el ADMINISTRADOR. Solo habla XML con los microservicios, y no copia a la web: D4 le deja el diseño y las corridas. Cómo leer la tabla: [`README.md`](../README.md).

## Dependencias

- RF-A, RF-B, RF-D, RF-E y RF-F.
- 17 servicios: `estado-servicios`, `auth`, `sesiones`, `usuarios`, `enfermedades`, `regiones`, `tipos-intervencion`, `escenarios`, `intervenciones`, `validacion`, `aprobacion`, `escenarios-xml`, `corridas`, `resultados` (por medio de `comparacion`), `comparacion`, `pareto` y `notificaciones`.

## Requerimientos

| ID | Requerimiento | Criterio de aceptación | Paso | Componente | Prioridad | Estado |
|---|---|---|---|---|---|---|
| RF-H01 | La app tiene su propio inicio de sesión, con captcha | Solo entran ANALISTA y ADMINISTRADOR; a los demás roles los rechaza. Los tokens viven solo en memoria. Si la sesión fue revocada o cerrada, regresa al inicio de sesión | 2.1 | Escritorio, Seguridad | Alta | Hecho |
| RF-H02 | La app lista los escenarios, con búsqueda, y abre uno con sus versiones e intervenciones | La búsqueda filtra la lista; el detalle muestra las versiones y su estado | 2.2 | Escritorio | Alta | Hecho |
| RF-H03 | El detalle de una versión muestra sus intervenciones en una línea de tiempo y en una tabla | Cada intervención aparece como una barra entre su día de inicio y de fin | 2.4 | Escritorio | Alta | Hecho |
| RF-H04 | Las intervenciones se agregan, se quitan y se mueven desde la app | El formulario de cada intervención se arma con el `param_schema` de su tipo | 2.4 | Escritorio | Alta | Hecho |
| RF-H05 | La app exporta una versión a `.xml` y abre un `.xml` local | El archivo se valida contra `escenario.xsd` antes de importarlo; uno inválido no se manda al servidor | 2.6 | Escritorio | Alta | Hecho |
| RF-H07 | La app lanza un lote: N réplicas por cada versión aprobada elegida | Solo ofrece versiones aprobadas. Con menos de 30 réplicas pide confirmación | 3.1 | Escritorio | Alta | Hecho |
| RF-H08 | La app muestra la cola de corridas, con filtro y con el avance de cada una | Se ve qué espera, qué corre y qué terminó, y una rejilla de réplicas por versión | 3.3 | Escritorio | Alta | Hecho |
| RF-H10 | La app compara versiones: encima sus curvas, cada una con su banda | Toma de cada versión una corrida completada por semilla, y solo las semillas comunes | 3.5 | Escritorio | Alta | Hecho |
| RF-H11 | La app dibuja la frontera de Pareto sobre las medianas | La frontera usa el costo que responde `pareto`. La lectura es neutra: no recomienda | 3.5 | Escritorio | Alta | Hecho |
| RF-H13 | La app exporta la comparación a CSV y a PDF, y la imprime | El archivo queda en la computadora. También exporta el historial de corridas a CSV | 3.6 | Escritorio | Alta | Hecho |
| RF-H14 | La app lleva una bitácora local de actividad | `actividad.log` nunca guarda tokens ni contraseñas | Soporte | Escritorio | Baja | Hecho |
| RF-H15 | La app muestra los avisos de `notificaciones` | El aviso de una versión dictaminada o de una corrida terminada aparece en la barra de estado | 2.9, 3.4 | Escritorio | Media | Hecho |
| RF-H17 | El menú depende del perfil | «Forzar error» solo lo ve el ADMINISTRADOR | 2.1 | Escritorio, Seguridad | Alta | Hecho |
| RF-H18 | La app cierra la sesión | Al cerrar, la app olvida los tokens y regresa al inicio de sesión | Soporte | Escritorio | Alta | Hecho |
| RF-H19 | La barra de estado muestra la salud de los servicios y la cola | El estado sale de `estado-servicios` | Soporte | Escritorio, Monitoreo | Media | Hecho |
| RF-H20 | El selector de motor ofrece `abm-gpu` cuando `corridas` lo acepta | El motor aparece solo si está habilitado en ese despliegue | 3.1 | Escritorio | Media | Falta |
| RF-H21 | La app muestra la escala de los resultados (D6) | Junto a los conteos se ve el factor de habitantes por agente | 3.5 | Escritorio | Media | Falta |
| RF-H22 | La app avisa cuando las bandas de dos escenarios se enciman (D8) | Ver RF-F23 | 3.5 | Escritorio | Media | Falta (A3) |
| RF-H23 | La app revisa la expiración del token antes de usarlo | Un token vencido se renueva sin esperar el rechazo del servidor | 2.1 | Escritorio, Seguridad | Baja | Por decidir (C10): hoy lo valida cada servicio, y la app renueva cuando recibe `TOKEN_EXPIRADO` |
| RF-H24 | La app muestra los errores del servidor con un mensaje entendible | Un error llega con su `codigo`, y la app dice qué pasó sin mostrar la traza. Sin red, lo dice y deja reintentar | Todos | Escritorio | Alta | Verificar: ningún paso lo describe |

## Fuera de alcance

| ID | Qué pedía | Por qué sale |
|---|---|---|
| RF-H06 | Subir y bajar escenarios del servidor | La app trabaja siempre contra el servidor; el intercambio de archivos es RF-H05 |
| RF-H09 | Bajar los resultados completos para analizarlos sin conexión | Se cubre con la exportación (RF-H13) |
| RF-H12 | Mapa de incidencia | Repite el mapa de la web (RF-G03) |
| RF-H16 | Editar escenarios sin conexión | La app necesita los servicios para validar y guardar |
| — | Aprobar o rechazar versiones | Es de la web (D4) |
| — | Editar una intervención en su lugar | `intervenciones` no tiene esa ruta: se quita y se vuelve a agregar |
