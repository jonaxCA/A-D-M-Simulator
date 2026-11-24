# EPIDEMIA — Sistema Monolítico v0.1

Responsables de programación de este Sprint:

-- Rolando Rivas Dávalos

-- Jonathan Correa Ascencio

-- Carlos Rodrigo Gómez González 

-- Mauricio Gallardo Barbosa

-- Enrique Ortiz Davila

-- Luz Colugna Elizondo

Primera versión funcional del monolito del **Simulador de respuesta a epidemias**,
correspondiente al Primer Avance.

Incluye dashboard público, login con JWT, dashboard autenticado, análisis de
monitoreo, mapa por municipio de Nuevo León, catálogo de enfermedades, captura de
casos, gestión de usuarios y bitácora de auditoría, además del motor de simulación
de referencia (`motor/`), que todavía no está conectado a las pantallas.

Corre como **una sola app Flask monolítica contra PostgreSQL**, sin capa de
microservicios (eso es alcance del segundo parcial). En este proyecto, "demo" se
refiere únicamente a los **datos de demostración** (`demo_datos_nl.sql`), no al sistema.

---

# Guía de instalación

Estas instrucciones funcionan en **Linux, macOS y Windows**. Si es tu primera vez,
sigue los 5 pasos en orden y no te saltes ninguno.

Para los microservicios y Docker, sigue en **Docker: microservicios del grupo 14:00**, más abajo.

## Paso 0 — Qué necesitas instalado

| Requisito | Versión | Cómo verificar |
|---|---|---|
| **PostgreSQL** | 15 o superior | `psql --version` |
| **Python** | 3.12 o superior | `python3 --version` (en Windows: `python --version`) |
| **Conexión a internet** | — | Necesaria al abrir la app: las gráficas usan Highcharts desde su CDN |

> **PostgreSQL 15 es obligatorio**, no es capricho: la migración `006_escenarios.sql`
> usa `UNIQUE NULLS NOT DISTINCT`, que no existe en versiones anteriores.

Si no lo tienes:

- **Windows / macOS**: instalador oficial de <https://www.postgresql.org/download/>
  (en Windows, durante la instalación **anota la contraseña** que le pongas al
  usuario `postgres`; la vas a necesitar en el Paso 1).
- **Debian / Ubuntu**: `sudo apt install postgresql python3-venv`
- **Fedora**: `sudo dnf install postgresql-server python3`

### Abrir la consola de PostgreSQL (`psql`)

Todos los comandos de base de datos de esta guía se corren con `psql`.

- **Windows**: abre **SQL Shell (psql)** desde el menú inicio, o usa
  `"C:\Program Files\PostgreSQL\18\bin\psql.exe"` desde PowerShell (ajusta el
  número a la versión que hayas instalado).
- **Linux / macOS**: `psql` ya está en tu `PATH`.

Conéctate siempre así (te va a pedir la contraseña del usuario `postgres`):

```bash
psql -h localhost -U postgres
```

Si eso te da error de autenticación, revisa **Problemas comunes** al final.

---

## Paso 1 — Crear la base de datos y el usuario de la aplicación

Conéctate con `psql -h localhost -U postgres` y pega esto **tal cual**:

```sql
CREATE DATABASE simulador_epidemico;

CREATE ROLE epidemia_app LOGIN PASSWORD 'epidemia_app_pw';
```

Después **sal** (`\q`). Todavía falta darle permisos al rol, pero eso se hace
hasta el Paso 3, cuando ya existan las tablas.

> Puedes cambiar el nombre de la base y la contraseña si quieres; solo recuerda
> usar los mismos valores en el Paso 4.

---

## Paso 2 — Cargar el esquema y los datos

Desde una terminal, **parado en la raíz del repositorio** (donde está el
`README.md`), corre los tres archivos **en este orden exacto**:

```bash
psql -h localhost -U postgres -d simulador_epidemico -v ON_ERROR_STOP=1 -f datos/postgres/dump_completo.sql
psql -h localhost -U postgres -d simulador_epidemico -v ON_ERROR_STOP=1 -f datos/postgres/semillas/nl_municipios_completos.sql
psql -h localhost -U postgres -d simulador_epidemico -v ON_ERROR_STOP=1 -f datos/postgres/semillas/demo_datos_nl.sql
```

En Windows PowerShell es lo mismo, pero anteponiendo la ruta a `psql.exe` si no
está en el `PATH`. No hace falta configurar la codificación de la consola: los tres
archivos están en UTF-8 y lo declaran en su primera instrucción
(`SET client_encoding = 'UTF8'`). Sin eso, `psql` en Windows los leería como WIN1252
y los municipios con acento quedarían como “AnÃ¡huac”.

**Qué hace cada uno:**

| Archivo | Qué carga |
|---|---|
| `datos/postgres/dump_completo.sql` | El esquema completo: las migraciones numeradas concatenadas |
| `datos/postgres/semillas/nl_municipios_completos.sql` | Completa los 51 municipios y sus bandas censales de edad (0–19, 20–39, 40–59, 60–79, 80+ y edad no especificada) |
| `datos/postgres/semillas/demo_datos_nl.sql` | Datos de demostración (sintéticos): 3,824 casos, escenario, simulaciones y la usuaria de login |

**El orden importa.** Los dos últimos archivos dependen del esquema y del catálogo
de regiones que carga `dump_completo.sql`.

> **¿Ya tenías la base de una versión anterior?** Vuelve a correr
> `datos/postgres/dump_completo.sql` y
> `datos/postgres/semillas/nl_municipios_completos.sql`. Ambos son idempotentes:
> la semilla completa las bandas censales que falten en los 41 municipios
> agregados después de la migración 021, y no pisa bandas que ya existan o hayan
> sido corregidas manualmente.
>
> **Ojo: `simulation_results` se retira.** El dump incluye la migración `041`, que
> borra la tabla `simulation_results` (`DROP TABLE IF EXISTS`). Si esta base tiene
> series de corridas anteriores a D28, volver a correr el dump las pierde. El resumen
> ya quedó en `simulation_runs` gracias a la `038`, y la serie se recupera volviendo a
> lanzar la corrida con la misma semilla (ver la nota de compose más abajo). Ni la app
> ni los servicios la leen.

> **Corrección de bandas por municipio.** En Regiones, `ADMINISTRADOR` puede
> abrir **Corregir bandas de edad**. La suma de las cinco bandas debe conservar
> la población con edad declarada; “edad no especificada” permanece separada y
> no se imputa. La población de 60 años o más se recalcula desde 60–79 + 80+ y
> queda auditada con motivo, usuario, fecha e IP.

> **Migraciones que van fuera del dump.** Una migración que depende de una semilla
> no puede vivir dentro de `dump_completo.sql`, porque el dump corre antes que las
> semillas. Esas se corren aparte, después del paso de semillas, y están listadas en
> `datos/scripts/verifica_migraciones.py`. Ese script verifica que cada archivo de
> `datos/postgres/migraciones/` coincida con su bloque del dump y que las apartadas
> no estén duplicadas dentro de él:
>
> ```bash
> python datos/scripts/verifica_migraciones.py
> ```

`-v ON_ERROR_STOP=1` hace que `psql` se detenga al primer error en vez de seguir
y dejarte la base a medias. Si un comando termina sin mensajes de `ERROR`, salió bien.

---

## Paso 3 — Dar permisos al usuario de la aplicación

Ahora que las tablas ya existen, dale acceso al rol que creaste en el Paso 1:

```bash
psql -h localhost -U postgres -d simulador_epidemico -c "
  GRANT USAGE ON SCHEMA public TO epidemia_app;
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO epidemia_app;
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO epidemia_app;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO epidemia_app;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO epidemia_app;
"
```

La app necesita `INSERT` y `UPDATE` (no solo lectura) porque el login actualiza
`users.last_login_at` y la auditoría escribe en `audit_log`.

