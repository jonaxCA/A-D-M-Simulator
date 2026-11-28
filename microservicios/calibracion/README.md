# EPIDEMIA - Servicio calibracion

Calibra `seir-ref` contra una serie semanal observada (D50): ABC por rechazo sobre un hipercubo
latino de tres parámetros. La lógica es una función pura de `procesamiento/calibracion/` (regla 2);
este servicio registra la calibración en `calibrations` (migración 062), la encola y la expone, y
`calibracion-trabajador` la corre. Lo usa el escritorio (A4: calibración y validación).

- Puerto externo: 5246. Puerto interno en Docker: 8000. Perfil `simulacion`. Imagen
  `epidemia/base-simulacion` (con `procesamiento/`, sin `backend_web`).
- Contrato en `docs/contratos/calibracion/openapi.json`; cada respuesta XML valida contra
  `calibracion.xsd`. Ejemplos en `ejemplos/`, sacados de la calibración real de la serie de D50.

## Qué se calibra

| Parámetro | Qué es | Rango (supuesto, regla 8) |
|---|---|---|
| `r0` | R0 nominal de `seir-ref-0.1` | 1.0 a 5.0 |
| `rho` | Fracción de contagios que se reporta; no entra al motor | 0.01 a 1.0 |
| `phi` | Reducción de contactos de la Jornada Nacional de Sana Distancia (`CIERRE_TRABAJO` y `REDUCCION_AFORO`) | 0 a 1 |

Lo demás queda fijo: la enfermedad del catálogo con sus supuestos, la población por edad de la
región (la gente sin edad se prorratea), las capas de contacto del motor, `CIERRE_ESCUELAS` desde el
23-03-2020 e `infectados_iniciales = max(1, round(c₀/ρ))`. El caso simulado de una semana es ρ por los
contagios desplazados 5 días; los infectados iniciales cuentan como inicio de síntomas el día 0.

Cada combinación corre con las semillas 1 a `seeds`, y su distancia es la pérdida media
Σ(log(1+o) − log(1+s))² en las primeras ⅔ de las semanas. Se aceptan las de menor distancia
(`quantile`). La banda p5–p95 de `/fit` sale de las aceptadas por sus semillas. RMSE, R² y
cobertura se calculan aparte en la ventana de calibración y en la de validación, el último ⅓, que
nunca entra a la pérdida. Detalle y resultados: §19 de `docs/arquitectura/ficha_simulador.md`.

## Rutas

| Método | Ruta | Roles | Qué hace |
|--------|------|-------|----------|
| POST | `/api/v1/calibrations` | EPIDEMIOLOGO, ANALISTA y ADMINISTRADOR (`calibrations.run`) | Revisa el conjunto y encola. **202**. Cuerpo: `dataset_id` y, opcionales, `engine` (solo `seir-ref`), `samples` (100 a 10 000; 5 000), `seeds` (1 a 5; 3), `quantile` (0.001 a 0.2; 0.01) y `sampling_seed` (1) |
| GET | `/api/v1/calibrations[?status=…&dataset=…&limit=…]` | ANALISTA, EPIDEMIOLOGO, ADMINISTRADOR, INVESTIGADOR y AUTORIDAD_SANITARIA (`simulations.read`) | Las más recientes, dentro del alcance de la cuenta |
| GET | `/api/v1/calibrations/{id}` | Los mismos | Estado, avance (de Redis mientras corre), intentos, configuración y versiones; completada, también parámetros, pérdida, métricas y ventanas |
| POST | `/api/v1/calibrations/{id}/cancel` | Los que lanzan | `encolado` o `ejecutando` → `cancelado`; **409** si ya terminó |
| GET | `/api/v1/calibrations/{id}/fit` | Los que leen | Por semana: observado, mediana, p5–p95 y ventana; RMSE, R² y cobertura por ventana (RF-F13, RF-F14). **409** si no está completada |
| GET | `/api/v1/calibrations/{id}/scenario` | Los que leen | La configuración calibrada como entrada de una versión: el escenario, las intervenciones de la Jornada y el r0 como ajuste de la versión (D59). El escritorio la crea y pasa por revisión (D4, D5) |
| GET | `/api/v1/calibrations/evaluate?dataset=…&r0=…&rho=…&phi=…` | Los que leen | Síncrona, sin escribir: un juego de parámetros con las semillas 1 a 5 |
| GET | `/api/v1/calibrations/state[?engine=…&disease=…&region=…]` | Los que leen | El estado de cada versión de motor; lo mismo que `/pareto/calibration` (D46) |

CAPTURISTA recibe 403 en todas. Lanzar y cancelar quedan en la bitácora (`RUN` y `CANCEL`, entidad
`calibration`) y tienen el límite estricto de las corridas (D31). **Nadie declara un modelo
calibrado desde una ruta:** subirlo en `procesamiento/estado_validacion.json` es un PR revisado, con
la evidencia en la ficha (D39, D50).

## El trabajador

`calibracion-trabajador` es la misma imagen con `CALIBRACION_TRABAJADOR=1`, sin puerto publicado.
Toma de `queue:calibraciones`, marca la calibración `ejecutando` (solo si estaba `encolado`, y suma
un intento), publica el avance en `calibration:<id>:progress` cada 200 corridas y guarda el
resultado entero al terminar, solo si sigue `ejecutando`. Cada 200 corridas revisa en la base si la
cancelaron.

La base manda sobre Redis (D19). Al arrancar, regresa a `encolado` las que quedaron en `ejecutando`
con menos de 3 intentos y la misma versión del motor, cierra las demás como `fallido` y mete a la
cola las `encolado` que falten (D38). Con la misma configuración el resultado es el mismo bit a bit,
así que repetirla no duplica nada.

Una calibración por defecto (5 000 muestras con 3 semillas) son 15 000 corridas de `seir-ref`: unos
3.5 minutos en una máquina de desarrollo.

## Pruebas

- `procesamiento/tests/test_calibracion.py`: el algoritmo con una serie sintética de parámetros
  conocidos, el hipercubo, la pérdida, las métricas, el desfase, la reproducibilidad y la cancelación.
- `tests/test_calibracion.py`: las rutas con la base simulada, los roles, el alcance y el XSD.
- `tests/test_trabajador.py`: correr, cancelar a la mitad, otra versión del motor y la recuperación.
- `tests/test_calibracion_bd.py`: contra la base de pruebas (`DATABASE_URL_PRUEBAS`).
- `microservicios/pruebas_integracion/contenedores/test_compose_calibracion.py`: contra los
  contenedores, con el trabajador detenido a la mitad.

```bash
python -m pytest procesamiento/tests/test_calibracion.py microservicios/calibracion
```
