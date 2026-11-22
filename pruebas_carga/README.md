# Pruebas de carga (Locust)

| Archivo | Qué es |
|---|---|
| `perfiles.py` | Los cinco perfiles de uso real de RNF-A16 (F4). Es el que se usa ahora. |
| `escalones.py` | La forma de carga: sube por escalones y luego baja, para la saturación y la recuperación. |
| `analiza.py` | El resumen: por escalón, por perfil, los 10 endpoints más lentos, saturación, recuperación y las metas de RNF-A. Solo usa la biblioteca estándar. |
| `corre_nube.py` | Corre todo contra la máquina de GCP pidiendo las contraseñas sin mostrarlas. |
| `ventana_nube.sh` | En la máquina: respalda y sube los límites antes; restaura todo después. |
| `locustfile.py` | La mezcla anterior (carga normal, estrés y límites, 2026-11-16). Se conserva para repetir esas mediciones. |

Locust va en su propio entorno: `python -m venv C:\Temp\locust` y
`C:\Temp\locust\Scripts\python.exe -m pip install locust` (probado con la 2.47.0).

## Los perfiles

| Perfil | Peso | Quién | Qué hace |
|---|---|---|---|
| `ConsultaWeb` | 4 | Personas en la web | Tablero público; con sesión: tablero, mapa, escenarios, simulaciones, monitoreo y comparación. Inicia sesión por el formulario de la web, con su captcha. |
| `CapturaMovil` | 3 | La app móvil (CAPTURISTA) | Lotes de 5 casos por `sincronizacion`, de vez en cuando uno de 100 (RNF-A08), fotos a `evidencias`, avisos y su perfil. |
| `EscritorioReportes` | 2 | La app de escritorio | Resultados y curvas de corridas, comparaciones, Pareto, mapa de zonas, situación y exportación XML. |
| `PanelAdministracion` | 1 | Administradores | Directorio y salud de los servicios, usuarios, resumen y avisos. |
| `CorridasAutomaticas` | 1 | Procesos automáticos | Lanzan una corrida `seir-ref`, esperan a que termine y leen sus resultados (RNF-A14). |

Cada petición se nombra `perfil: MÉTODO servicio ruta`. Un 429 con `Retry-After` es el límite
de D31 haciendo su trabajo: cuenta aparte (`[429] ...`), no como error, y el usuario espera lo que
dice `Retry-After`, como las apps.

## En local

Contra el compose de pruebas (base `simulador_epidemico_pruebas`, nunca la de la demostración):

```bash
python infra/pruebas_integracion.py --conservar -- --co -q      # lo levanta y lo deja arriba
RESULTADOS=<dir> USUARIOS_PASO=20 SEGUNDOS_PASO=40 USUARIOS_MAX=60 \
  C:/Temp/locust/Scripts/python.exe -m locust -f pruebas_carga/perfiles.py,pruebas_carga/escalones.py \
  --headless --csv <dir>/locust --csv-full-history --html <dir>/reporte.html
python pruebas_carga/analiza.py <dir>
```

Sin `URL_SERVICIOS`, los perfiles van a cada servicio por su puerto y a la web en
`http://localhost:5000`. Con los límites de siempre, la única cuenta CAPTURISTA llega a su
límite de 600 casos por minuto y la mayoría de los lotes salen 429: es lo esperado.

## En la nube

Las pruebas escriben casos, fotos y corridas en la base de la máquina, y para medir la
saturación hay que quitar un rato los límites. Por eso van en una ventana que deja todo como
estaba:

1. **Antes de abrir la ventana**, las contraseñas de las cuentas de demostración ya cambiadas
   en la máquina (la web, como administrador: Usuarios → Editar). Las de `docs/INSTALACION.md`
   son públicas, y la ventana restaura la base tal como estaba al abrirla.
2. **Abrir**, en la máquina: `sudo bash pruebas_carga/ventana_nube.sh abre`. Respalda
   PostgreSQL, MongoDB y las fotos en `/var/backups/epidemia-carga` y sube los límites.
3. **Correr**, en la PC (unos 12 minutos con los valores por omisión: escalones de 20 usuarios
   cada 60 s hasta 200, y 2 minutos de recuperación):

   ```powershell
   C:\Temp\locust\Scripts\python.exe pruebas_carga\corre_nube.py --url https://epidemos.app
   ```

   Pide la contraseña de cada cuenta sin mostrarla y deja todo en
   `docs/pruebas/carga/<fecha>_nube_perfiles/`, con `resumen.md`. Mientras corre, nadie
   use esas cuentas en otro lado: cada una admite 3 sesiones (D41) y la cuarta cierra la más
   antigua, así que Locust volvería a iniciar sesión a media prueba.
4. **Cerrar**, en la máquina: `sudo bash pruebas_carga/ventana_nube.sh cierra`. Detiene los
   servicios, vacía las colas de corridas, restaura las tres cosas y los límites, levanta todo y
   compara los conteos de casos, corridas y usuarios con los de antes.

Ensayado completo el 2026-11-21 contra el compose de pruebas: 9 149 casos y 61 corridas antes;
12 724 y 109 después de la carga; 9 149 y 61 al cerrar, con los 36 contenedores sanos.

Locust corre en una sola PC, así que la cifra incluye la red de la PC a us-central1. Desde una
sola IP, sin la ventana, los límites por IP de D31 serían el techo, no la máquina.

## Cómo lee los resultados `analiza.py`

- Los primeros 10 s de cada escalón no cuentan (los usuarios van llegando).
- **Saturación:** el primer escalón con errores ≥ 1 %, o con p95 de más de 2 veces el del primer
  escalón y de más de 500 ms, o en que las peticiones por segundo crecen menos del 10 % con más
  usuarios. El escalón anterior es la capacidad.
- **Recuperación:** desde que baja la carga, el tiempo hasta la primera ventana de 10 s con p95
  de no más de 1.2 veces el del primer escalón y sin errores.
- **Metas:** RNF-A01 (p95 de las consultas en el último escalón sano), A05 (casos guardados por
  segundo), A06 (personas en la web sin errores), A07 (tablero), A08 (lote de 100) y A14 (lanzar
  una corrida).
