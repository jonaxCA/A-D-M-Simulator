# Tercer parcial

- [`checklist.md`](checklist.md): las tareas de cada bloque. Empieza por «Alcance acordado» y «Lo que la retroalimentación reabre».
- [`RETROALIMENTACION_SEGUNDO_PARCIAL.txt`](RETROALIMENTACION_SEGUNDO_PARCIAL.txt): lo que pidió el profesor. Manda sobre todo lo demás.
- [`preguntas0.md`](preguntas0.md): las respuestas a las decisiones del bloque 0.

## Aviso para el salón 1 (A, B y C) · 2026-11-18

El checklist se rehízo con la retroalimentación del profesor. Varias casillas de ustedes esperan una decisión nueva del bloque 0 o una ruta del backend que todavía no existe, y el bloque 0 va a tardar en contestar. Pueden empezar ya con lo que no espera a nadie.

### Mientras tanto

1. **Una decisión pendiente no se adivina.** Deja esa casilla sin hacer y sigue con otra.
2. **No inventes rutas ni contratos.** Los que existen están en [`docs/contratos/`](../../contratos/) y en el [catálogo](../../arquitectura/microservicios.md). Si falta una ruta, pídesela al dueño del servicio («Dueños de los servicios» del checklist): D es Rolando, E es Enrique y F es Jonathan. Mientras llega, prueba con respuestas falsas.
3. **Web: nada de SQL nuevo en `backend_web`.** La web va a dejar de ir directo a PostgreSQL (C6). Lo que hagas con SQL nuevo se tira después.
4. **Dudas:** abre un issue con tu bloque y la casilla, y sigue con lo demás. Los PR van a `feat/tercer-parcial`.

### A · Escritorio

- **Ya:** A1 (la propuesta de la interfaz es tuya), A2 salvo el bucket, y en A4: revisar la app contra la lista, configuración del modelo, editor, intervenciones, ejecución, comparación, análisis económico, Pareto, reportes, reproducibilidad, mapas regionales (con `zonas`, que ya existe) y que cada gráfica diga su fuente, periodo, modelo, versión y unidades.
- **Espera:** proyectos (bloque 0 y D), gestión de datos (D6), calibración, validación y sensibilidad (bloque 0 y E), auditoría de un escenario (D7), subir el reporte al bucket (D2) y el dominio con HTTPS (F).

### B · Android

- **Ya:** B1 salvo las fotos, B2 salvo el dominio, y en B4: revisar la app contra la lista, panel del capturista, GPS con selección manual, cola local cifrada, no dar un caso por recibido hasta que el servidor lo confirme, consulta agregada (con `indicadores`, `series` y `zonas`) y control de calidad en el teléfono.
- **Espera:** editar y dar seguimiento a casos, y los conflictos al sincronizar (bloque 0 y F7); formularios por enfermedad y las alertas nuevas (F7); institución y región en el perfil, y el menú por perfil de campo (bloque 0 y E7); las fotos en el bucket (D2), y el dominio con HTTPS (F).

### C · Web

- **Ya:** el inventario de C6 (cada pantalla y cada consulta, con el servicio que debería atenderla; es lo primero que se necesita para mover la web), C1, C2, C5, el rótulo de personas-día en `/comparacion` (C3) y revisar la web contra la lista de C7.
- **Espera:**
  - **Pasar cada módulo a su servicio (C6):** la decisión que reemplaza D20 y las rutas de E9.
  - **Los avisos de P2 (C4) y fijar las personas-día por dosis (C3):** se resuelven en los servicios. `aprobacion` ya avisa al autor, e `intervenciones` ya fija el factor; no los hagas con SQL.
  - **Campañas y seguimiento de intervenciones:** bloque 0.
  - **Institución y región de cada cuenta:** E7.
  - **Fotos y reportes en el bucket:** D2.
