# Dueños de las reglas de negocio

> **Estado: Vigente** · 2026-11-20, F el 2026-11-22, D y las copias el 2026-11-23 · E8 (D37). Cada regla vive en un solo servicio; los demás la
> piden por HTTP con `llamar()` y no la reescriben. `epidemia_comun` solo guarda lo técnico
> (verificar tokens, Redis, formatos, errores, llaves). Catálogo: [`microservicios.md`](microservicios.md).

Estado: **movida** = ya vive con su dueño y no queda copia en `epidemia_comun` ni en otro
servicio; **lectura copiada** = otro servicio lee las mismas columnas con la misma consulta, sin
decidir ni escribir nada, y `test_copias_de_lectura.py` exige que siga igual a la del dueño;
**copia del monolito** = la de `backend_web`, que se va cuando se retire (D36).

Ningún servicio importa `backend_web` (2026-11-23): las guardas son `test_sin_backend_web.py`,
`test_simulacion_sin_backend_web.py`, `test_vigilancia_sin_backend_web.py` y
`test_datos_sin_backend_web.py`. `epidemia/base`, la imagen con `backend_web`, queda solo para la
consola y la web. `procesamiento/` es la biblioteca de los modelos y no es de ningún servicio
(D37): la importan los de simulación, `calibracion` y los de D que revisan contra el motor
(`enfermedades`, `parametros` y `validacion`).

## Bloque E: identidad y simulación

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Credenciales, captcha, bloqueo por intentos fallidos, emisión del *access* | `auth` | `auth/datos.py`, `auth/rutas.py` | E | movida |
| MFA: TOTP, códigos de respaldo, restablecer (D40) | `auth` | `auth/mfa.py` | E | movida |
| Abrir sesión, TTL de 8 h y tope de sesiones concurrentes (D41) | `sesiones` | `sesiones/almacen.py`, `POST /api/v1/sessions/internal/open` | E | movida (`auth` la llama por HTTP) |
| Renovar con rotación de *refresh* y detectar su reutilización | `sesiones` | `sesiones/almacen.py` | E | movida |
| Cerrar sesiones (logout, de una cuenta, de un dispositivo) y revocar tokens | `sesiones` | `sesiones/almacen.py`; `usuarios` y `roles` piden `DELETE /sessions/user/{id}` con `epidemia_comun.sesiones.cerrar_de_usuario` | E | movida |
| Dispositivos autorizados de una cuenta (D41) | `sesiones` | `sesiones/dispositivos.py` | E | movida |
| Revisar que un token siga vigente (firma, revocación, sesión abierta) | todos (técnico) | `epidemia_comun/seguridad.py`, `epidemia_comun/sesiones.verificar` | E | se queda en `epidemia_comun` |
| Altas, ediciones y bajas de cuentas; perfil; instituciones (D42) | `usuarios` | `usuarios/datos.py`, `usuarios/rutas.py` | E | movida |
| Roles, permisos y asignación de rol | `roles` | `roles/rutas.py` | E | movida |
| Alcance por región e institución (D43) | `roles` (dueño); los demás lo piden | `roles/rutas.py`, cliente en `epidemia_comun/alcance.py` | E | movida |
| Bitácora: consulta, resumen e historial | `roles` | `roles/rutas.py` | E | movida |
| Lanzar, cancelar y reintentar corridas; prioridad, candado y cola (D44) | `corridas` | `corridas/datos.py`, `corridas/rutas.py` | E | movida |
| Estimación y posición en la cola | `corridas` | `corridas/datos.py` (`estimar_corrida`) | E | movida |
| Ejecutar la corrida, avance, recuperación de interrumpidas (D38) y escribir resultados | `simulador` | `simulador/ejecucion.py`, `trabajador.py`, `datos.py` | E | movida |
| Curvas diarias de una corrida (MongoDB, D28) | `simulador` escribe, `resultados` lee | `simulador/serie.py`, `resultados/serie.py` | E | movida (ya no está en `epidemia_comun`) |
| Resultados, indicadores y banda p5-p95 (D8) | `resultados` | `resultados/rutas.py` | E | movida |
| Comparar corridas: diferencias, incertidumbre y contrafactual | `comparacion` | `comparacion/rutas.py` | E | movida |
| Costo-impacto, frontera de Pareto y sensibilidad | `pareto` | `pareto/dominio.py`, `pareto/rutas.py` | E | movida |
| Elegir hasta N corridas a comparar (`corridas_a_comparar`) | `comparacion` y `pareto` | `comparacion/seleccion.py` y `pareto/seleccion.py`: el mismo archivo, que `test_copias_de_lectura.py` exige igual | E | movida |

