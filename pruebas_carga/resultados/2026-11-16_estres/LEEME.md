# Estrés: rampa a 100 usuarios (2026-11-16)

- Rama `feat/4-seguridad-y-fallos`, commit `c7ebeb7` más los cambios sin confirmar de límites.
- Comando: `RESULTADOS=<dir> locust -f pruebas_carga/locustfile.py Estres --headless -u 100 -r 3 -t 150s --csv <dir>/locust --csv-full-history --html <dir>/reporte.html`
- 100 usuarios (llegan en unos 33 s), espera de 50 a 300 ms, la misma mezcla que la carga normal, sobre las 4 cuentas de demostración. Un proceso por servicio, en la misma máquina que Locust.
- Límites vigentes: los de `limites.py` sin variables.

## Resultados

| Endpoint | Aceptadas | req/s | p50 ms | p95 ms | p99 ms | 429 |
|---|---|---|---|---|---|---|
| GET /regions (público, sin límite) | 11687 | 78.2 | 26 | 98 | 170 | 0 |
| GET /regions/{id} (público) | 3883 | 26.0 | 7 | 68 | 150 | 0 |
| GET /cases | 7200 | 48.2 | 10 | 24 | 44 | 12149 |
| GET /cases/{id} | 5514 | 36.9 | 7 | 17 | 29 | 139 |
| GET /dashboard/indicators | 5991 | 40.1 | 2 | 4 | 8 | 0 |
| GET /scenarios | 1080 | 7.2 | 21 | 62 | 110 | 6823 |
| GET /scenarios/{id}/versions | 1080 | 7.2 | 40 | 97 | 230 | 4851 |
| GET /runs | 1080 | 7.2 | 11 | 24 | 38 | 6723 |
| POST /runs | 38 | 0.3 | 15 | 32 | 43 | 111 |
| **Total (incluye los 429)** | **68359** | **457.5** | **3** | **43** | **110** | **30756** |

- Fallos reales (5xx, tiempos agotados, 429 sin `Retry-After`): 0.
- Un 409 en `POST /runs` (2 veces) es el candado de la versión ocupado; se cuenta aparte.
- CPU más alta (muestreo con `docker stats`): `postgres` entre 113 % y 187 %, `regiones` entre 90 % y 145 %, `casos` hasta 53 %; el resto, menos de 10 %.

## Interpretación

- No se llegó al punto de quiebre: a 457 req/s no hubo un solo error y el p99 total quedó en 110 ms. Lo que más se estira es `regiones` (p99 170 ms) porque ese catálogo es público y no pasa por el límite, así que consume PostgreSQL sin tope.
- Los límites protegen: la mayor parte del exceso (30 756 peticiones) se rechazó en 2 ms sin tocar la base. Las rutas con límite normal quedaron limitadas a 120 por minuto por cuenta, y fueron las lentas, aun así sin errores.
- Con tantos usuarios sobre 4 cuentas no se midió el techo de cada servicio; para eso habría que subir `LIMITE_NORMAL` y `LIMITE_PERMISIVO` en el compose, que hoy no los pasa al contenedor.

## Recomendación (no se cambió código)

- Considerar un límite por IP (perfil `publico` con un valor alto, por ejemplo 300/60) para `GET /regions`, que es la única ruta abierta y la que más CPU gasta en PostgreSQL.
- Para estimar capacidad real, repetir con `LIMITE_*` altos y con más de 100 usuarios; hasta entonces la cifra defendible es "100 usuarios sobre 4 cuentas, 457 req/s, 0 errores".
