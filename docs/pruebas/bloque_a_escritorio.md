# Evidencia y defensa del bloque A

La primera entrega se hizo en el PR #173. La aplicación usa PySide6 y consulta los
microservicios por XML, con GeoJSON para la capa de límites del mapa. Las pruebas locales
usan ejemplos de `docs/contratos` y las capturas comparativas usan datos ilustrativos.

## Reproducir la verificación

    python -m pytest -q frontend_desktop
    python -m pytest -q procesamiento/tests

| Evidencia | Resultado observado | Dónde verificar |
| --- | --- | --- |
| Suite de escritorio del PR #173 | 246 pruebas aprobadas | `frontend_desktop/tests` |
| Suite del motor | 123 pruebas aprobadas, 10 omitidas y 119 subpruebas aprobadas | `procesamiento/tests` |
| Diferencias y exportaciones | Referencia seleccionable, tasas en puntos porcentuales, relativa sin valor frente a cero. Alineación por día y exclusión de semillas incompletas | `test_bloque_a.py` |
| Trazabilidad y PDF | Se consultan versiones del motor por réplica. Se omiten gráficas con metadatos incompletos. Qt abre los PDF y encuentra las diferencias, el modelo, la serie y la metodología | `test_bloque_a.py`, `test_ficha_corrida.py` y `test_regresion_reportes_encolado.py` |
| Editor, validación y parámetros | El XML da unidades, rango, fuente y estado. La selección más reciente prevalece aunque otra respuesta llegue después. La versión se puede consultar aun cuando falla la validación | `test_bloque_a.py` y `test_humo.py` |
| Datos municipales | El ejemplo XML llena los puntos, la tabla de incidencia y la serie registrada por municipio | `test_bloque_a.py` |
| Encolado y navegación | El POST se envía tras confirmar. Conserva versión de escenario, semilla y motor. Cancelar las corridas en espera se limita al motor seleccionado | `test_ficha_corrida.py`, `test_bloque_a.py` y `test_regresion_reportes_encolado.py` |

Las verificaciones de escritorio usan transporte simulado con respuestas XML del contrato.
Se conserva la evidencia previa de errores, permisos y sesión. El recorrido contra el dominio
HTTPS y la recuperación del trabajador requieren un entorno de integración.

## Recorrido para mostrar

1. **Escenarios.** Abre una versión. Muestra población, horizonte, estado, autor y revisor.
   Abre **Consultar parámetros de la enfermedad** y señala qué devuelve el catálogo sobre
   unidades, límites y supuestos. Enseña la intervención, su duración y el costo unitario.
2. **Simulaciones.** Elige una corrida completada. Abre su ficha y muestra versión del motor,
   semilla, huella y parámetros guardados. Abre la versión del escenario desde ahí. Si hay un
   equivalente, abre su ficha y compara el motor, la versión y el resumen.
3. **Comparación.** Selecciona dos versiones y filtra por el mismo motor. Elige una curva,
   explica su banda p5–p95 y abre la réplica de origen. Cambia la referencia en **Diferencias**.
   En **Supuestos de costos**, distingue pesos de personas-día y explica los puntos dominados.
4. **Exportación.** Abre el PDF comparativo y el de una réplica. Muestra la procedencia de la
   gráfica, la versión, la metodología, las limitaciones y los archivos CSV de indicadores,
   curvas y diferencias.
5. **Indicadores municipales.** Cambia el periodo y abre la serie de un municipio. Los puntos
   representan coordenadas del servicio y el color indica su nivel de incidencia. Son datos
   registrados por vigilancia, separados de las curvas de simulación.

Las pantallas y sus controles están en el [manual de usuario](../manuales/manual_usuario_escritorio.md).

## Respuestas breves para la defensa

- **¿Por qué comparten semillas?** Para incluir un conjunto común de réplicas en las medianas.
  Si falta el resultado de una semilla, se retira de todos los escenarios. Las series se
  alinean por el día que informa el servicio.
- **¿Qué significa una diferencia?** Es la mediana del escenario menos la de la referencia.
  El porcentaje relativo requiere una referencia distinta de cero. Si cambian el motor, la
  versión o el horizonte, la lectura es descriptiva.
- **¿Qué demuestra la huella?** Que las corridas recibieron la misma entrada canónica del
  escenario. Para hablar de reproducibilidad también se revisan el motor, la versión y el
  resultado. Reencolar usa la configuración que el servidor tiene disponible en ese momento.
- **¿Por qué se omite una gráfica?** Para mantener identificados su motor, versión y periodo.
  Los indicadores numéricos siguen disponibles en la tabla.
- **¿Qué representa Pareto?** Alternativas para las que ninguna otra tiene a la vez costos e
  impacto iguales o menores y mejora al menos uno de esos objetivos. Personas-día mide el
  costo operativo del modelo y los importes en pesos se reportan aparte.

