# Carga por perfiles en la nube, con 4 vCPU (2026-11-21)

Segunda medición, para comparar con [`2026-11-21_nube_perfiles`](../2026-11-21_nube_perfiles/LEEME.md)
después de cambiar la máquina de e2-highmem-2 (2 vCPU) a **e2-standard-4 (4 vCPU, 15 GB)**. Mismo
código (`87bdb8a` y la plantilla de nginx de `9a49ac5`), mismos perfiles y escalones (20 usuarios
cada 60 s hasta 200; 120 s de recuperación con 20).

**No es una comparación exacta:** esta corrida se lanzó sin abrir la ventana.
- Los límites de D31 estaban vigentes: 107 respuestas 429, 61 de ellas al lanzar corridas (perfil
  estricto, 10 por minuto por cuenta). Hubo menos corridas, así que el simulador pesó menos que en
  la primera.
- Lo que escribió la prueba (4 546 casos, 163 corridas, fotos y series) quedó en la base; se
  restauró después con el respaldo de la primera ventana, tomado a las 18:14 con las contraseñas
  ya cambiadas (`ventana_nube.sh cierra`).

## Resultado

| Usuarios | Peticiones/s | p50 | p95 | Errores | Con 2 vCPU: p95 y errores |
|---|---|---|---|---|---|
| 20 | 4.2 | 0.39 s | 4.4 s | 0 % | 7.8 s, 0 % |
| 40 | 5.8 | 0.43 s | 13 s | 1.0 % | 30 s, 6.8 % |
| 100 | 10.7 | 0.41 s | 30 s | 7.7 % | 30 s, 23.6 % |
| 200 | 20.2 | 0.51 s | 30 s | 19.1 % | 30 s, 31.2 % |

Mediana por ruta con 20 usuarios, antes y después:

| Ruta | 2 vCPU | 4 vCPU |
|---|---|---|
| `web: GET /mapa` | 11.0 s | 3.0 s |
| `web: GET /api/mapa` | 8.0 s | 4.4 s |
| `sincronizacion`, lote de 5 casos | 5.3 s | 1.3 s |
| `web: GET /escenarios` | 3.2 s | 0.25 s |
| `web: GET /` (tablero) | 2.1 s | 0.54 s |
| `zonas`, `/zones/map` | 2.8 s | 0.20 s |

- Por perfil: el panel, el escritorio y las corridas automáticas, sin errores. Los 795 errores son
  504 de la móvil (`sincronizacion`, 463) y de la web (tablero, mapa y las demás páginas, 332).
- Metas: **cumplen** RNF-A06 (51 personas en la web sin errores) y RNF-A14 (lanzar una corrida,
  p95 0.88 s). **No cumplen** RNF-A01 (p95 0.66 s contra 0.5 s), A05 (5.6 casos/s), A07 (tablero
  p95 36 s) y A08 (lote de 100 contra el límite de 30 s).
- La saturación sigue alrededor de 40 usuarios, ahora no por falta de CPU sino por dos rutas:
  `sincronizacion` (una llamada a `casos` por caso) y las consultas del tablero y del mapa de la
  web, que se vuelven más lentas conforme la prueba agrega miles de casos.

## Qué sigue

**La causa principal no eran las consultas sino las conexiones:** `backend_web.db` y
`epidemia_comun.bd` abrían una conexión a PostgreSQL por consulta (47 ms cada una, contra 0.06 ms
de una consulta con la conexión abierta), y el mapa hace 53. Con las conexiones reutilizadas
(`epidemia_comun/conexiones.py`), en la base de pruebas: la tendencia de los 51 municipios pasa de
1 975 ms a 18 ms y las tres consultas del tablero de 218 ms a 18 ms.

1. Desplegarlo en la máquina (junto con las migraciones 050 a 055 del bloque E) y repetir con la
   ventana. Hecho: [`2026-11-21_nube_perfiles_conexiones`](../2026-11-21_nube_perfiles_conexiones/LEEME.md).
2. Si `sincronizacion` sigue lenta con las conexiones reutilizadas, mandar el lote completo a
   `casos` en una sola llamada en lugar de una por caso.