## Bloque F: vigilancia, analítica y plataforma

Ninguno de los nueve importa `backend_web` y sus imágenes parten de `epidemia/base-vigilancia`
(`test_vigilancia_sin_backend_web.py`). Lo que la web todavía lee de `backend_web` quedó como
copia, abajo.

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Validar un caso contra los CHECK de `cases` y los catálogos de la captura (`valida_caso`, `get_enfermedades_para_captura`, `get_municipios_catalogo`) | `casos` | `casos/captura.py` y `casos/conversion.py` | F | copia (abajo) |
| Corregir, cambiar el estado y seguir un caso con versión e historial (D47) | `casos` | `casos/seguimiento.py` | F | movida |
| Formularios por enfermedad con versiones (D48) | `casos` | `casos/formularios.py` | F | movida |
| Casos con datos incompletos y su aviso (D49) | `casos` | `casos/rutas.py` (`faltantes`) | F | movida |
| Lotes de la app: idempotencia, candado y resultado por caso | `sincronizacion` | `sincronizacion/rutas.py` | F | movida |
| Dispositivos de las apps: registrar, revocar; un caso de uno ajeno o revocado no entra | `dispositivos` | `dispositivos/almacen.py` (ya no está en `backend_web`) | F | movida; `casos` guarda la lectura (abajo) |
| Lotes de vacuna y sus dosis | `vacunas` | `vacunas/lotes.py` (ya no está en `backend_web`) | F | movida |
| Campañas de salud (D49) | `vacunas` | `vacunas/campanas.py` | F | movida |
| Tarjetas del panorama y resumen de situación | `indicadores` | `indicadores/consultas.py` | F | copia (abajo) |
| Numerador, denominador y periodo de cada indicador; mortalidad, letalidad y casos graves | `indicadores` | `indicadores/definidos.py` | F | movida |
| Series de Monitoreo (diaria, edad, sexo, totales) | `series` | `series/consultas.py` | F | copia (abajo) |
| Series con rango libre, por semana o mes, grupos y Highcharts | `series` | `series/agregadas.py` | F | movida |
| Tabla por zona, mapa, su serie y la tendencia de un municipio | `zonas` | `zonas/consultas.py` | F | copia (abajo) |
| Mapa de calor, jurisdicciones sanitarias, geometría y ubicar un punto | `zonas` | `zonas/calor.py`, `jurisdicciones.py` y `geometria.py` | F | movida |
| Filtros y clave de ámbito de las consultas analíticas (`filtros_ambito`, `clave_ambito`) | `series`, `zonas` | `epidemia_comun/ambito.py` solo lee y valida los parámetros (técnico); los catálogos, con el `consultas.py` de cada uno | F | movida |
| Avisos: crear, a un rol, leer, marcar como leídos y preferencias (D49) | `notificaciones` | `notificaciones/almacen.py` (ya no está en `backend_web`) | F | movida |
| Estado de los servicios, capacidad, colas y alertas técnicas | `estado-servicios` | `estado_servicios/` | F | movida |

