# Calibración de `seir-ref` contra la serie de D50 (2026-11-23)

La primera calibración con el método de D50 (`abc-rechazo`, `calibracion-0.1`) sobre
`COVID19_NL_2020_SINTOMAS` v1: los casos confirmados de COVID-19 en Nuevo León por semana de inicio
de síntomas, del 2020-03-01 al 2020-07-26 (22 semanas, 22 259 casos; ficha §18). Es la evidencia
de E7 y de la §19 de [`ficha_simulador.md`](../../../arquitectura/ficha_simulador.md).

- `entrada.json`: la serie, lo fijo (los parámetros de COVID-19 del catálogo, tal como están en
  la base, y la población de Nuevo León por edad del Censo 2020) y la configuración por omisión.
- `resultado.json`: la salida completa de `procesamiento.calibracion.calibrar`, la misma que guarda
  `calibracion-trabajador` en `calibrations.result`.

## Configuración

5 000 combinaciones de (r0, ρ, φ) por hipercubo latino (semilla 1), cada una con las semillas 1 a 3:
15 000 corridas de `seir-ref-0.1`. Se aceptan las 50 de menor pérdida (1 %). Tardó 208 s en la
máquina de desarrollo. Las primeras 15 semanas calibran (2020-03-01 a 2020-06-07) y las últimas 7
validan (2020-06-14 a 2020-07-26), sin entrar a la pérdida.

## Resultado

| Parámetro | Mediana | p5–p95 de las aceptadas | Rango muestreado |
|---|---|---|---|
| r0 | 2.59 | 2.29–3.05 | 1.0–5.0 |
| ρ (fracción reportada) | 0.30 | 0.02–0.66 | 0.01–1.0 |
| φ (reducción de la Jornada) | 0.37 | 0.12–0.63 | 0–1 |

| Ventana | Semanas | RMSE (casos) | R² | Cobertura p5–p95 |
|---|---|---|---|---|
| Calibración | 15 | 136 | 0.89 | 60 % |
| Validación | 7 | 3 041 | −25.9 | 71 % |

- **r0 y φ se confunden** (correlación de 0.96 entre las aceptadas), como anticipó D50: un r0 más
  alto con más reducción de contactos da la misma curva. Por eso la banda usa las combinaciones
  aceptadas y no los márgenes. ρ casi no se identifica (p5–p95 de 0.02 a 0.66): con
  `infectados_iniciales = c₀/ρ`, la serie fija sobre todo el crecimiento, no el nivel.
- **El r0 calibrado** (2.59) cae dentro del IC 2.39–3.44 de Billah et al. 2020 que trae el catálogo,
  y es nominal: el efectivo de `seir-ref` es ~6 % mayor con D = 9 (§11).
- **La validación no llega a la tolerancia.** La ficha fija, con D50, una cobertura de al menos 80 %
  en las semanas de validación; dio 71 %. La mediana sigue creciendo después del pico observado
  (3 295 casos la semana del 2020-07-05): el modelo no reproduce el descenso, porque φ es constante
  y la Jornada no termina. Con D50, el modelo podría declararse **calibrado** (sus corridas con esa
  configuración serían `prediccion`), pero **no validado**.
- `estado_validacion.json` no cambia: declararlo calibrado es un PR revisado (D39, D50) y lo decide
  el equipo con esta evidencia.

## Cómo repetirla

Por el servicio, con el compose arriba y una cuenta de EPIDEMIOLOGO, ANALISTA o ADMINISTRADOR:
`POST /api/v1/calibrations` con `{"dataset_id": <id de COVID19_NL_2020_SINTOMAS v1>}` en
`calibracion` (5246), y al terminar `GET /api/v1/calibrations/{id}/fit`.

Sin la base, desde la raíz, con la misma entrada (sale idéntico bit a bit con la misma versión de
NumPy):

```bash
python -c "import json; from procesamiento.calibracion import calibrar; \
d = 'docs/pruebas/calibracion/2026-11-23/'; e = json.load(open(d + 'entrada.json')); \
r = json.loads(json.dumps(calibrar(e['observado'], e['base'], e['configuracion']))); \
print(r == json.load(open(d + 'resultado.json')))"
```
