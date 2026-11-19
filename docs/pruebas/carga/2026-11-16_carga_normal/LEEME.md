# Carga normal (2026-11-16)

- Rama `feat/4-seguridad-y-fallos`, sobre el commit `c7ebeb7` más los cambios sin confirmar de límites de consumo.
- Entorno: Docker Desktop en Mac (arm64, 7.7 GiB), 28 contenedores del compose sin el perfil `gpu`, un solo proceso por servicio. Locust corre en la misma máquina.
- Comando: `RESULTADOS=<dir> locust -f pruebas_carga/locustfile.py UsoNormal --headless -u 20 -r 5 -t 2m --csv <dir>/locust --csv-full-history --html <dir>/reporte.html`
- Host: servicios directos en `localhost:52xx` (no hay pasarela ni nginx). 20 usuarios de Locust repartidos entre las 4 cuentas de demostración (5 por cuenta), espera de 0.5 a 2 s.
- Mezcla: casos (lista y detalle), municipios, escenarios y versiones, corridas, indicadores del tablero y una corrida nueva cada 2 minutos por usuario (cuentas ANALISTA y ADMINISTRADOR).
- Límites vigentes: los de `limites.py` sin variables `LIMITE_*` (normal 120/60, permisivo 600/60 en `casos` y `sincronizacion`, estricto 10/60 en escrituras de `corridas`, login 10/60 por IP).

## Resultados

| Endpoint | Peticiones | req/s | p50 ms | p95 ms | p99 ms | Fallos | 429 |
|---|---|---|---|---|---|---|---|
| GET /cases | 533 | 4.5 | 11 | 21 | 28 | 0 | 0 |
| GET /cases/{id} | 149 | 1.2 | 11 | 18 | 34 | 0 | 0 |
| GET /regions | 282 | 2.4 | 26 | 42 | 46 | 0 | 0 |
| GET /regions/{id} | 116 | 1.0 | 9 | 16 | 17 | 0 | 0 |
| GET /scenarios | 215 | 1.8 | 23 | 35 | 36 | 0 | 0 |
| GET /scenarios/{id}/versions | 153 | 1.3 | 35 | 54 | 56 | 0 | 0 |
| GET /runs | 209 | 1.7 | 13 | 22 | 25 | 0 | 0 |
| GET /dashboard/indicators | 170 | 1.4 | 3 | 6 | 24 | 0 | 0 |
| POST /runs | 19 | 0.2 | 19 | 31 | 31 | 0 | 0 |
| POST /auth/login (con captcha) | 4 | 0.0 | 220 | 220 | 220 | 0 | 0 |
| **Total** | **1854** | **15.5** | **15** | **40** | **53** | **0 (0 %)** | **0** |

El login tarda unos 200 ms por el hash de la contraseña. El script lo hace una vez por cuenta y reutiliza el token, para no chocar con el límite de login por IP.

## Interpretación

- Con el uso esperado, ningún usuario llega a un límite: cero 429 y cero errores. El endpoint más lento es `/scenarios/{id}/versions` (p95 54 ms).
- Lo más caliente fue `postgres` (alrededor de 17 % de CPU); los servicios, menos de 8 %.
- Limitación: los 20 usuarios comparten 4 cuentas, así que cada cuenta recibe 5 veces el tráfico de una persona. Es un escenario más duro para los límites por usuario que el real.

## Recomendación (no se cambió código)

Los perfiles `normal` y `permisivo` dejan margen amplio: el pico por cuenta y ruta fue de 1 a 2 req/s, contra 2 req/s (120/60) o 10 req/s (600/60). No hay razón para subirlos.