## Compartidas o con copia

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Armar la entrada del motor desde una versión (`entrada_de_version`) | `simulador` (la usa `pareto` para el costo-impacto) | `procesamiento/entrada_motor.py` (se importa, D37) | E | movida a `procesamiento`; no es de ningún servicio |
| El estado del lote sigue al de su corrida | la base | el trigger `tg_simulation_runs_sincroniza_lote` (065); antes, `_sincroniza_lote` copiado en `simulador` y `corridas` | E | movida a la base (2026-11-23): corre en la transacción de quien cambia la corrida |
| `get_run` y `get_motor_run` (corrida con su versión, escenario y región; su motor) | `corridas` | `corridas/datos.py`; `get_run` en `resultados/datos.py`, `simulador/datos.py` y `pareto/datos.py`, y `get_motor_run` en `simulador/datos.py` | E | lectura copiada |
| `get_resultado_run` (el resumen de una corrida) | `resultados` | `resultados/datos.py`; en `pareto/datos.py` | E | lectura copiada |
| `region_de_version` (para el alcance) | `corridas` | `corridas/datos.py`; en `pareto/datos.py` | E | lectura copiada |
| `version_para_motor` (las filas de una versión que entran al motor) | `simulador` | `simulador/datos.py`; en `pareto/datos.py`, y sus consultas en `validacion/huella.py` para la huella con la que se firma una versión (D55) | E, D | lectura copiada; la de `validacion` la vigila `test_la_huella_es_la_misma_que_calcula_el_simulador` |
| `escenario_detalle` (un escenario, una versión y sus intervenciones) | `escenarios` | `escenarios/datos.py`; en `validacion/datos.py` | D | lectura copiada |
| `tipos` (los tipos de intervención activos con su `param_schema`) | `tipos-intervencion` | `tipos_intervencion/datos.py`; en `intervenciones/datos.py` | D | lectura copiada |
| Leer un número del texto de un formulario (`conversion.entero`, `numero_de_esquema`) | todos (técnico) | `epidemia_comun/conversion.py`, copia de `backend_web/conversion.py`; otra en `casos/conversion.py` | E | se queda en `epidemia_comun`; `test_copias_del_monolito.py` exige que sean iguales |
| Monolito `backend_web` (`queries.py`, `simulaciones.py`) | los de arriba | `backend_web/` | C | se retira cuando la web consuma los servicios (D36, E9) |
| Consultas del tablero, de Monitoreo y del mapa; validación y catálogos de la captura | `indicadores`, `series`, `zonas` y `casos` | sus `consultas.py`, `casos/captura.py` y `casos/conversion.py`; copia en `backend_web/queries.py` y `backend_web/conversion.py`, que la web todavía lee | F (la web, C) | copia: la del monolito se va cuando la web consuma el servicio (D36); hasta entonces `test_copias_del_monolito.py` exige que sean iguales |
| `estado_para_captura` (si un dispositivo puede capturar) | `dispositivos` | `dispositivos/almacen.py`; lectura de solo consulta en `casos/captura.py` | F | copia (la misma prueba) |
| `get_enfermedad` y `get_region_municipio` (que existan la enfermedad y el municipio de un filtro) | `enfermedades` y `regiones` | lecturas de solo consulta en `series/consultas.py` y `zonas/consultas.py` | F | copia (la misma prueba) |

## Bloque D: archivos, series observadas, escenarios y catálogos

Ninguno importa `backend_web` (2026-11-23, `test_datos_sin_backend_web.py`). Los que no usan el
motor parten de `epidemia/base-vigilancia`; `enfermedades`, `parametros` y `validacion`, de
`epidemia/base-simulacion`. Las funciones originales siguen en `backend_web/queries.py`, sin uso
fuera de sus pruebas, hasta que se retire el monolito.

