# D48 - Formularios de captura por enfermedad, con versiones

Fecha: 2026-11-22 · Estado: Aceptada (aprobada por el dueño del bloque F; pendiente de validación del líder) · Atiende la retroalimentación de la app móvil (formularios por enfermedad) · Amplía D1 y D47

## Contexto
La retroalimentación pide formularios definidos por enfermedad, con versiones, validaciones y datos
obligatorios. Hoy los campos de un caso son fijos (enfermedad, municipio, fechas, edad, sexo,
ubicación, resultado y gravedad): un dato propio de una enfermedad (los signos de alarma del dengue,
por ejemplo) no tiene dónde ir. La app captura sin conexión, así que un caso puede llegar días
después con una versión del formulario que ya no es la vigente.

## Opciones consideradas
- Dónde: A) columnas nuevas en `cases` por cada dato; B) un formulario por enfermedad, versionado,
  y las respuestas en un JSON del caso.
- Edición: A) se edita la versión publicada; B) borrador que se publica y ya no cambia.
- Sin respuestas: A) obligatorio desde que haya formulario; B) se acepta mientras la versión
  vigente no lo pida.

## Decisión
- **B: formulario por enfermedad.** Los campos fijos del caso no cambian; cada enfermedad suma los
  suyos en `case_forms` (migración 059), una fila por versión, con sus campos en orden: clave,
  etiqueta, tipo (texto, entero, decimal, fecha, booleano, opcion, opciones), obligatorio y, según el
  tipo, mínimo, máximo, largo máximo u opciones. Un campo no repite uno fijo del caso. El caso
  guarda `form_id` (la versión con que se capturó) y `form_answers` (las respuestas, ya validadas).
- **B: versiones inmutables.** El EPIDEMIOLOGO y el ADMINISTRADOR (quienes dan de alta enfermedades,
  D1) crean un borrador, lo editan y lo publican. Publicado ya no cambia: para cambiarlo se crea y
  publica otra versión, y la anterior pasa a `retirado`, que sigue valiendo para los casos
  capturados con ella sin conexión. A lo más un borrador y una publicada por enfermedad.
- **Validación en `casos`:** al capturar, al recibir un lote y al corregir (D47), las respuestas se
  validan contra la versión del caso (de su enfermedad, publicada o retirada): obligatorios, tipos,
  rangos y opciones, con todos los motivos juntos en el 422.
- **B: sin respuestas se acepta por ahora.** La app actual todavía no manda formularios (B4); si
  fuera obligatorio, todo lo que capture de esa enfermedad se rechazaría. Cada versión trae
  `required`: cuando la app ya lo soporte, se publica una versión con `required` en true y desde ese
  momento un caso de la enfermedad sin sus respuestas es 422.
- Rutas en `casos`: `GET /forms`, `GET /forms/current` (lo que la app guarda para capturar sin red),
  `GET /forms/{id}`, `POST /forms`, `PUT /forms/{id}` y `POST /forms/{id}/publish`. Los borradores solo
  los ven quienes los arman.

## Consecuencias
- La app móvil (B4) baja los formularios vigentes, arma la captura con ellos y manda `form_id` y
  `form_answers` en cada caso (también en el lote de `sincronizacion`). No lo hace todavía.
- Las respuestas viven en JSON: los indicadores, series y zonas no las agregan. Si un dato se vuelve
  indicador, se decide aparte si pasa a columna.
- Cambiar la enfermedad de un caso con formulario pide el formulario de la nueva (o quitarlo).
- La web o el escritorio pueden ofrecer el editor de formularios; hoy se arman por la API o la
  consola de pruebas.