> **Por qué las dos líneas de `ALTER DEFAULT PRIVILEGES`.** `ON ALL TABLES` otorga
> permisos sobre las tablas que existen *en ese momento*, no sobre las futuras. Sin
> esto, la primera migración que agregue una tabla deja a la app sin acceso a ella y
> la pantalla correspondiente falla con `permiso denegado`, aunque la migración haya
> corrido sin un solo error. `ALTER DEFAULT PRIVILEGES` aplica a lo que cree de aquí
> en adelante el mismo rol que ejecuta este comando (`postgres`), que es quien corre
> las migraciones.

> **¿Ya tenías la base y una pantalla te da `permiso denegado`?** Vuelve a correr el
> bloque de arriba: el `GRANT ... ON ALL TABLES` alcanza las tablas que se agregaron
> desde entonces, y el `ALTER DEFAULT PRIVILEGES` evita que vuelva a pasar.

---

## Paso 4 — Instalar Python y configurar la conexión

### 4.1 Crear el entorno virtual e instalar dependencias

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r frontend_web/requerimientos.txt   # la app web (arrastra backend_web)
pip install -r procesamiento/requerimientos.txt  # el motor de simulacion
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r frontend_web/requerimientos.txt   # la app web (arrastra backend_web)
pip install -r procesamiento/requerimientos.txt  # el motor de simulacion
```

> Si PowerShell bloquea el script de activación, corre una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Sabrás que el entorno está activo porque el prompt empieza con `(.venv)`.

### 4.2 Crear el archivo `.env`

Copia la plantilla:

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Y edita `.env` para que quede así (ajusta usuario, contraseña, host, puerto y
nombre de base si usaste otros en el Paso 1):

```
DATABASE_URL=postgresql://epidemia_app:epidemia_app_pw@localhost:5432/simulador_epidemico
JWT_SECRET_KEY=<la cadena que te dé el comando de abajo>
```

Genera el secreto con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Las dos variables son **obligatorias**. Si falta alguna, o si se quedó con el valor
de ejemplo de `.env.example`, la app se niega a arrancar y dice cuál es. Antes
había valores por omisión en el código: sin `.env`, la app firmaba los tokens con
un secreto público y se conectaba como el superusuario `postgres` sin avisar.

**No necesitas exportar nada a mano**: `db.py` lee el `.env` automáticamente con
`python-dotenv` al arrancar.

---

## Paso 5 — Arrancar la aplicación

Con el entorno virtual activo y en la raíz del repositorio:

```bash
python -m frontend_web.run
```

Verás algo como `Running on http://127.0.0.1:5000`. Abre en tu navegador:

**<http://localhost:5000/>**

Para detenerla: `Ctrl + C`.

Por omisión arranca **solo en tu máquina y sin depurador**. Para desarrollar,
agrega al `.env` (o define en la terminal) lo que necesites:

| Variable | Efecto |
| --- | --- |
| `FLASK_DEBUG=1` | Depurador y recarga automática al guardar un `.py` |
| `EPIDEMIA_HOST=0.0.0.0` | Visible para tu red local (p. ej. para abrirla desde un celular) |
| `EPIDEMIA_PORT=5001` | Otro puerto |

`FLASK_DEBUG=1` y `EPIDEMIA_HOST=0.0.0.0` juntos se rechazan: el depurador de
Werkzeug ejecuta código Python desde el navegador y no debe quedar abierto a la red.

La web no corre simulaciones (D4): consulta las corridas que lanza la app de escritorio y
ejecuta el simulador. Por eso, al arrancar, ya no toca las corridas encoladas o en ejecución.

### Credenciales

| Usuario | Contraseña | Rol | Qué puede hacer |
|---|---|---|---|
| `alex.cavazos` | `Epidemia2026!` | ANALISTA | Vigilancia, mapa, monitoreo y captura de casos |
| `diana.flores` | `Epidemia2026!` | EPIDEMIOLOGO | Lo mismo por ahora |
| `karla.trevino` | `Epidemia2026!` | CAPTURISTA | La cuenta de la app móvil: registra su teléfono, captura casos, sube sus fotos, escanea lotes de vacuna y sincroniza lotes de casos (servicios `dispositivos`, `casos`, `evidencias`, `vacunas` y `sincronizacion`). En la web, tablero, mapa, monitoreo y captura de casos; sin escenarios ni simulaciones |
| `admin` | `Admin2026!` | ADMINISTRADOR | Además, **Usuarios** y **Auditoría** |

> Los dos primeros son personas distintas a propósito: la migración `013`
> prohíbe que quien crea una versión de escenario sea quien la aprueba, y esa
> regla ya vive en la base de datos. Las pantallas que la usan (crear escenario,
> enviar a revisión, aprobar) son parte del siguiente avance, así que hoy ambos
> usuarios ven lo mismo en la interfaz.

> Si tu base se cargó antes de que existiera `karla.trevino`, créala como `admin` en
> **Usuarios** con el rol CAPTURISTA. No vuelvas a cargar `demo_datos_nl.sql` sobre una base
> en uso: empieza vaciando casos, escenarios y corridas.

> Las cuatro contraseñas las pone `datos/postgres/semillas/demo_datos_nl.sql`, así que con los
> tres comandos del Paso 2 ya puedes entrar con cualquiera. No hay archivos
> extra que correr.
>
> **Por qué importa el detalle:** `010_datos_iniciales.sql` crea al usuario
> `admin` con el marcador `REEMPLAZAR_ANTES_DE_DESPLEGAR` como `password_hash`,
> inválido a propósito. Quien instale **solo el esquema**, sin los datos de
> demostración, se queda con esa cuenta inutilizable — que es justo lo que
> quieres en un servidor real. La contraseña que funciona vive únicamente en los
> datos de demostración.

### Gestión de usuarios (solo ADMINISTRADOR)

Entrando como `admin` aparece **Usuarios** en el menú, con alta, edición, baja
lógica y eliminación. Con `diana.flores` ese menú **no se ve**, y entrar por URL
directa (o mandar un POST a mano) tampoco funciona: rebota al dashboard y deja el
intento en la bitácora como `PERMISSION_DENIED`.

Cada operación queda registrada en Auditoría con el estado antes y después
(nunca se guarda la contraseña).

**Sobre el botón Eliminar.** Funciona gracias a la migración
`011_fix_audit_log_delete.sql`, incluida en `dump_completo.sql`. `003_sistema.sql`
declaraba `audit_log.user_id ... ON DELETE SET NULL`, pero la bitácora tiene un
trigger que rechaza todo `UPDATE`, así que borrar a cualquier usuario con un solo
evento fallaba con `restrict_violation`. La `011` permite **únicamente** que la
llave foránea ponga `user_id` en NULL sin tocar ningún otro campo: la bitácora
sigue sin admitir borrados ni cambios de contenido.

Aun así no siempre procede: si el usuario tiene casos capturados,
escenarios o lotes de simulación, la base lo impide con `ON DELETE RESTRICT` y
la pantalla te dice exactamente qué tiene y te manda a **Desactivar**.

**Desactivar sigue siendo la vía recomendada.** Al eliminar de verdad, los
eventos que esa persona generó permanecen en la bitácora pero **pierden la
atribución**: quedan con `user_id` nulo y se muestran como "Anónimo". Ya no vas
a poder saber quién los hizo. Lo único que se conserva es el registro `DELETE`,
que guarda en `data_before` quién era la cuenta eliminada. La baja lógica evita
esa pérdida por completo.

---

## ¿Quedó bien instalado?

Recorre esta lista. Si algo no coincide, ve a **Problemas comunes**.

1. `http://localhost:5000/` abre el **dashboard público** sin pedir login.
2. Entras con `diana.flores` / `Epidemia2026!` y llegas al **Panorama Epidemiológico**.
3. El dashboard muestra números **distintos de cero** (~684 casos activos) y una
   gráfica de curva epidémica dibujada.
