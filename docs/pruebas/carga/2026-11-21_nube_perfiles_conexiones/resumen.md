# Resumen de la prueba de carga por perfiles

Escalones de 20 usuarios cada 60 s hasta 200; luego 20 usuarios durante 120 s. Los primeros 10 s de cada escalón no cuentan.

## Por escalón

| Usuarios | Peticiones/s | Casos/s | Media ms | p50 | p95 | p99 | Errores | 429 | Saturación |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 5.3 | 14.8 | 224 | 181 | 448 | 1897 | 0 (0.00 %) | 0 |  |
| 40 | 11.0 | 29.7 | 222 | 176 | 440 | 2031 | 0 (0.00 %) | 0 |  |
| 60 | 16.3 | 44.1 | 236 | 188 | 470 | 2012 | 0 (0.00 %) | 0 |  |
| 80 | 21.3 | 61.7 | 277 | 203 | 604 | 2836 | 0 (0.00 %) | 0 |  |
| 100 | 26.0 | 71.4 | 398 | 240 | 1187 | 4350 | 0 (0.00 %) | 0 | p95 > 2× el inicial y > 500 ms |
| 120 | 28.7 | 72.8 | 712 | 277 | 3202 | 5598 | 0 (0.00 %) | 0 | p95 > 2× el inicial y > 500 ms |
| 140 | 28.8 | 63.9 | 1373 | 356 | 5430 | 7876 | 0 (0.00 %) | 0 | p95 > 2× el inicial y > 500 ms |
| 160 | 23.0 | 32.0 | 2299 | 361 | 8318 | 19437 | 2 (0.17 %) | 0 | p95 > 2× el inicial y > 500 ms |
| 180 | 17.5 | 6.0 | 6737 | 412 | 30077 | 45192 | 28 (3.19 %) | 0 | errores ≥ 1 % |
| 200 | 24.7 | 25.3 | 5319 | 327 | 25699 | 35546 | 16 (1.30 %) | 0 | errores ≥ 1 % |

**Saturación:** a los 100 usuarios (p95 > 2× el inicial y > 500 ms). El último escalón sano fue el de 80 usuarios, con 21.3 peticiones por segundo y p95 de 604 ms.

**Recuperación:** al bajar a 20 usuarios, el p95 volvió a su nivel inicial en 40 s, sin errores.

## Por perfil (toda la prueba)

| Perfil | Peticiones | Errores | 429 | Media ms | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| corridas | 1946 | 0 | 0 | 300 | 230 | 668 | 1792 |
| escritorio | 2889 | 12 | 0 | 867 | 272 | 3417 | 14863 |
| movil | 3560 | 48 | 0 | 2571 | 205 | 17888 | 30080 |
| panel | 1122 | 0 | 0 | 117 | 94 | 238 | 352 |
| web | 3366 | 0 | 0 | 3176 | 411 | 22167 | 38975 |

## Los 10 endpoints más lentos (p95, toda la prueba)

| Endpoint | Peticiones | Fallos | Media ms | p95 | p99 |
|---|---|---|---|---|---|
| web: GET / (tablero) | 913 | 0 | 4357 | 34000 | 45000 |
| movil: POST sincronizacion /sync/cases (100 casos) | 189 | 16 | 8188 | 30000 | 30000 |
| movil: POST sincronizacion /sync/cases (5 casos) | 1939 | 32 | 3834 | 23000 | 30000 |
| web: GET /api/mapa | 516 | 0 | 3195 | 22000 | 26000 |
| web: GET /monitoreo | 235 | 0 | 3252 | 22000 | 26000 |
| web: GET /escenarios | 237 | 0 | 2561 | 21000 | 23000 |
| web: GET /mapa | 246 | 0 | 2932 | 21000 | 24000 |
| web: GET /dashboard | 703 | 0 | 2620 | 20000 | 25000 |
| web: GET /comparacion | 263 | 0 | 2206 | 17000 | 24000 |
| escritorio: GET comparacion /comparisons | 425 | 12 | 3649 | 16000 | 18000 |

## Metas de rendimiento (RNF-A)

| Requisito | Meta | Medido | Resultado |
|---|---|---|---|
| RNF-A01 consultas de los servicios | p95 ≤ 500 ms | p95 634 ms en el último escalón sano (410 peticiones GET) | no cumple |
| RNF-A05 casos por `sincronizacion` | 100 casos/s | hasta 72.8 casos/s en un escalón | no cumple |
| RNF-A06 personas en la web a la vez | 50 sin errores | hasta 73 en la web sin errores | cumple |
| RNF-A07 el tablero carga | ≤ 3 s | p95 24968 ms (1616 cargas) | no cumple |
| RNF-A08 lote de 100 casos | ≤ 30 s | p95 30084 ms (189 lotes) | no cumple |
| RNF-A14 lanzar una corrida | ≤ 1 s | p95 422 ms (305 lanzamientos) | cumple |
