# D46 - Sensibilidad exploratoria y estado de calibración, en `pareto`

Fecha: 2026-11-20 · Estado: Aceptada (tomada por el orquestador; pendiente de validación del líder) · Reabre RF-F12 y toca RF-E17 · Depende de D24 (reabierta), D37 y D39

## Contexto
La retroalimentación pide análisis de sensibilidad y calibración, y el checklist (E7) pide las rutas para que el escritorio (A4) las use. D24 quedó reabierta: el método de calibración, su función de pérdida, sus datos y dónde corre son del bloque 0 y todavía no existen. La sensibilidad no necesita datos observados: solo el motor de referencia. El checklist no asigna estas rutas a un servicio en particular dentro del bloque E.

## Opciones consideradas
- Opción A: esperar al bloque 0 y no exponer nada.
- Opción B: exponer la sensibilidad (cálculo exploratorio) y el estado de calibración (solo lectura), y dejar la ejecución de una calibración para cuando D24 se cierre.
- Opción C: un servicio nuevo para las dos cosas.

## Decisión
Opción B, dentro de `pareto`. Es el servicio de analítica de E que no pertenece a otro dominio (`resultados`, `comparacion` y `corridas` tienen los suyos) y ya depende de `procesamiento/analitica`. Un servicio nuevo no se justifica con dos rutas de lectura.

**Sensibilidad** (`GET /api/v1/pareto/sensitivity`): análisis de un factor a la vez.
- Recibe una versión de escenario aprobada, un parámetro de la enfermedad (`r0`, `incubacion_dias`, `infeccioso_dias` o `dias_hospitalizacion`), y de 1 a 9 valores absolutos (`values`) o cambios porcentuales (`percent`).
- Corre el motor de referencia (`seir-ref`) en el proceso, con las semillas 1 a 5 por valor, y regresa por cada valor la media, el mínimo y el máximo de la métrica, y su diferencia contra el valor de la versión, que siempre se incluye como base.
- No crea corridas ni escribe datos, así que no pasa por `corridas` ni por la cola, y no registra bitácora. Se descartó lanzar corridas reales: 5 semillas por valor tardan milisegundos y las corridas reales exigirían escenarios y versiones nuevos por cada valor.
- Los valores probados son supuestos del análisis (regla 8): se marcan así y no son datos. La categoría es la de D39, siempre `exploratoria` mientras no haya calibración.
- La lógica es una función pura en `procesamiento/analitica/sensibilidad.py`.

**Calibración** (`GET /api/v1/pareto/calibration`): solo lectura. Regresa, por versión de motor, `estado` (`sin_calibrar`, `calibrado` o `validado`), la categoría de D39 y su evidencia, leídos de `procesamiento/estado_validacion.json`, y `disponible: false`. No hay ruta para ejecutar una calibración: se agrega cuando el bloque 0 decida el método (un POST hoy da 405).

Pueden consultar los tres roles que ya consultan `pareto` (ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR); CAPTURISTA recibe 403.

## Consecuencias
- El escritorio puede mostrar la sensibilidad y el estado de calibración sin esperar al bloque 0. Ningún resultado se presenta como predicción.
- Cuando D24 se cierre, el estado se actualiza en `estado_validacion.json` y se agrega la ruta que ejecuta la calibración, con su bitácora y su cola.
- `pareto` suma dos rutas fuera de su nombre; si el método de calibración exige datos o ejecuciones largas, debe pasar a un servicio propio.
