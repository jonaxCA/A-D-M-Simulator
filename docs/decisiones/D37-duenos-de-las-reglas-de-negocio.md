# D37 - Dueños de las reglas de negocio y servicios sin `backend_web`

Fecha: 2026-11-19 · Estado: Aceptada · Cambia las reglas 2 y 14 y el paso 2 de «Antes de escribir código» de `microservicios/AGENTS.md`

## Contexto
La retroalimentación pide dueños claros de las reglas de negocio, contratos de dominio separados, despliegues independientes y una biblioteca común solo con funciones técnicas. Hoy 27 de los 29 servicios importan `backend_web` directamente, y los 29 lo arrastran porque `epidemia_comun` también lo importa (`ambito.py`, `fabrica.py`, `seguridad.py` y `validaciones.py`). Un cambio en `queries.py` puede obligar a reconstruir y volver a probar todos los servicios.

## Opciones consideradas
- Opción A: un paquete de dominio compartido, separado del monolito, que importen todos.
- Opción B: cada regla se muda al servicio dueño, y los demás se la piden por HTTP.
- Opción C: copiar las reglas en cada servicio que las use.

## Decisión
Opción B. La A cambia el nombre del acoplamiento sin quitarlo. La C reparte la misma regla en varias copias sin pruebas.

**Quién es el dueño:**
- Es dueño de una regla el servicio dueño de la tabla que esa regla protege. El dueño de cada tabla es el que dice el catálogo, en la columna «Escribe».
- Si una regla no escribe (una validación, un cálculo), su dueño es el servicio cuya tarea, según el catálogo, la nombra. Por ejemplo, la coherencia de parámetros es de `validacion` y la frontera es de `pareto`.
- La tabla de dueños de E8 lista cada regla con su servicio. Si una regla no encaja, se decide aquí y se agrega a la tabla.

**Cómo se muda una regla:**
- El código pasa de `backend_web` al servicio dueño (`microservicios/<servicio>/dominio.py` o un módulo con nombre propio), con sus pruebas.
- Si otro servicio la necesita, la llama por HTTP con `llamar()`.
- Cada servicio pasa en su propio PR (D, E y F, cada uno en los suyos).

**Qué se queda en `epidemia_comun`.** Solo lo técnico: fábrica de la app, formato y errores, tokens y su validación, Redis, MongoDB como conexión, HTTP entre servicios, salud, registro y límites.
- `Contexto` (quién actúa) y la consulta de la base para `/health` se mudan a `epidemia_comun` como técnicas.
- `ambito.py` y `validaciones.py` son de dominio y se van con su dueño.
- `series_corridas.py` deja de ser código compartido. El formato del documento queda como contrato en `docs/contratos/series_corridas/` (esquema JSON). Lo escribe `simulador` y lo lee `resultados`, cada uno con su propio código.
- `sesiones.py` de la biblioteca solo *revisa* una sesión, que es técnico y se queda. Crear y cerrar sesiones es del servicio `sesiones`.

**Excepción:** `procesamiento/` (los motores) no es el monolito. Es la biblioteca de los modelos, con su versión (`engine_version`). La importan `simulador` y `validacion`, porque la compatibilidad de un escenario con el motor debe revisarse con el mismo código que lo corre.

**Contratos de dominio:** un servicio solo conoce a otro por su `openapi.json` y su XSD de `docs/contratos/`, nunca por sus clases.

**Despliegue independiente:**
- La imagen de cada servicio copia solo su carpeta, `epidemia_comun` y, si la usa, `procesamiento/`.
- Una prueba revisa que ningún servicio importe `backend_web` ni a otro servicio.
- Se demuestra reconstruyendo un servicio con `--no-deps` sin tocar a los demás (E8).

## Consecuencias
- Un cambio en la web ya no obliga a tocar servicios, y una regla vive en un solo lugar.
- Las 431 pruebas de `backend_web` se reparten entre los servicios dueños. Mientras dura la mudanza conviven, y ninguna prueba se borra sin que su copia pase en el dueño.
- Algunas lecturas que hoy son una consulta local pasan a ser una llamada HTTP: más latencia y un fallo posible más (503 `SERVICIO_NO_DISPONIBLE`).
- La regla 14 («el monolito no se toca para consumir servicios») se retira por D36. El paso 2 de «Antes de escribir código» pasa a decir «busca la regla en su servicio dueño».
- `backend_web` termina siendo solo la capa HTTP de la web (D36).

## Cierre de E8 (2026-11-23)
- Ningún servicio importa `backend_web`; `epidemia/base` queda solo para la consola y la web. Las reglas de `enfermedades`, `escenarios`, `escenarios-xml`, `intervenciones`, `regiones` y `validacion` pasaron a su carpeta. Revisar un escenario es de `validacion`: `escenarios` le pide el dictamen y guarda el formulario normalizado que regresa; las reglas de una intervención son de `intervenciones`, y `validacion` se las pide (`POST /api/v1/interventions/validate`).
- `ambito.py` y `validaciones.py` se quedaron en `epidemia_comun`, pero ya solo con lo técnico: leer y validar parámetros, sin catálogos ni reglas de dominio. Se suma `conversion.py` (leer un número del texto de un formulario).
- **La excepción de `procesamiento/` se amplía:** lo importan los servicios que corren o revisan contra el motor: los de simulación, `calibracion` (D50), `enfermedades` (el estado de los parámetros), `parametros` (los límites) y `validacion`.
- **Copias:** una regla que escribe ya no se copia. El estado del lote, que llevaban `simulador` y `corridas`, es un trigger de la base (065). Las lecturas de solo consulta que otro servicio hace con la misma SQL que el dueño (`get_run`, `version_para_motor`, `escenario_detalle`, los tipos de intervención…) se quedan, porque pedirlas por HTTP no cambia quién decide. A diferencia de la opción C, no van sin pruebas: `test_copias_de_lectura.py` exige que sigan iguales a las del dueño.
