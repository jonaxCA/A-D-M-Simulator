# Resumen de la prueba de carga por perfiles

Escalones de 20 usuarios cada 60 s hasta 200; luego 20 usuarios durante 120 s. Los primeros 10 s de cada escalón no cuentan.

## Por escalón

| Usuarios | Peticiones/s | Casos/s | Media ms | p50 | p95 | p99 | Errores | 429 | Saturación |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 3.3 | 2.8 | 2300 | 1209 | 7820 | 13571 | 0 (0.00 %) | 0 |  |
| 40 | 4.1 | 0.7 | 5844 | 947 | 30080 | 30182 | 14 (6.83 %) | 0 | errores ≥ 1 % |
| 60 | 5.9 | 0.0 | 5567 | 733 | 30085 | 37642 | 24 (8.08 %) | 0 | errores ≥ 1 % |
| 80 | 6.9 | 0.0 | 8036 | 1004 | 30139 | 30370 | 74 (21.57 %) | 0 | errores ≥ 1 % |
| 100 | 8.1 | 0.0 | 7949 | 1168 | 30092 | 30268 | 95 (23.57 %) | 0 | errores ≥ 1 % |
| 120 | 10.8 | 0.0 | 7063 | 1184 | 30083 | 30258 | 112 (20.70 %) | 0 | errores ≥ 1 % |
| 140 | 11.0 | 0.0 | 9034 | 2159 | 30087 | 30267 | 139 (25.32 %) | 0 | errores ≥ 1 % |
| 160 | 12.8 | 0.0 | 8827 | 1410 | 30085 | 30265 | 165 (25.70 %) | 0 | errores ≥ 1 % |
| 180 | 13.5 | 0.0 | 9209 | 1967 | 30090 | 30253 | 171 (25.26 %) | 0 | errores ≥ 1 % |
| 200 | 12.9 | 0.0 | 11242 | 4944 | 30089 | 30298 | 202 (31.22 %) | 0 | errores ≥ 1 % |

**Saturación:** a los 40 usuarios (errores ≥ 1 %). El último escalón sano fue el de 20 usuarios, con 3.3 peticiones por segundo y p95 de 7820 ms.

**Recuperación:** al bajar a 20 usuarios, el p95 volvió a su nivel inicial en 40 s, sin errores.

## Por perfil (toda la prueba)

| Perfil | Peticiones | Errores | 429 | Media ms | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| corridas | 1195 | 0 | 0 | 2815 | 2407 | 6129 | 7436 |
| escritorio | 1787 | 111 | 0 | 3466 | 384 | 30076 | 30088 |
| movil | 815 | 492 | 0 | 18809 | 30077 | 30130 | 30272 |
| panel | 1060 | 0 | 0 | 383 | 123 | 1182 | 1817 |
| web | 780 | 633 | 0 | 26461 | 30080 | 30263 | 33466 |

## Los 10 endpoints más lentos (p95, toda la prueba)

| Endpoint | Peticiones | Fallos | Media ms | p95 | p99 |
|---|---|---|---|---|---|
| escritorio: GET pareto /pareto | 124 | 106 | 28730 | 30000 | 31000 |
| movil: POST sincronizacion /sync/cases (100 casos) | 45 | 45 | 30099 | 30000 | 30000 |
| movil: POST sincronizacion /sync/cases (5 casos) | 483 | 447 | 28424 | 30000 | 30000 |
| web: GET / (tablero) | 186 | 152 | 27465 | 30000 | 46000 |
| web: GET /api/mapa | 135 | 120 | 28869 | 30000 | 30000 |
| web: GET /comparacion | 50 | 40 | 26385 | 30000 | 30000 |
| web: GET /dashboard | 185 | 143 | 25186 | 30000 | 30000 |
| web: GET /escenarios | 58 | 53 | 28196 | 30000 | 30000 |
| web: GET /mapa | 53 | 47 | 28344 | 30000 | 30000 |
| web: GET /monitoreo | 40 | 31 | 24812 | 30000 | 30000 |

## Metas de rendimiento (RNF-A)

| Requisito | Meta | Medido | Resultado |
|---|---|---|---|
| RNF-A01 consultas de los servicios | p95 ≤ 500 ms | p95 1876 ms en el último escalón sano (77 peticiones GET) | no cumple |
| RNF-A05 casos por `sincronizacion` | 100 casos/s | hasta 2.8 casos/s en un escalón | no cumple |
| RNF-A06 personas en la web a la vez | 50 sin errores | hasta 0 en la web sin errores | no cumple |
| RNF-A07 el tablero carga | ≤ 3 s | p95 30267 ms (371 cargas) | no cumple |
| RNF-A08 lote de 100 casos | ≤ 30 s | p95 30252 ms (45 lotes) | no cumple |
| RNF-A14 lanzar una corrida | ≤ 1 s | p95 6394 ms (78 lanzamientos) | no cumple |
