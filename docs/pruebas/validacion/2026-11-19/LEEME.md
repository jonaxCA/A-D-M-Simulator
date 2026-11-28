# Validación científica de los motores · 2026-11-19

Evidencia de las §13 a §15 de la [ficha del simulador](../../../arquitectura/ficha_simulador.md) [Retro: «Hace falta validación científica»]. Cada archivo es la salida tal cual del comando, medida sobre el commit `e539481` de `feat/bloque-0`, con Python 3.14.4 y NumPy 2.5.5 en WSL 2 (Linux).

| Archivo | Comando | Qué muestra |
|---|---|---|
| [`esperados.md`](esperados.md) | `python -m procesamiento.mediciones esperados` | `seir-ref` da el tamaño final de un SEIR (z = 1 − e^(−R0·z)) con el R0 efectivo, la letalidad y la hospitalización que recibe, y los casos límite |
| [`sensibilidad.md`](sensibilidad.md) | `python -m procesamiento.mediciones sensibilidad` | Un parámetro a la vez a 0.8 y 1.2 veces: cada uno mueve sus métricas en la dirección esperada |
| [`reproducibilidad.md`](reproducibilidad.md) | `python -m procesamiento.mediciones reproducibilidad` | La misma semilla y versión dan la misma salida bit a bit en `seir-ref` y `abm-ref`; otra semilla da otra. `abm-gpu` no corre en esta máquina |

Lo esencial de las tres lo revisa `procesamiento/tests/test_validacion_cientifica.py`, que corre con `python -m pytest procesamiento/tests`.

## Cómo leerlo

- **Verificado, no validado.** Esto prueba que los modelos son matemáticamente consistentes y reproducibles, no que reproduzcan un brote real: no hay datos observados ni calibración. Sus corridas son exploratorias (D39).
- **R0 efectivo.** El paso de un día alarga el periodo infeccioso medio: el R0 que corre es ~10 % mayor que el capturado (ficha, §11). Corregirlo es una decisión del equipo, pendiente.

## Cómo repetirlo

Desde la raíz, con el entorno de `procesamiento/requerimientos.txt`, corre los tres comandos. Los números cambian solo si cambian el código, la versión de NumPy o los escenarios de `procesamiento/mediciones.py`. Las huellas de reproducibilidad son de la salida completa, así que dependen también de NumPy.
