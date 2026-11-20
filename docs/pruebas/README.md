# Pruebas de carga y de fallos

Resultados medidos el 2026-11-16 sobre el compose de `infra/`, con un proceso de Locust en la misma máquina. Cada carpeta trae su `LEEME.md` (comando, cifras, interpretación), los CSV de Locust, `cronologia.csv`, la salida de consola y `reporte.html`.

## Carga

| Escenario | Qué mide |
|---|---|
| [carga_normal](carga/2026-11-16_carga_normal/LEEME.md) | Mezcla de uso normal con pocos usuarios: p50, p95, p99 y errores por endpoint |
| [estres](carga/2026-11-16_estres/LEEME.md) | Rampa a 100 usuarios; busca el punto de saturación |
| [limites_autenticados](carga/2026-11-16_limites_autenticados/LEEME.md) | Los límites de consumo por usuario: 429 con `Retry-After` |
| [limites_login](carga/2026-11-16_limites_login/LEEME.md) | El límite de login por IP |

## Cómo repetirlas

1. Levanta el compose (`docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait`; ver `docs/INSTALACION.md`).
2. Con el entorno de Python activo, desde la raíz: `RESULTADOS=<carpeta> locust -f pruebas_carga/locustfile.py <Clase> --headless -u <usuarios> -r <rampa> -t <duracion> --csv <carpeta>/locust --csv-full-history --html <carpeta>/reporte.html`. La clase y los valores exactos de cada escenario están en su `LEEME.md`.
3. Las cuentas son las de demostración de `docs/INSTALACION.md`; se cambian con `PRUEBAS_CUENTAS="usuario:contraseña,..."`.
4. Para otras cifras de límite, edita `infra/limites.env` y recrea los contenedores.

El script está en [`pruebas_carga/locustfile.py`](../../pruebas_carga/locustfile.py).

## Suite consolidada

[suite/2026-11-19](suite/2026-11-19/LEEME.md): todas las pruebas en una sola ejecución, sobre una base creada desde cero: 2281 pasan, 2 fallan (ya existían; se explican ahí) y 182 se saltan.

## Validación científica

[validacion/2026-11-19](validacion/2026-11-19/LEEME.md): resultados esperados (tamaño final de un SEIR, letalidad, casos límite), sensibilidad y reproducibilidad de los motores, con el comando que repite cada tabla.

[Bloque A de escritorio](bloque_a_escritorio.md) reúne pruebas de regresión, pasos de demostración y límites de la verificación.

## Volumen de datos

[volumen/2026-11-18](volumen/2026-11-18/LEEME.md): 10,000 corridas de 180 días en `series_corridas` (D29), con la inserción, las consultas con y sin índice, con y sin la caché de Redis, y el uso de CPU, memoria y disco de MongoDB. Se repite con `python datos/scripts/volumen_mongo.py` (ver su LEEME).

## Fallos

La demostración se ejecuta con `python infra/demo_fallos.py` (ver `arquitectura_v3.md` §9). Resultados del 2026-11-16: [fallos/2026-11-16](fallos/2026-11-16/LEEME.md) (servicio caído, Redis y la web, MongoDB y bucket de la demostración, PostgreSQL, tiempo excedido y cierre de sesión), con la salida de consola, las respuestas de cada caso y cómo repetirla.