4. **Mapa epidemiológico** pinta los municipios de Nuevo León en colores.
5. **Auditoría** ya tiene al menos un renglón `LOGIN` — lo generó tu propio acceso.
6. Entrando como `admin` aparece **Usuarios** en el menú, con los botones de
   Editar / Desactivar / Eliminar.

Verificación rápida por consola (deberías ver `casos=3824`):

```bash
psql -h localhost -U postgres -d simulador_epidemico -Atc "SELECT 'casos='||count(*) FROM cases"
```

---

## Base para las pruebas

Las pruebas **no** corren contra `simulador_epidemico`, sino contra su propia base,
`simulador_epidemico_pruebas`. `audit_log` es de solo inserción: lo que una prueba
escribe ahí no se puede borrar, y algunas pantallas (Regiones, por ejemplo) leen de
ahí si una cifra fue corregida a mano. Corriendo contra la base de la demostración,
la suite le dejaría marcas visibles.

Créala una vez, y otra vez cuando cambien el dump o las semillas. Es lo mismo que
los pasos 2 y 3, sobre la base de pruebas, y pide la contraseña de `postgres`:

```bash
python datos/scripts/prepara_base_pruebas.py
```

- Usa el mismo usuario y contraseña de tu `DATABASE_URL`; solo cambia el nombre de
  la base (le agrega `_pruebas`). No hay que escribir otra credencial.
- Para usar otra base, define `DATABASE_URL_PRUEBAS` en el `.env`. Si apunta a la
  misma base que `DATABASE_URL`, las pruebas se niegan a correr.
- Mientras la base de pruebas no exista, las pruebas que la necesitan se saltan o
  fallan con un mensaje que lo dice.

---

## Docker: microservicios del grupo 14:00

Estos son los pasos exactos con que se levantaron los 12 servicios para las evidencias
del segundo parcial (la carpeta `evidencias/` se retiró el 2026-10-30; sigue en el historial de git). PostgreSQL y Redis corren en contenedores; los servicios, con
`waitress` en tu máquina, cada uno con su rol de la migración 026. Necesitas Docker Desktop
(o Docker Engine en Linux), el cliente `psql` y el entorno de Python del paso 4 con las
dependencias de abajo.

```bash
pip install -r backend_web/requerimientos.txt -r procesamiento/requerimientos.txt \
            -r microservicios/comun/requirements.txt waitress==3.0.2
```

### 0. PostgreSQL en un contenedor

Una base nueva en `127.0.0.1:5433`, para no tocar la de los pasos 1 a 3. Son los mismos
pasos 1, 2 y 3 de arriba, contra el contenedor:

```bash
docker run -d --name epidemia-pg -e POSTGRES_PASSWORD="<contraseña de postgres>" \
  -p 127.0.0.1:5433:5432 postgres:16-alpine
export PGPASSWORD="<contraseña de postgres>"
P="psql -h 127.0.0.1 -p 5433 -U postgres -v ON_ERROR_STOP=1"

$P -c "CREATE DATABASE simulador_epidemico;"
$P -c "CREATE ROLE epidemia_app LOGIN PASSWORD '<contraseña de epidemia_app>';"
$P -d simulador_epidemico -f datos/postgres/dump_completo.sql          # trae de la 001 a la 041
$P -d simulador_epidemico -f datos/postgres/semillas/nl_municipios_completos.sql
$P -d simulador_epidemico -f datos/postgres/semillas/demo_datos_nl.sql
$P -d simulador_epidemico -c "GRANT USAGE ON SCHEMA public TO epidemia_app;
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO epidemia_app;
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO epidemia_app;"

# Contraseña de cada rol de la 026 (svc_auth, svc_sesiones, … svc_zonas)
for s in auth sesiones usuarios roles enfermedades parametros regiones poblacion \
         tipos_intervencion indicadores series zonas; do
  $P -d simulador_epidemico -c "ALTER ROLE svc_$s PASSWORD '<contraseña del rol>';"
done
```

Los avisos `NOTICE: ... does not exist, skipping` son normales: el dump es idempotente.

### 1. Redis

```bash
cp infra/.env.example infra/.env        # escribe REDIS_PASSWORD (ver el comentario del archivo)
docker compose -f infra/docker-compose.yml up -d redis
docker compose -f infra/docker-compose.yml ps            # redis debe salir "healthy"
```

Queda en `127.0.0.1:6380` de tu máquina, con contraseña y AOF.

### 2. Los 12 servicios

Desde la raíz del repositorio, cada uno en su puerto del catálogo y con su rol:

```bash
REDIS_PASSWORD=$(grep '^REDIS_PASSWORD=' infra/.env | cut -d= -f2-)
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
export REDIS_URL="redis://:$REDIS_PASSWORD@127.0.0.1:6380/0"
export JWT_SECRET_KEY="<una cadena larga, la misma en todos los servicios>"

for par in auth:5201 sesiones:5202 usuarios:5203 roles:5204 enfermedades:5211 \
           parametros:5212 regiones:5213 poblacion:5214 tipos_intervencion:5215 \
           indicadores:5251 series:5252 zonas:5253; do
  s=${par%%:*}; p=${par##*:}
  DATABASE_URL="postgresql://svc_$s:<contraseña del rol>@127.0.0.1:5433/simulador_epidemico" \
    waitress-serve --listen=127.0.0.1:$p microservicios.$s.app:app > logs_$s.txt 2>&1 &
done
```

- `JWT_SECRET_KEY` es obligatoria y no puede ser el valor de ejemplo: sin ella el servicio
  no arranca. Debe ser la misma en todos, porque `auth` firma y los demás verifican.
- Para apagarlos: `kill %1 %2 …` (o `pkill -f waitress-serve`), y
  `docker rm -f epidemia-pg` y `docker compose -f infra/docker-compose.yml stop redis`.

### 3. Alternativa: los servicios en contenedores

Todos los `Dockerfile` parten de la imagen `epidemia/base` (`infra/docker/base.Dockerfile`):
Python 3.12, las dependencias y el código que comparten (`backend_web/`, `procesamiento/` y
`microservicios/comun/`), con usuario sin privilegios. Cada servicio solo agrega su carpeta y
su contrato, arranca `waitress` en el puerto 8000 y tiene `HEALTHCHECK` a `/health`. El compose
construye la base antes que los servicios, y cada dominio es un perfil. Desde cero:

```bash
python infra/genera_env.py                    # crea infra/.env y llena las contraseñas vacías
docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait
docker compose -f infra/docker-compose.yml ps # todo debe salir "healthy"
```

Escribe el comando en una sola línea, así funciona igual en bash, PowerShell y cmd.

`genera_env.py` no imprime ninguna contraseña ni cambia las que ya tienen valor. Para levantar
solo un dominio, deja únicamente su perfil (`--profile catalogos`); sin `--profile` solo
arrancan PostgreSQL, Redis y MongoDB.

**No uses `--profile '*'` para levantar.** Activa también el perfil `gpu`, cuyo `simulador-gpu` (`abm-gpu`, D23)
necesita una GPU de NVIDIA y NVIDIA Container Toolkit. Sin ellos falla con

```
Error response from daemon: could not select device driver "nvidia" with capabilities: [[gpu]]
```

y el compose se detiene a la mitad: algunos servicios (por ejemplo `escenarios`, `aprobacion`,
`escenarios-xml` y `sincronizacion`) quedan en `Created` sin arrancar, y el panel los marca
caídos. Se arregla corriendo el comando de arriba; si quieres, borra el contenedor que quedó
creado con `docker rm epidemia-simulador-gpu-1`. Solo en una máquina con GPU se agrega
`--profile gpu` (ver `procesamiento/abm_gpu/README.md`).

**Para bajar todo, ahí sí va `'*'`:** `docker compose -f infra/docker-compose.yml --profile '*' down`. `down` sin `--profile` solo baja PostgreSQL, Redis y
MongoDB; los servicios siguen arriba y falla con `Network epidemia_default Resource is still in
use`. `down` no necesita la GPU, y de paso quita el `simulador-gpu` que haya quedado creado.

