# Límites con sesión: lectura de casos, lectura de corridas y lanzamiento de corridas (2026-11-16)

- Rama `feat/4-seguridad-y-fallos`, commit `c7ebeb7` más los cambios sin confirmar de límites.
- Comando: `RESULTADOS=<dir> locust -f pruebas_carga/locustfile.py LimiteCasos LimiteCorridas --headless -u 2 -r 2 -t 130s --csv <dir>/locust --csv-full-history --html <dir>/reporte.html`
- Un usuario de Locust por clase, sin espera casi: `LimiteCasos` pide `GET /cases` como `karla.trevino` cada 50 ms (perfil permisivo, 600/60); `LimiteCorridas` lanza una corrida cada 200 ms como `alex.cavazos` (estricto, 10/60) y lista corridas como `diana.flores` (normal, 120/60). Cada cuenta tiene su propio contador, así que los límites por usuario se miden limpios.
- Límites vigentes: los de `limites.py`, sin variables `LIMITE_*`.
- En el script, un 429 con `Retry-After` y código `LIMITE_EXCEDIDO` cuenta como esperado y sale en filas `[429] ...`; sin esos dos datos se cuenta como fallo.

## Resultados

| Endpoint | Aceptadas | 429 | Fallos reales | p95 aceptadas ms | p95 de los 429 ms |
|---|---|---|---|---|---|
| GET /cases (600/60) | 1342 | 692 | 0 | 19 | 6 |
| GET /runs (120/60) | 270 | 173 | 0 | 19 | 6 |
| POST /runs (10/60) | 30 | 137 | 0 | 23 | 6 |

Cronología (`cronologia.csv`), por ventana de 60 s:

- `GET /cases`: 600 aceptadas y luego 429 hasta que se abre la ventana siguiente; a partir de ahí otras 600.
- `GET /runs`: 120 aceptadas por ventana.
- `POST /runs`: 10 aceptadas por ventana (30 en tres ventanas).
- Al abrir la ventana vuelve el 2xx, a los 60 s del primer paso de la ventana anterior.

## Interpretación

- Los umbrales coinciden con los configurados, el 429 sale en unos 4 ms (no cuesta nada rechazar) y las demás rutas de la misma cuenta siguen sirviendo: el contador es por usuario y por ruta.
- Cada ruta tiene su propio cupo: una cuenta puede hacer hasta 600 por minuto en cada ruta de `casos`, no 600 en total.

## Recomendación (no se cambió código)

- `estricto` 10/60 en `POST /runs`: es adecuado para un humano que lanza corridas. Si el escritorio lanza las 30 réplicas de una comparación (D8) con un `POST /runs` cada una, tardaría unos 3 minutos solo por el límite. Conviene decidir si la comparación va por un solo POST o si ese rol tiene un cupo mayor, por ejemplo `LIMITE_ESTRICTO=60/60`.
- Mantener `permisivo` 600/60 para `casos` y `sincronizacion` hasta medir el lote real de la app móvil; la sincronización de un lote de 100 casos pasa por `casos` uno por uno con el token de la persona, y 600/min cubre ese caso.
