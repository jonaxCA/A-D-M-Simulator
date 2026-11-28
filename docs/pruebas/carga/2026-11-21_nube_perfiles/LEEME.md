# Carga por perfiles en la nube (2026-11-21)

- Máquina: `instance-20261120-215738`, **e2-highmem-2 (2 vCPU, 16 GB)**, us-central1-c, con el
  código de `87bdb8a` (antes de integrar el bloque E) y la plantilla de nginx de `9a49ac5`.
- Ventana: `pruebas_carga/ventana_nube.sh abre` (respaldo de PostgreSQL, MongoDB y fotos; límites
  de D31 subidos a 1 000 000/60) y `cierra` al terminar. Antes: 3 824 casos, 0 corridas y 4
  usuarios; al cerrar, 5 953 casos y 79 corridas; restaurada: 3 824, 0 y 4.
- Comando, desde la PC del equipo (red de la UDEM): `pruebas_carga/corre_nube.py --url
  https://35-222-19-202.sslip.io`, escalones de 20 usuarios cada 60 s hasta 200 y 120 s de
  recuperación con 20. Los cinco perfiles de `pruebas_carga/perfiles.py`.
- Archivos: `resumen.md` (de `analiza.py`), los CSV de Locust, `reporte.html`, `cronologia.csv` y
  `usuarios.csv`.

## Resultado

**La máquina se satura con unos 40 usuarios.** En total 5 733 peticiones, 1 236 fallos, p50 de
1.3 s, p95 y p99 de 30 s, y un máximo de 16.6 peticiones por segundo con 200 usuarios. Todos los
fallos son 504 de nginx: la petición pasó de los 30 s de `NGINX_TIEMPO_MAXIMO`. No hubo 5xx de
los servicios ni 429 (los límites estaban subidos).

| Usuarios | Peticiones/s | p50 | p95 | Errores |
|---|---|---|---|---|
| 20 | 3.3 | 1.2 s | 7.8 s | 0 % |
| 40 | 4.1 | 0.9 s | 30 s | 6.8 % |
| 100 | 8.1 | 1.2 s | 30 s | 23.6 % |
| 200 | 12.9 | 4.9 s | 30 s | 31.2 % |

- Por perfil: el panel (p95 1.2 s) y las corridas automáticas no tuvieron errores. La web, la
  móvil (`sincronizacion`) y `pareto` del escritorio se llevaron todos los 504.
- Recuperación: al bajar a 20 usuarios, el p95 volvió en 40 s al del primer escalón. Ese nivel
  ya era malo (7.8 s), así que la cifra dice poco.

## Por qué

1. **La máquina se quedó sin CPU.** Al terminar, la carga media era de 15 a 19 en 2 vCPU, y
   PostgreSQL seguía en 87 % con las consultas de peticiones que nginx ya había cortado.
2. **El simulador ocupó un núcleo completo toda la prueba.** Corre una corrida a la vez y le
   llegaban más de las que terminaba: de lanzar a terminar, la mediana pasó de 12 s en los dos
   primeros minutos a 148 s al final (78 lanzadas, 62 terminadas). Con un núcleo para el
   simulador, la web, PostgreSQL y los 29 servicios se repartieron el otro.
3. **Hay rutas lentas aun con poca carga.** Con 20 usuarios, la mediana de `/mapa` fue 11 s, la de
   `/api/mapa` 8 s, un lote de 5 casos 5.3 s (`sincronizacion` llama a `casos` una vez por caso),
   el inicio de sesión de 2 a 6 s y el tablero 2.1 s. En la PC, con el mismo perfil y 20
   usuarios, el p95 era de unos 430 ms.

## Metas (RNF-A)

Ninguna se cumple en esta máquina: A01 (p95 de consultas 1.9 s contra 500 ms), A05 (2.8 casos/s
contra 100), A06 (ninguna persona en la web sin errores contra 50), A07 (tablero p95 30 s contra
3 s), A08 (lote de 100 en 30 s, cortado por nginx) y A14 (lanzar una corrida p95 6.4 s contra
1 s). Las metas no se corrigen con esto: lo medido es una máquina chica con el simulador dentro,
no el techo del diseño.

## Qué sigue

- **Más CPU que memoria.** La máquina usa unos 2.6 GB de 16 en reposo. Una e2-standard-4 (4 vCPU,
  16 GB) duplica la CPU con la misma memoria; se cambia con la máquina detenida y conserva la IP
  fija. Revisar el costo en la calculadora de GCP antes.
- **Ponerle tope de CPU a los simuladores** (`cpus` en el compose), para que las corridas esperen
  en su cola en lugar de quitarle CPU a la web y a los servicios. Lanzar ya no espera la corrida
  (RNF-A14), así que el costo es solo que tardan más.
- **Revisar las consultas de `/mapa`, `/api/mapa` y el tablero** con `EXPLAIN ANALYZE` en la base
  de la máquina, y la de `pareto`.
- **`sincronizacion`:** una sola llamada a `casos` por lote en lugar de una por caso.
- Repetir la medición con la misma ventana después de cada cambio.