| Perfil | Servicios |
|---|---|
| `identidad` | `auth`, `sesiones`, `usuarios`, `roles` |
| `catalogos` | `enfermedades`, `parametros`, `regiones`, `poblacion`, `tipos-intervencion` |
| `vigilancia` | `casos`, `sincronizacion`, `dispositivos`, `evidencias`, `vacunas`, `importacion` |
| `escenarios` | `escenarios`, `intervenciones`, `aprobacion`, `validacion`, `escenarios-xml` |
| `simulacion` | `corridas`, `simulador`, `simulador-abm`, `resultados`, `comparacion`, `pareto` |
| `analitica` | `indicadores`, `series`, `zonas` |
| `plataforma` | `notificaciones`, `estado-servicios`, `consola` |
| `web` | `web`: el sitio en contenedor, en `http://localhost:5000` (el mismo puerto que `python -m frontend_web.run`: uno u otro). Se agrega con `--profile web` |
| `gpu` | `simulador-gpu`: solo con GPU de NVIDIA; no entra en el comando de arriba |

**La base.** El compose trae su propio PostgreSQL 16. La primera vez, con el volumen vacío,
`infra/postgres/10-inicializa.sh` carga el dump (con todas las migraciones), las dos semillas y
los permisos de `epidemia_app`, y pone la contraseña de cada rol `svc_*` desde
`DB_PASSWORD_<SERVICIO>`. No toca la base de tu máquina. Queda en `127.0.0.1:5433`, así que el
monolito también puede usarla:

```
DATABASE_URL=postgresql://epidemia_app:<EPIDEMIA_APP_PASSWORD de infra/.env>@127.0.0.1:5433/simulador_epidemico
```

Cada servicio se conecta con su rol. Para apuntar uno a otra base, define su
`DATABASE_URL_<SERVICIO>` completo (ver `infra/.env.example`). Una migración nueva entra en un
volumen ya cargado corriéndola con `psql` contra el puerto 5433; `down -v` borra la base (y
los archivos del emulador del bucket, en el volumen `bucket-datos`) y la vuelve a cargar desde
cero en el siguiente `up`. Si la migración crea el rol de un servicio nuevo (la 031 de
`dispositivos`, la 032 de `evidencias` o la 033 de `vacunas`), corre antes `python infra/genera_env.py`, que agrega
su `DB_PASSWORD_<SERVICIO>` a `infra/.env`, y ponle esa contraseña con
`ALTER ROLE svc_<servicio> PASSWORD '...'`: `10-inicializa.sh` solo las pone la primera vez.

**Si ya tenías el compose antes de MongoDB (D1, 2026-11-18).** Tu volumen de PostgreSQL no
tiene las migraciones 038 y 041, y `infra/.env` no tiene las contraseñas de MongoDB. Sin la
038, el simulador nuevo marca cada corrida como fallida y `resultados` no responde. En este
orden:

```bash
python infra/genera_env.py
docker compose -f infra/docker-compose.yml up -d postgres --wait
docker compose -f infra/docker-compose.yml exec postgres psql -v ON_ERROR_STOP=1 -U postgres -d simulador_epidemico -f /datos/migraciones/038_resumen_en_simulation_runs.sql
docker compose -f infra/docker-compose.yml exec postgres psql -v ON_ERROR_STOP=1 -U postgres -d simulador_epidemico -f /datos/migraciones/041_retira_simulation_results.sql
docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait
```

1. `genera_env.py` agrega `MONGO_ROOT_PASSWORD` y `MONGO_PASSWORD` sin tocar las demás.
2. La 038 copia a `simulation_runs` el resumen de las corridas que ya tenías.
3. La 041 borra `simulation_results`, y con ella la serie de esas corridas: su detalle sigue
   mostrando el resumen, pero sin curvas. Para recuperar las curvas de una, vuelve a lanzarla
   con la misma semilla.
4. El `up` crea MongoDB vacío y reconstruye la imagen base, que ahora trae `pymongo`.

Comprueba que `curl "http://localhost:5243/health?format=json"` diga `"mongodb": true`. Si
prefieres empezar de cero, `down -v` borra todos los volúmenes (también las corridas y los
archivos del bucket) y el siguiente `up` carga la base con todas las migraciones.

**El bucket (D30; D2, 2026-11-22).** El compose trae un emulador de Cloud Storage
(`fake-gcs-server`, servicio `bucket`) en `127.0.0.1:4443`, con el bucket `epidemia-archivos`.
`evidencias` guarda ahí las fotos de los casos y los reportes de las comparaciones, y las URLs
firmadas que regresa apuntan a `http://localhost:4443`, así que se abren en el navegador de tu
máquina. Para ver lo que hay: `curl "http://localhost:4443/storage/v1/b/epidemia-archivos/o"`.
Si ya tenías el compose antes de D2, tu base no tiene la 039 y las fotos viejas siguen en el
volumen `epidemia_evidencias-datos`, que ya nadie lee. En este orden:

```bash
docker compose -f infra/docker-compose.yml up -d postgres --wait
docker compose -f infra/docker-compose.yml exec postgres psql -v ON_ERROR_STOP=1 -U postgres -d simulador_epidemico -f /datos/migraciones/039_reportes_de_comparacion.sql
docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma up -d --build --wait
```

El `up` reconstruye las imágenes base, que ahora traen `google-cloud-storage`. Comprueba que
`curl "http://localhost:5224/health?format=json"` diga `"bucket": true`. Las fotos viejas no se
mudan solas: sus filas apuntan a `evidence/...` y `/content` responde 404 hasta que alguien las
suba con esa misma ruta; en la demostración se pueden dar por perdidas.

Con todo arriba (los 26 servicios, PostgreSQL y Redis) son unos 1,100 MiB: de 32 a 51 MiB por
servicio, 83 MiB PostgreSQL y 6 MiB Redis (medido el 21 de octubre).

Un servicio suelto, sin compose, necesita antes la imagen base:

```bash
docker build -f infra/docker/base.Dockerfile -t epidemia/base .
docker build -f microservicios/regiones/Dockerfile -t epidemia/regiones .
docker run --rm -p 5213:8000 --add-host=host.docker.internal:host-gateway   -e DATABASE_URL="postgresql://svc_regiones:<contraseña del rol>@host.docker.internal:5433/simulador_epidemico"   -e REDIS_URL="redis://:<REDIS_PASSWORD>@host.docker.internal:6380/0"   -e JWT_SECRET_KEY="<la misma cadena de los demás>"   epidemia/regiones
```

La carpeta de `tipos-intervencion` es `microservicios/tipos_intervencion/`.

### 4. Comprobar

```bash
for p in 5201 5202 5203 5204 5211 5212 5213 5214 5215 5251 5252 5253; do
  curl -s "http://127.0.0.1:$p/health?format=json"; echo
done
# cada uno: {"servicio": "...", "estado": "ok", "postgresql": true, "redis": true}
```

Con `estado-servicios` arriba, una sola consulta trae la salud de los 31 (los que no están
arriba salen `caido`), y su directorio da la URL de cada uno:

```bash
curl -s "http://127.0.0.1:5262/api/v1/services/health?format=json"
curl -s "http://127.0.0.1:5262/api/v1/services?format=json"
```

Para las rutas con candado, inicia sesión con `auth`:

```bash
curl -s "http://127.0.0.1:5201/api/v1/auth/captcha?format=json"
# {"captcha_id": "...", "pregunta": "3 + 5", ...}
curl -s -H "Content-Type: application/json" "http://127.0.0.1:5201/api/v1/auth/login?format=json" \
  -d '{"usuario": "admin", "password": "<la de la tabla de credenciales>", "captcha_id": "...", "captcha_respuesta": "8"}'
# {"access_token": "...", "refresh_token": "...", ...}
```

