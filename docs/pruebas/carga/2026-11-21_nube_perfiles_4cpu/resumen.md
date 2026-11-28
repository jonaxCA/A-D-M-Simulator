# Resumen de la prueba de carga por perfiles

Escalones de 20 usuarios cada 60 s hasta 200; luego 20 usuarios durante 120 s. Los primeros 10 s de cada escalón no cuentan.

## Por escalón

| Usuarios | Peticiones/s | Casos/s | Media ms | p50 | p95 | p99 | Errores | 429 | Saturación |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 4.2 | 5.6 | 1017 | 389 | 4448 | 6543 | 0 (0.00 %) | 0 |  |
| 40 | 5.8 | 3.2 | 3182 | 429 | 13022 | 30083 | 3 (1.03 %) | 0 | errores ≥ 1 % |
| 60 | 8.1 | 3.7 | 3793 | 415 | 16842 | 20758 | 1 (0.25 %) | 2 | p95 > 2× el inicial y > 500 ms |
| 80 | 10.2 | 0.7 | 4023 | 417 | 22682 | 30094 | 23 (4.51 %) | 2 | errores ≥ 1 % |
| 100 | 10.7 | 0.0 | 5189 | 411 | 30078 | 30086 | 41 (7.68 %) | 3 | errores ≥ 1 % |
| 120 | 11.9 | 0.0 | 5556 | 396 | 30083 | 33857 | 45 (7.58 %) | 7 | errores ≥ 1 % |
| 140 | 13.8 | 0.0 | 5413 | 375 | 30081 | 36292 | 49 (7.10 %) | 8 | errores ≥ 1 % |
| 160 | 15.6 | 0.0 | 6313 | 425 | 30085 | 43255 | 134 (17.18 %) | 4 | errores ≥ 1 % |
| 180 | 17.6 | 0.0 | 6410 | 461 | 30084 | 30245 | 166 (18.82 %) | 5 | errores ≥ 1 % |
| 200 | 20.2 | 0.0 | 6563 | 507 | 30083 | 30243 | 193 (19.07 %) | 21 | errores ≥ 1 % |

**Saturación:** a los 40 usuarios (errores ≥ 1 %). El último escalón sano fue el de 20 usuarios, con 4.2 peticiones por segundo y p95 de 4448 ms.

**Recuperación:** en 120 s después de bajar a 20 usuarios no volvió al p95 inicial sin errores.

## Por perfil (toda la prueba)

| Perfil | Peticiones | Errores | 429 | Media ms | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| corridas | 1553 | 0 | 61 | 544 | 500 | 985 | 1294 |
| escritorio | 2791 | 0 | 5 | 1002 | 295 | 6581 | 13211 |
| movil | 912 | 463 | 0 | 16828 | 30074 | 30104 | 30250 |
| panel | 1102 | 0 | 0 | 179 | 101 | 422 | 638 |
| web | 1136 | 332 | 0 | 17129 | 16005 | 30247 | 42736 |

## Los 10 endpoints más lentos (p95, toda la prueba)

| Endpoint | Peticiones | Fallos | Media ms | p95 | p99 |
|---|---|---|---|---|---|
| web: GET / (tablero) | 302 | 93 | 20880 | 39000 | 53000 |
| movil: POST sincronizacion /sync/cases (100 casos) | 54 | 53 | 29985 | 30000 | 30000 |
| movil: POST sincronizacion /sync/cases (5 casos) | 545 | 410 | 25004 | 30000 | 30000 |
| web: GET /api/mapa | 155 | 49 | 19169 | 30000 | 30000 |
| web: GET /comparacion | 81 | 18 | 12705 | 30000 | 30000 |
| web: GET /dashboard | 255 | 81 | 15596 | 30000 | 30000 |
| web: GET /escenarios | 68 | 14 | 14158 | 30000 | 30000 |
| web: GET /mapa | 91 | 30 | 18354 | 30000 | 30000 |
| web: GET /monitoreo | 98 | 27 | 15165 | 30000 | 30000 |
| web: GET /simulaciones | 75 | 20 | 13894 | 30000 | 30000 |

## Metas de rendimiento (RNF-A)

| Requisito | Meta | Medido | Resultado |
|---|---|---|---|
| RNF-A01 consultas de los servicios | p95 ≤ 500 ms | p95 658 ms en el último escalón sano (90 peticiones GET) | no cumple |
| RNF-A05 casos por `sincronizacion` | 100 casos/s | hasta 5.6 casos/s en un escalón | no cumple |
| RNF-A06 personas en la web a la vez | 50 sin errores | hasta 51 en la web sin errores | cumple |
| RNF-A07 el tablero carga | ≤ 3 s | p95 35915 ms (558 cargas) | no cumple |
| RNF-A08 lote de 100 casos | ≤ 30 s | p95 30247 ms (54 lotes) | no cumple |
| RNF-A14 lanzar una corrida | ≤ 1 s | p95 884 ms (163 lanzamientos) | cumple |