## Decisiones y dependencias

| Punto | Decisión o entrega que falta |
| --- | --- |
| A1 y configuraciones por versión | A define los cambios de interfaz y, con D, el alcance de los parámetros que se guardan por versión (el bloque 0 lo delegó el 2026-11-22). D define el contrato. |
| A2, almacenamiento y nube | E publica los motores habilitados. D y F entregan la ruta de reportes, el bucket y las URLs firmadas. F habilita HTTPS. |
| Gestión de datos y proyectos | A y D acuerdan el modelo del proyecto, el identificador y las reglas de calidad de los conjuntos (el bloque 0 lo delegó el 2026-11-22). D expone la carga, consulta y versionado. |
| Calibración, sensibilidad y recuperación | El escritorio consume D46. El método de calibración y los criterios de validación con datos observados están en D50; E expone sus rutas en el servicio `calibracion`. E participa en la demostración de recuperación del trabajador. |
| Repetición histórica | D y E exponen el identificador y la versión del conjunto, los parámetros históricos y el contrato de reejecución. |

El [checklist](../parciales/parcial-3/checklist.md#a-app-de-escritorio--frontend_desktop)
distingue lo terminado en la rama, lo parcial y lo bloqueado.

## Integración sobre feat/tercer-parcial · 22 de noviembre

| Verificación | Resultado |
| --- | --- |
| Escritorio y TLS | PySide6 mostró el captcha XML de `https://epidemos.app/estado-servicios` con verificación del certificado activa. El directorio anunció 29 servicios con HTTPS en el dominio y la salud reportó 29 sanos, 0 degradados y 0 caídos. |
| Rutas protegidas en nube | Las rutas de geometría y de historial respondieron 401 `TOKEN_AUSENTE` sin sesión. Queda por probar el recorrido con cuenta de demostración y permisos de región. |
| Plano, historial y validación | Regresión en `test_mapa_auditoria.py`: 51 polígonos de INEGI, interior de anillos, selección y serie, ETag y renovación del token, historial paginado con 403, estado de calibración y sensibilidad para versión aprobada. |
| Suite local de escritorio | 315 pruebas aprobadas en la rama de integración. Se ejecutó completa porque cambiaron el cliente HTTP y el lector XML compartidos. |

## MFA, reporte al bucket y datos observados · 23 de noviembre

| Verificación | Resultado |
| --- | --- |
| Segundo paso del login (D40, D41) | `test_mfa_reportes_datos.py`: el perfil crítico recibe el reto sin tokens; `verify` abre la sesión y revisa el rol; `enroll` regresa el secreto y `confirm` los códigos de respaldo; un código incorrecto es un error que se entiende; el diálogo regresa a la contraseña si el reto vence; la bitácora no guarda el token de MFA, el código ni los respaldos; el identificador del equipo va solo con `EPIDEMIA_DISPOSITIVO=1` y es estable. |
| Reporte al bucket (RF-F17) | El PDF va tal cual con `Content-Type: application/pdf`, `X-Content-SHA256` y sus corridas ordenadas; no se manda lo que el servidor rechazaría (no PDF, sin corridas, más de 100); la URL firmada se abre en el navegador y otra comparación apaga el botón. |
| Gestión de datos (D6, D53) | Verificar calidad e importar mandan el archivo con su tipo y solo los metadatos del contrato; se muestran todas las fallas y si el archivo ya estaba; la lista trae las versiones y los puntos validan con `serie_observada.xsd`. |
| Lector XML | Una etiqueta plural con valor (`<puntos tipo="numero">4</puntos>` del resumen de un conjunto) es escalar, igual que `epidemia_comun.formatos.de_xml`. |
| Suite local de escritorio | 360 pruebas aprobadas (`QT_QPA_PLATFORM=offscreen python -m pytest frontend_desktop`). |

Pendiente para la prueba con servicios levantados: subir un reporte al emulador del bucket y abrir
su URL, e importar `docs/contratos/importacion/ejemplos/entrada_serie.csv` con un analista. Con
`MFA_PERFILES=ADMINISTRADOR` en `auth`, entrar con `admin` y enrolar con un código de alta.

Para el ensayo, abre el escritorio con `EPIDEMIA_DIRECTORIO=https://epidemos.app/estado-servicios`.
Con una cuenta de demostración, elige un escenario de Nuevo León con eventos, abre **Indicadores
municipales** y **Historial de auditoría**. Comprueba con un analista que el historial de una
región permitida abre y que una región fuera de alcance se rechaza. Repite con administrador
para verificar el acceso autorizado. Los cambios de la aplicación no requieren migraciones.