El captcha dura 5 minutos y sirve una vez. `usuarios` y `roles` exigen ADMINISTRADOR (`admin`).

Swagger queda en `http://localhost:<puerto>/docs`. Ábrelo con `localhost`, no con
`127.0.0.1`: el contrato declara `http://localhost:<puerto>` y con otro origen el navegador
bloquea "Try it out". Pega el `access_token` en **Authorize** (sin `Bearer`). Para ver XML,
deja `format` vacío y elige `application/xml` en **Media type**; para JSON, `format=json`.

**La consola de pruebas** queda en `http://localhost:5260` (perfil `plataforma`). Ábrela con
`localhost`, no con `127.0.0.1`: cada servicio abre CORS solo para `CONSOLE_ORIGIN`, que en el
compose es `http://localhost:5260`. Tiene el panel de salud de los 31, el inicio de sesión
(con captcha), Swagger de cada servicio con el token ya puesto y un probador que también
exporta la petición como `curl`. La pestaña **Recorrido** tiene los pasos del guion de
aceptación listos para correr en orden. El token vive solo en la memoria de la página:
recargarla cierra la sesión de la consola. Swagger UI se descarga de unpkg.com la primera vez que abres
su pestaña. Detalles en `microservicios/consola/README.md`.

### 5. Pruebas de los microservicios

No necesitan Docker ni base: usan fakeredis, mongomock y la base simulada.

```bash
pip install -r backend_web/requerimientos.txt -r procesamiento/requerimientos.txt \
            -r microservicios/comun/requirements.txt "fakeredis>=2.20,<3" "mongomock>=4.1,<5" pytest
export PYTHONPATH="$PWD:$PWD/microservicios/comun"
python -m pytest microservicios -q
```

Las de integración (`microservicios/pruebas_integracion/contenedores/`) corren contra los
contenedores, y ahí se saltan. Se corren con:

```bash
python infra/pruebas_integracion.py
```

El script levanta desde cero un compose aparte (proyecto `epidemia-pruebas`, con un segundo
`simulador`), sobre la base `simulador_epidemico_pruebas` y con sus propios volúmenes de
PostgreSQL y Redis: nunca toca los de la demostración. Corre las pruebas y lo borra
(`--conservar` lo deja arriba). Sus contraseñas, aleatorias, quedan en `infra/.env.pruebas`, que
no se sube. Publica los mismos puertos que el compose de la demostración, así que ese tiene que
estar abajo; el script lo revisa antes de empezar.

### 6. nginx como única entrada (D25, D26)

En la nube solo se entra por nginx, en 443. En local se prueba igual sumando
`infra/docker-compose.nginx.yml` al compose: nginx publica 80 (redirige a 443) y 443, y ningún
servicio publica su puerto. PostgreSQL, Redis y MongoDB siguen solo en `127.0.0.1`.

