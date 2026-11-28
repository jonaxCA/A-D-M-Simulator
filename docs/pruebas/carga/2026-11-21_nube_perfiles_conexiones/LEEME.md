# Carga por perfiles en la nube: 4 vCPU y conexiones reutilizadas (2026-11-21)

Tercera medición del día, para comparar con [la de 2 vCPU](../2026-11-21_nube_perfiles/LEEME.md) y
[la de 4 vCPU](../2026-11-21_nube_perfiles_4cpu/LEEME.md).

- Máquina e2-standard-4 (4 vCPU, 15 GB) con `6c751c5`: el bloque E integrado (migraciones 050 a
  055), la ruta de nginx corregida y **las conexiones a PostgreSQL reutilizadas**
  (`epidemia_comun/conexiones.py`).
- Con la ventana (`ventana_nube.sh`): respaldo con la base ya migrada (3 824 casos, 0 corridas, 4
  usuarios) y límites de D31 subidos. Al cerrar había 33 164 casos y 305 corridas; restaurada a
  3 824, 0 y 4.
- Mismos cinco perfiles y escalones (20 usuarios cada 60 s hasta 200; 120 s de recuperación).

## Resultado

**La capacidad pasa de unos 40 a unos 80 o 100 usuarios.** En total 12 883 peticiones y 60 fallos
(0.5 %), contra 5 733 y 1 236 (21.6 %) en la primera medición.

| Usuarios | Peticiones/s | Casos/s | p50 | p95 | Errores |
|---|---|---|---|---|---|
| 20 | 5.3 | 14.8 | 181 ms | 448 ms | 0 % |
| 40 | 11.0 | 29.7 | 176 ms | 440 ms | 0 % |
| 80 | 21.3 | 61.7 | 203 ms | 604 ms | 0 % |
| 100 | 26.0 | 71.4 | 240 ms | 1.2 s | 0 % |
| 140 | 28.8 | 63.9 | 356 ms | 5.4 s | 0 % |
| 180 | 17.5 | 6.0 | 412 ms | 30 s | 3.2 % |

- Saturación (criterio de `analiza.py`): a los 100 usuarios, por el p95. Sin errores hasta 140
  usuarios; desde 160 aparecen los 504 de nginx.
- Recuperación: al bajar a 20 usuarios, el p95 volvió al inicial (448 ms) en 40 s, sin errores.
- Errores: 48 son 504 de `sincronizacion` con 160 usuarios o más, y 12 son 503 de `comparacion`,
  que esperó más de 5 s a `resultados`: fallan limpios, sin 500.

Las tres mediciones, mediana con 20 usuarios:

| Ruta | 2 vCPU | 4 vCPU | 4 vCPU y conexiones |
|---|---|---|---|
| `web: GET /mapa` | 11.0 s | 3.0 s | 0.25 s |
| `web: GET /api/mapa` | 8.0 s | 4.4 s | 0.25 s |
| `sincronizacion`, lote de 5 casos | 5.3 s | 1.3 s | 0.20 s |
| `web: GET /` (tablero) | 2.1 s | 0.54 s | 0.22 s |
| `web: GET /dashboard` | 2.1 s | 0.37 s | 0.13 s |

## Metas (RNF-A)

| Requisito | Meta | Medido | Resultado |
|---|---|---|---|
| RNF-A01 consultas de los servicios | p95 ≤ 500 ms | 634 ms con 80 usuarios | no cumple, por poco |
| RNF-A05 casos por `sincronizacion` | 100 casos/s | 72.8 casos/s con 120 usuarios, todos con una sola cuenta CAPTURISTA | no cumple |
| RNF-A06 personas en la web a la vez | 50 sin errores | 73 sin errores | **cumple** |
| RNF-A07 el tablero carga | ≤ 3 s | p95 < 0.7 s hasta 100 usuarios; 2.1 s con 120 | **cumple** hasta 120 usuarios |
| RNF-A08 lote de 100 casos | ≤ 30 s | p95 < 14 s hasta 160 usuarios | **cumple** hasta 160 usuarios |
| RNF-A14 lanzar una corrida | ≤ 1 s | p95 422 ms | **cumple** |

`analiza.py` mide A07 y A08 sobre toda la prueba, incluidos los escalones ya saturados; por eso su
tabla dice «no cumple». La tabla de arriba usa el p95 por escalón.

## Qué sigue

- `sincronizacion` es ahora la ruta más lenta con carga: con 140 usuarios, un lote de 5 casos tarda
  4.5 s de mediana porque llama a `casos` una vez por caso. Mandar el lote en una sola llamada
  acercaría RNF-A05 a los 100 casos/s.
- El tablero (`/`) es la siguiente: 2.5 s de mediana con 140 usuarios.