| Regla de negocio | Servicio dueño | Dónde vive | Bloque | Estado |
|---|---|---|---|---|
| Validar un archivo por su contenido, su tamaño y su huella; guardarlo en el bucket (D30, D35) | `evidencias` | `evidencias/datos.py` y `evidencias/reportes.py` | D | movida (D2) |
| Revisar una serie observada: solo agregados, periodos seguidos, metadatos de fuente, licencia y corte; versionarla por clave (D53) | `importacion` | `importacion/lectura.py` y `importacion/datos.py` | D | nació ahí (D6) |
| Enviar a revisión, aprobar con firma, rechazar y devolver una versión; la bandeja (D55) | `aprobacion` | `aprobacion/datos.py` (`envia_a_revision`, `resuelve_revision` y `get_pendientes_revision` siguen en `backend_web`, ya sin uso fuera de sus pruebas, hasta que se retire el monolito) | D | movida (D7) |
| La huella de la entrada del motor de una versión (la firma, D55) | `validacion` | `validacion/huella.py`, con `procesamiento.contrato.huella` | D | nació ahí (D7) |
| Revisar un escenario o una versión nueva contra el motor (`valida_escenario`, `valida_version`, `revisa_version`) | `validacion` | `validacion/reglas.py`; `escenarios` y `escenarios-xml` le piden el dictamen por HTTP | D | movida (E8, 2026-11-23) |
| Alta, versión siguiente y duplicado de un escenario; la lista | `escenarios` | `escenarios/datos.py` | D | movida (E8, 2026-11-23) |
| Validar, agregar, quitar y mover una intervención; validar su costo (`valida_intervencion`, `valida_costo_intervencion`) | `intervenciones` | `intervenciones/reglas.py` y `datos.py`; `validacion` le pide `POST /interventions/validate` | D | movida (E8, 2026-11-23) |
| Lista de enfermedades con su actividad y su estado de parámetros; reglas del alta | `enfermedades` | `enfermedades/datos.py` y `reglas.py` | D | movida (E8, 2026-11-23) |
| Catálogo de los municipios de NL con la fuente de su población | `regiones` | `regiones/datos.py` | D | movida (E8, 2026-11-23) |
| Proyectos de investigación, archivar un escenario y los responsables de cada versión (D54) | `escenarios` | `escenarios/datos.py` | D | nació ahí (D7) |
| Rangos de los parámetros epidemiológicos (`parametros_epidemiologicos`), su intervalo y sus versiones (D58) | `parametros` | `parametros/reglas.py` y `parametros/datos.py` (ya no en `epidemia_comun/validaciones.py`); los límites, de `procesamiento.entrada_motor` | D | movida (D7) |
| Ajustes de los parámetros de la enfermedad en una versión de escenario, y los parámetros efectivos (D59) | `parametros` | `parametros/rutas.py` (las reglas, las de `parametros/reglas.py`); `procesamiento.entrada_motor.parametros_efectivos` los combina; `aprobacion` y el monolito congelan «catálogo con ajustes» al enviar | D | nació ahí (A4) |
| Definiciones de caso versionadas y clasificación de las enfermedades (D58) | `enfermedades` | `enfermedades/datos.py` | D | nació ahí (D7) |
| Jerarquía, jurisdicciones sanitarias y búsqueda territorial (D58) | `regiones` | `regiones/datos.py`; `zonas` sigue leyendo las jurisdicciones de `datos/geo/` para agrupar casos | D | nació ahí (D7) |
| Corregir la población y las bandas de un municipio, con sus versiones y periodos (D58) | `poblacion` | `poblacion/datos.py` (`actualiza_poblacion_municipio` y `actualiza_grupos_edad_municipio` siguen en `backend_web`, ya sin uso fuera de sus pruebas) | D | movida (D7) |
| Catálogo de tipos de intervención y sus supuestos de efectividad (D58) | `tipos-intervencion` | `tipos_intervencion/datos.py` | D | movida (D7) |

## Contratos de dominio

Cada respuesta se arma con los campos que dice el contrato (`docs/contratos/<servicio>/`), no con
la fila de la base ni con un objeto interno. Cuando una consulta trae más columnas de las que se
publican (por ejemplo `region_population` en `get_run`), la ruta las recorta con
`epidemia_comun.contratos.proyectar(fila, CAMPOS)`; `corridas` lo hace así y una prueba compara
las claves con el ejemplo del contrato. Las demás respuestas de E se arman con diccionarios
explícitos.