1. **El certificado**, una vez. Queda en `infra/nginx/certs/`, que no se sube a git:

   ```bash
   python infra/nginx/certificado_local.py
   ```

   Con [mkcert](https://github.com/FiloSottile/mkcert) instalado sale uno de confianza para el
   navegador, el escritorio y el emulador. Antes, corre tú `mkcert -install` una vez: agrega la
   autoridad de mkcert a los certificados en que confía tu sistema. Sin mkcert, el script usa
   OpenSSL (el de Git sirve) y sale uno autofirmado: sirve para probar, pero el navegador avisa
   y `curl` necesita `-k`. Para cambiar uno por otro, `--nuevo`.

2. **Levantar** los servicios y la web detrás de nginx (los mismos perfiles que arriba más
   `web`, sin `gpu`):

   ```bash
   docker compose -f infra/docker-compose.yml -f infra/docker-compose.nginx.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma --profile web up -d --build --wait
   ```

3. **Qué queda:**
   - `https://localhost/<servicio>/api/v1/...`: cada servicio bajo su nombre, con las mismas
     rutas. Swagger, en `https://localhost/<servicio>/docs`. A un servicio solo van sus rutas
     (`/api/...`, `/health`, `/docs` y `/openapi.json`): `/usuarios` o `/escenarios/3` son
     páginas de la web.
   - `https://localhost/consola/`: la consola de pruebas.
   - `https://localhost/`: la web (contenedor `web`). Llama a cada servicio por la red interna
     (`URL_SERVICIOS=http://{servicio}:8000`) y les pasa la IP de quien la usa, para que el
     límite por IP de D31 cuente a cada persona y no a la web.
   - `http://localhost/...` redirige a `https://`.
   - El directorio (`https://localhost/estado-servicios/api/v1/services`) da
     `https://localhost/<servicio>` como URL de cada servicio.

4. **La web en tu PC, para desarrollarla** con recarga automática: levanta sin `--profile web`
   y con `WEB_DESTINO=host.docker.internal:5000`, para que nginx la busque en tu PC. La web
   llama a cada servicio por su puerto (D36), que detrás de nginx ya no está publicado.
   Apúntala a nginx antes de arrancarla:

   ```bash
   for s in auth sesiones usuarios roles enfermedades parametros regiones poblacion tipos-intervencion casos sincronizacion dispositivos evidencias vacunas importacion escenarios intervenciones aprobacion validacion escenarios-xml corridas simulador resultados comparacion pareto indicadores series zonas notificaciones estado-servicios; do
     export "SERVICIO_$(echo "$s" | tr 'a-z-' 'A-Z_')_URL=https://localhost/$s"
   done
   # Con mkcert -install no hace falta más: la web (urllib) confía en el almacén del sistema.
   # Con el certificado autofirmado, que confíe en él:
   export SSL_CERT_FILE="$PWD/infra/nginx/certs/epidemia.pem"
   python -m frontend_web.run
   ```

5. **Variables**, todas con valor por omisión: `NGINX_PUERTO_HTTP` (80), `NGINX_PUERTO_HTTPS`
   (443), `NGINX_TIEMPO_MAXIMO` (30 s, el tiempo máximo por petición), `WEB_DESTINO`
   (`web:8000`, el contenedor) y `URL_PUBLICA_NGINX` (`https://localhost/{servicio}`; para el
   emulador de Android, `https://10.0.2.2/{servicio}`).

6. **Probarlo:** `python infra/pruebas_integracion.py --nginx` levanta el compose de pruebas con
   nginx y corre `test_compose_nginx.py`: prefijos, Swagger, el directorio, que ningún servicio
   ni la web publique su puerto, la web en la raíz, una llamada con token, que el límite cuente
   la IP real del cliente y el tiempo máximo.

**Por qué los servicios confían en nginx solo en este modo.** Con `DETRAS_DE_PROXY=1`, waitress
(`epidemia_comun/servir.py`) y Flask (`ProxyFix`) toman la IP del cliente, el protocolo, el host
y el prefijo de las cabeceras `X-Forwarded-*` que pone nginx, y nginx las sobrescribe siempre.
Sin eso el servicio vería la IP de nginx, y el límite por IP de D31 sería uno solo para todos.
La variable solo se prende cuando los servicios no publican su puerto: si alguien pudiera
llegar directo, falsearía esas cabeceras.

### 7. HTTPS con Let's Encrypt en la máquina (D26)

El despliegue completo en GCP, de la máquina a las actualizaciones, está en
[`DESPLIEGUE_GCP.md`](DESPLIEGUE_GCP.md); aquí, el certificado.

En la nube el certificado es de Let's Encrypt, gratuito y de confianza para el navegador, la
app de escritorio y la móvil (que trae la raíz ISRG Root X1). No hace falta comprar un dominio:
con la IP fija de la máquina, `34-56-78-90.sslip.io` resuelve solo a `34.56.78.90`.

**Antes:** la máquina de Compute Engine con IP externa fija y el firewall abierto en 80 y 443
(F1); Docker con Compose, `openssl` y `curl`; el repositorio y su `infra/.env`.

1. **La primera vez**, desde la raíz del repositorio en la máquina:

   ```bash
   sudo LETSENCRYPT_PRUEBA=1 bash infra/nginx/letsencrypt.sh   # ensayo, sin límites
   sudo NUEVO=1 bash infra/nginx/letsencrypt.sh                 # el certificado real
   ```

   Sin `DOMINIO`, el script arma el nombre con la IP externa de la máquina
   (`<ip-con-guiones>.sslip.io`). Pone un certificado provisional para que nginx arranque, lo
   levanta, pide el real por HTTP (puerto 80, `/.well-known/acme-challenge/`) y recarga nginx.
   Correrlo acepta los términos de Let's Encrypt. Con `LETSENCRYPT_CORREO` llegan los avisos de
   vencimiento; sin él, se registra sin correo.

2. **Anota el dominio en `infra/.env`** (`DOMINIO=34-56-78-90.sslip.io`), para que el compose lo
   tome siempre, y levanta todo con los tres archivos, los perfiles de arriba y la web:

   ```bash
   python3 infra/genera_env.py   # agrega SECRET_KEY_WEB si tu infra/.env es anterior a la web
   docker compose -f infra/docker-compose.yml -f infra/docker-compose.nginx.yml -f infra/docker-compose.letsencrypt.yml -f infra/docker-compose.cloud-logging.yml --profile identidad --profile catalogos --profile vigilancia --profile escenarios --profile simulacion --profile analitica --profile plataforma --profile web up -d --build --wait
   ```

   `docker-compose.cloud-logging.yml` manda los registros de cada contenedor a Cloud Logging
   (N6) con el driver `gcplogs`. Solo funciona en Compute Engine, con los alcances por omisión
   de la cuenta de servicio (incluyen `logging.write`): en una PC no lo sumes. Se ven en la
   consola, en **Logging → Explorador de registros**, con la consulta
   `logName="projects/<proyecto>/logs/gcplogs-docker-driver"`. La web y los servicios anotan
   cada petición con su `X-Correlation-ID`, y la web pasa el suyo a cada servicio al que llama:
   buscándolo se sigue una petición de punta a punta. Desde la terminal:

   ```bash
   gcloud logging read 'logName="projects/<proyecto>/logs/gcplogs-docker-driver" AND jsonPayload.container.name="/epidemia-web-1"' --limit 20 --freshness 1h
   ```

3. **Renovación:** sola. certbot intenta renovar cada 12 h y solo renueva cuando al certificado
   le quedan menos de 30 días; nginx recarga cada 6 h para tomar el nuevo sin cortar
   conexiones.

4. **Las apps** apuntan al directorio `https://<DOMINIO>/estado-servicios/api/v1/services`, que
   ya da `https://<DOMINIO>/<servicio>` como URL de cada servicio.

**Con un dominio propio** (el del equipo es `epidemos.app`): en su DNS, un registro A a la IP
fija y nada más; **sin AAAA** (la máquina no tiene IPv6 y Let's Encrypt lo preferiría) y, si hay
un CAA, que permita `letsencrypt.org`. Luego, en la máquina:

```bash
sudo LETSENCRYPT_PRUEBA=1 DOMINIO=epidemos.app bash infra/nginx/letsencrypt.sh   # ensayo
sudo NUEVO=1 DOMINIO=epidemos.app bash infra/nginx/letsencrypt.sh                 # el real
```

y `DOMINIO=epidemos.app` en `infra/.env` antes de volver a levantar todo, para que nginx y el
directorio de `estado-servicios` lo tomen. El simulador de abm-gpu de la PC también apunta a
`https://epidemos.app/notificaciones` (`infra/.env.gpu-remoto`).

**Si Let's Encrypt responde «too many certificates already issued for sslip.io».** `sslip.io`
no está en la Public Suffix List, así que todos sus usuarios comparten el límite semanal de
certificados nuevos. Las renovaciones no cuentan, pero el primero puede fallar. La salida es un
subdominio gratuito de [DuckDNS](https://www.duckdns.org), que sí está en la lista y cuenta
aparte: se crea en su página, se apunta a la IP fija y se corre el script con
`DOMINIO=<nombre>.duckdns.org`.

Probado en local el 2026-11-20 con un certificado de prueba en las rutas de Let's Encrypt:
nginx arranca, sirve `/.well-known/acme-challenge/` por el 80 sin redirigir y toma el
certificado renovado al recargar. El certificado real solo se puede sacar en la máquina, con
su IP pública.

### 8. El simulador de abm-gpu en tu PC (D23)

No alcanzaron los créditos para una máquina con GPU en GCP. El simulador de `abm-gpu` corre en
una PC con GPU de NVIDIA y toma las corridas de la cola de la máquina de la nube, como
cualquier otro simulador: la cola no sabe dónde corre quien la atiende.

```
PC con GPU                                    Máquina de GCP
simulador-gpu ── túnel SSH por IAP ─────────▶ Redis, PostgreSQL y MongoDB (en su 127.0.0.1)
              ── HTTPS ─────────────────────▶ nginx → notificaciones
```

El túnel lo abre la PC hacia la máquina, así que funciona detrás de un módem, y en la máquina
no se abre ningún puerto a internet: las bases siguen escuchando solo en su `127.0.0.1`. El
simulador entra con el rol `svc_simulador`, que solo puede escribir lo suyo (D18). Si la PC
está apagada, las corridas de `abm-gpu` esperan `encolado` en la cola, y las que quedaron a
medias se reencolan (D38).

**Una vez, en la nube:**

1. En `infra/.env` de la máquina, `MOTORES_HABILITADOS=abm-ref,abm-gpu`, y vuelve a levantar
   `corridas`. La máquina no levanta `simulador-gpu` (perfil `gpu`). Después de cada
   `git pull`, vuelve a correr el `up -d --build`: el simulador cambia con la máquina (por
   ejemplo, con D44 lee tres colas por motor y parte de `epidemia/base-simulacion`).
2. La API de IAP activada en el proyecto (`gcloud services enable iap.googleapis.com`; es
   gratuita) y una regla de firewall que deje entrar a IAP al puerto 22 (la corres tú, en la
   consola o con `gcloud`):

   ```bash
   gcloud compute firewall-rules create permitir-ssh-iap --network=default --direction=INGRESS --action=allow --rules=tcp:22 --source-ranges=35.235.240.0/20
   ```

   Con ella puedes borrar `default-allow-ssh`, que abre el 22 a todo internet.

   En Windows, gcloud lanza un Python para el túnel de IAP; si toma el primero del PATH (por
   ejemplo, el de MSYS2 que trae Git), la conexión se cierra con «Remote side unexpectedly
   closed network connection». `infra/tunel_gpu.py` le pasa el Python del SDK; para un
   `gcloud compute ssh --tunnel-through-iap` a mano, pon `CLOUDSDK_PYTHON` con la ruta de
   `google-cloud-sdk/platform/bundledpython/python.exe`.

**En tu PC** (Docker Desktop con la GPU, como en «En el contenedor» de
`procesamiento/abm_gpu/README.md`, y el SDK de Google Cloud con tu sesión, `gcloud auth login`):

1. Copia `infra/gpu-remoto.env.example` como `infra/.env.gpu-remoto` (no entra a git) y pon los
   valores de `infra/.env` de la máquina. Son secretos: los copias tú.
2. Abre el túnel y déjalo abierto (Ctrl+C lo cierra):

   ```bash
   python infra/tunel_gpu.py --vm <nombre-de-la-maquina> --zona us-central1-a
   ```

3. Levanta el simulador:

   ```bash
   docker compose --env-file infra/.env.gpu-remoto -f infra/docker-compose.gpu-remoto.yml up -d --build
   ```

   Queda `healthy` cuando alcanza Redis y PostgreSQL por el túnel. Desde ahí, cada corrida de
   `abm-gpu` que se lance en la nube la corre tu GPU.

La serie de una corrida se guarda en dos operaciones (borrar e insertar), no una por día: con
el simulador lejos de MongoDB, eso es lo que más pesa.

Probado en local el 2026-11-20 con `python infra/pruebas_integracion.py --gpu-remoto`: el
compose de pruebas hace de nube sin `simulador-gpu`, y el simulador corre en otro proyecto de
Docker conectado solo por un túnel simulado en los mismos puertos. Una corrida de `abm-gpu`
termina, con su serie en MongoDB, su resumen en PostgreSQL y el aviso en `notificaciones`.

---

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `psql: error: connection to server ... failed` | El servidor de PostgreSQL no está corriendo. Linux: `sudo systemctl start postgresql`. Windows/macOS: inícialo desde el instalador o los Servicios del sistema. |
| `password authentication failed for user "postgres"` | Contraseña incorrecta. En Linux puedes reasignarla: `sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'nueva';"` |
| `Peer authentication failed` (solo Linux) | Estás conectando por socket. Usa siempre `-h localhost`, que fuerza conexión TCP con contraseña. |
| `FATAL: database "simulador_epidemico" does not exist` | Te faltó el Paso 1, o escribiste otro nombre en el `.env`. |
| `psycopg2.OperationalError` al arrancar la app (p. ej. *la autentificación password falló para el usuario «epidemia_app»*) | El `DATABASE_URL` del `.env` no coincide con tu base/usuario/contraseña reales. Revisa el Paso 4.2. Antes, con PostgreSQL de Windows en español, este error salía disfrazado de `UnicodeDecodeError: ... byte 0xf3`; si todavía lo ves, es el mismo problema. |
| `permission denied for table ...` | Te faltó el Paso 3 (los `GRANT`), o lo corriste **antes** del Paso 2, cuando las tablas todavía no existían. Vuelve a correrlo. |
| Todo se ve en **cero** y no puedes entrar | Falta `demo_datos_nl.sql` (Paso 2). Sin él no existe `diana.flores` ni hay casos. |
| Municipios como “AnÃ¡huac” o “General TerÃ¡n” en Regiones y el mapa | La base se cargó en Windows con una versión de las semillas que no declaraba su codificación. Volver a correr la semilla no los corrige, porque no pisa filas que ya existen. Corrígelos con `psql -h localhost -U postgres -d simulador_epidemico -c "UPDATE regions SET name = convert_from(convert_to(name, 'WIN1252'), 'UTF8') WHERE level = 'municipio' AND strpos(name, U&'\00C3') > 0;"`, que deshace exactamente la lectura equivocada (9 municipios), o vuelve a empezar de cero (abajo). |
| Las **gráficas no aparecen** (el resto sí) | Highcharts se carga desde su CDN: necesitas internet. |
| `syntax error at or near "NULLS"` al cargar el esquema | Tu PostgreSQL es menor a 15. Actualiza. |
| El puerto 5000 está ocupado | Pon `EPIDEMIA_PORT=5001` en el `.env`, o libera el 5000. En macOS suele ocuparlo *AirPlay Receiver*. |
| `RuntimeError: Falta JWT_SECRET_KEY` o `Falta DATABASE_URL` | El `.env` no existe, no está en la raíz del repositorio o se quedó con los valores de ejemplo. Revisa el Paso 4.2. |
| `Demasiados intentos fallidos` al entrar | Cinco contraseñas equivocadas seguidas bloquean la cuenta 15 minutos. Espera; no hay que tocar la base. |

### Volver a empezar de cero

Si quedó algo a medias y prefieres reinstalar la base:

```bash
psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS simulador_epidemico;"
```

Y repite desde el Paso 1.

`demo_datos_nl.sql` es seguro de volver a correr las veces que quieras: trunca
las tablas de casos, escenarios y simulaciones antes de insertar.

---

# Notas del proyecto

## Por qué no se reusó el export de Figma tal cual

Los zips de `figma-to-html*` exportan puro `<div>`/`<span>` posicionados de forma
absoluta, sin un solo `<form>`, `<input>` o `<button>` real, y con varias imágenes
de fondo rotas (rutas a archivos que no venían en el zip). El mapa "nacional" de
una de las capturas es una foto de stock, no una visualización real.

Por eso todas las pantallas están reconstruidas desde cero como HTML/CSS/JS limpio,
replicando el diseño de las capturas (paleta muestreada directamente de las
imágenes: sidebar `#091426`, azul `#1b6ce3`, badges rojo/ámbar/verde), pero con
markup funcional de verdad.

## Alcance: qué funciona y qué no

Casi todo el sistema tiene lógica real: dashboard público, login, dashboard
autenticado, **monitoreo** (con *Compartir vista*), mapa, catálogo de enfermedades
(con *+ Nueva enfermedad*), captura de casos (*+ Nuevo Reporte*), usuarios y
auditoría. **Simulaciones** y **Comparación** todavía son páginas "Próximamente".

El **motor de simulación** y el **cálculo de la frontera de Pareto** ya existen como
paquetes de Python en `procesamiento/`, con pruebas, pero aún no están conectados a la base
ni a las pantallas. Ver *Motor de simulación* más abajo.

Los tres **"Exportar" sí son funcionales** — el del dashboard descarga el resumen
de situación, el de Enfermedades el catálogo y el de Monitoreo el detalle por zona,
los tres **respetando los filtros que tengas puestos**.

## Qué es real y qué es de relleno

- **Real de verdad**: todos los números de todas las pantallas salen de consultas
  SQL contra PostgreSQL. Nada está hardcodeado en el HTML.
- **Auditoría real**: `audit_log` no trae historial precargado. Se llena con tu
  uso real de la app (cada login, logout y exportación). Que la pantalla empiece
  vacía es lo correcto.
- **Sintético pero cargado en Postgres**: los 3,824 casos, el escenario y las
  corridas de simulación. Los generó `gen_demo_data.py` con semilla fija
  (reproducible). No son casos reales.

Para regenerar los datos sintéticos (o ajustar tendencias por municipio):

```bash
python datos/scripts/gen_demo_data.py > datos/postgres/semillas/demo_datos_nl.sql
```

Si no cambiaste el script, lo único que cambia en el archivo son los tres hashes de
contraseña, porque la sal de bcrypt es aleatoria. Cualquier cambio a la semilla se hace en el
script y no en el archivo: `backend_web/tests/test_archivos_sql.py` falla si dejan de coincidir.

## Decisiones que falta validar.

- **Tasa de incidencia**: la cambié de "%" (como en el mock de Figma) a *casos por
  100,000 habitantes*, que es la convención epidemiológica real. Un porcentaje
  sobre 5.8M de habitantes nunca da un número legible.
- **Clasificación Crítico/Alerta/Estable**: la definí yo (≥50% de aumento semanal
  = Crítico, ≥15% = Alerta, resto = Estable). No viene del documento del proyecto.
- **Zonas en riesgo**: municipios con incidencia >10 casos/100k en los últimos 7
  días. Umbral también definido por mí.
- **Mapa con polígonos oficiales de INEGI**: la geometría es la capa municipal del
  Marco Geoestadístico 2024 de INEGI (entidad 19), no un geojson comunitario. Los
  **51 municipios** tienen polígono, **Hualahuises incluido**. La clave `CVEGEO` del
  shapefile ya es el `regions.code` de 5 dígitos, así que el join es directo, sin
  emparejar por nombre. Como control: la suma de las áreas da 64,291 km² contra los
  64,220 km² que reporta INEGI para el estado (0.11% de diferencia; la fuente
  anterior se iba 1.4%). El shapefile viene proyectado en Lambert Cónica Conforme
  (EPSG:6372) y `build_municipios_inegi.py` lo reproyecta a lon/lat, que es lo que
  Highcharts necesita.
- **Población: Censo 2020 de INEGI para los 51 municipios.** Antes, 41 de ellos
  llevaban aproximaciones de orden de magnitud con errores de hasta 82%
  (Pesquería tenía 26,000 habitantes contra 147,624 reales), lo que inflaba su
  incidencia por 100,000 habitantes hasta seis veces. Ahora salen de
  `datos/censo/nl_poblacion_municipios_1990_2020.tsv`, y
  `datos/scripts/build_regiones_sql.py` verifica en cada corrida que los 51 municipios
  sumen el total estatal en los siete años censales. La migración `015` corrige
  las bases que ya existían.
- **Highcharts Maps para el mapa** (no Leaflet): la materia exige Highcharts, así
  que el choropleth usa `Highcharts.mapChart` + `Highcharts.geojson()`. Las 5
  categorías de la leyenda son `dataClasses` del `colorAxis`, con los mismos
  umbrales que usa `queries.py` en el backend. *Nota técnica*: si vuelves a tocar
  este chart, `Highcharts.geojson()` deja las propiedades anidadas en
  `.properties`, no al nivel superior — por eso `dibujarMapa()` las aplana a mano
  antes del `joinBy`, y pasa `mapData` directo en la serie (no solo en `chart.map`).
- **Enfermedades no trae Agente, Tipo ni Riesgo** del mock: ninguna de las tres
  existe en `004_catalogos.sql`, y se decidió **no** tocar el esquema entregado.
  Inventarlas en Python rompía la regla de que nada de la vista esté hardcodeado, y
  meterlas en `default_params` habría contaminado el contrato con el motor de
  simulación. La tabla se quedó con lo que el catálogo sí modela. Si más adelante
  quieren esas columnas, el camino limpio es una migración numerada nueva
  (`013_*.sql` en adelante), no un parche aparte.
- **Columna "Alta" en vez de "Última act."**: `diseases` no tiene `updated_at`,
  solo `created_at`.
- **Monitoreo: "HOSPIT." se volvió "Graves"**: el esquema no modela hospitalización
  en ninguna parte; lo más cercano es `cases.severity = 'grave'`, así que se muestra
  eso con su nombre real en vez de uno prestado.
- **Monitoreo: las "zonas" son municipios reales**: el mock inventaba Zona
  Norte/Centro/Sur/Este/Oeste; `regions` no tiene ese nivel.
- **Monitoreo: el toggle Línea/Columna/Área solo afecta la serie de casos diarios.**
  La incidencia acumulada se queda siempre como línea: es una curva que solo sube, y
  dibujarla en columnas junto a un segundo eje se lee como si esas barras fueran
  casos. El selector "Indicador" en cambio ordena la tabla de zonas por casos o por
  incidencia.
- **La tarjeta "INACTIVAS" marca 0**: es correcto, todas las enfermedades están
  activas. Si quieres verla moverse, da de baja lógica una en Postgres
  (`UPDATE diseases SET is_active = FALSE WHERE code = 'PATOGENO_X';`) — que la
  pantalla reaccione es justamente la prueba de que lee de la base.
- Agregué **Dengue, Zika y Malaria** al catálogo (antes solo había SARS-CoV-2,
  Influenza y Patógeno X) para que el panel se pareciera al diseño de Figma.

## Motor de simulación

`procesamiento/motor/` es un modelo SEIR estocástico con hospitalizados, fallecidos y vacunados,
por grupo de edad y reproducible por semilla (`seir-ref-0.1`). El cálculo de costo y frontera
de Pareto para comparar escenarios está aparte, en `procesamiento/analitica/`, porque sirve
para cualquier motor. No depende de Flask ni de la
base, y no trae valores epidemiológicos ni costos por defecto: cada parámetro debe
venir con su fuente o marcado como supuesto.

Desde la raíz del repositorio:

```bash
python -m procesamiento.motor               # ejemplo A/B/C/D con frontera de Pareto
python -m pytest procesamiento/tests        # pruebas del motor
```

El motor se importa siempre como `procesamiento.motor`, también en las pruebas y en los
microservicios. `import motor` solo funciona dentro de `procesamiento/` y carga una segunda
copia, con otras clases de excepción: un `except EscenarioInvalido` de un lado no atrapa lo
que lanza el otro.

Los números del ejemplo son **supuestos ilustrativos**, no datos de Nuevo León.

## Estructura del proyecto

```
backend_web/db.py            conexion a Postgres (lee .env)
backend_web/queries.py       todas las consultas SQL reales
backend_web/auth.py          credenciales: bcrypt y firma del JWT
backend_web/audit.py         bitacora real: cada login/logout/export escribe en audit_log
backend_web/tests/           pruebas de las consultas contra PostgreSQL real

frontend_web/run.py          arranque de la app Flask
frontend_web/app/routes.py   rutas Flask
frontend_web/app/permisos.py sesion por cookie y decoradores de acceso por rol
frontend_web/app/templates/  plantillas Jinja2
frontend_web/app/static/css/styles.css        estilos
frontend_web/app/static/js/nl_municipios.json geometria de los 51 municipios (generado)
frontend_web/tests/          pruebas de las rutas

procesamiento/motor/         motor de simulacion de referencia (seir-ref)
procesamiento/abm/           modelo basado en agentes (abm-ref), con el mismo contrato
procesamiento/analitica/     costo, impacto y frontera de Pareto, para cualquier motor
procesamiento/contrato.py    lo que entra y sale de un motor (docs/contratos/motor/)
procesamiento/tests/         pruebas del motor

datos/postgres/dump_completo.sql   esquema completo (migraciones concatenadas)
datos/postgres/migraciones/        cada migracion como archivo individual
datos/postgres/semillas/           municipios (generado) y datos de demostracion (incluye las 3 cuentas)

datos/scripts/build_municipios_inegi.py  capa municipal de INEGI -> geojson del mapa + centroides
datos/scripts/build_regiones_sql.py      censo + centroides + catalogo -> semillas/nl_municipios_completos.sql
datos/scripts/build_grupos_edad.py       ITER -> censo/nl_estructura_edad_municipios_2020.tsv + migracion 021
datos/scripts/build_letalidad_edad.py    literatura + censo -> migracion 020
datos/scripts/gen_demo_data.py           generador de los datos de demostracion (semilla fija)
datos/scripts/refresca_fechas_demo.sql   mueve los casos de demostracion al presente (psql "$DATABASE_URL" -f ...)
datos/scripts/verifica_migraciones.py    comprueba migraciones sueltas contra el dump
datos/scripts/prepara_base_pruebas.py    crea la base en la que corren las pruebas
datos/geo/inegi_mg2024/      capa municipal oficial (Marco Geoestadistico 2024, ent. 19)
datos/geo/                   catalogo INEGI y centroides de los 51 municipios
datos/censo/                 poblacion municipal y estructura por edad (Censo 2020, INEGI)

docs/                        esta guia, decisiones del equipo, arquitectura y contexto
frontend_web/requerimientos.txt    dependencias de la app web
procesamiento/requerimientos.txt   dependencias del motor
.env.example                 plantilla de configuracion (el .env real no se sube)
.gitignore                   excluye .env, entornos virtuales, caches, respaldos y archivo/
archivo/                     solo local, ignorado por git: pipeline y fuentes geograficas superadas
```

## Notas de seguridad

La versión v0.1 corre en entorno local y **no está endurecida para producción**:

- La contraseña de `epidemia_app` está en texto plano en este README.
- Es el servidor de desarrollo de Flask. Ya no arranca con el depurador ni abierto
  a la red por omisión (ver Paso 5), pero sigue sin ser un servidor de producción.
- El JWT se firma con HS256 y un secreto compartido. Se revalida contra la base en
  cada petición (una cuenta desactivada o un rol retirado dejan de valer al
  instante), pero no hay renovación ni lista de revocación: eso es de
  `auth-service` en la capa de microservicios.
- El bloqueo por intentos es por cuenta, no por dirección IP.

Nada de esto debería llegar tal cual a Google Compute Engine en el tercer parcial.
