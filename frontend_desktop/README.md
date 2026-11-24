# EPIDEMIA · App de escritorio

> **Estado: Vigente** · 2026-11-08 · MVP del tercer parcial.

Manual de usuario: [`docs/manuales/manual_usuario_escritorio.md`](../docs/manuales/manual_usuario_escritorio.md).

App en Python y PySide6 para el **analista**. Diseña escenarios y su XML, los envía a revisión,
lanza lotes de réplicas y compara los resultados con exportación e impresión. Es el proceso que
le da D4 al escritorio. La web conserva la aprobación y la consulta.

Habla con los microservicios en **XML** y descarga la geometría municipal en **GeoJSON**,
el formato del contrato de `zonas/geometry`. Nunca toca PostgreSQL ni Redis. Conoce
una sola URL, la del directorio de `estado-servicios` (D13), y de ahí saca las demás.

## Instalar y correr

Desde la raíz del repositorio, con Python 3.12 o superior. Se usa un entorno virtual porque
Debian y Ubuntu no dejan instalar con pip en el Python del sistema (PEP 668):

```bash
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r frontend_desktop/requerimientos.txt
python -m frontend_desktop.run
```

Los servicios se levantan como en el `AGENTS.md` de la raíz. Estos son los perfiles que necesita
la app:

```bash
python infra/genera_env.py
docker compose -f infra/docker-compose.yml --profile identidad --profile catalogos \
  --profile escenarios --profile simulacion --profile plataforma up -d --build --wait
```

Variables de entorno opcionales:

| Variable                 | Por omisión              | Para qué                                                   |
|--------------------------|--------------------------|------------------------------------------------------------|
| `EPIDEMIA_DIRECTORIO`    | `http://localhost:5262`  | URL de `estado-servicios`; en la nube, la de nginx (D25)   |
| `EPIDEMIA_CONTRATOS`     | `docs/contratos` del repo | Carpeta con los XSD                                        |
| `EPIDEMIA_TIEMPO_ESPERA` | `15`                     | Segundos máximos por petición                              |
| `EPIDEMIA_DISPOSITIVO`   | sin definir              | `1` manda el identificador del equipo al iniciar sesión (D41), para despliegues con MFA o `DISPOSITIVO_OBLIGATORIO=1` |
| `EPIDEMIA_CARPETA_LOCAL` | `~/.epidemia-escritorio` | Dónde se guarda el identificador del equipo                |

Cuentas de la base de demostración (`docs/INSTALACION.md`):

- `alex.cavazos` / `Epidemia2026!`: ANALISTA, entra.
- `admin` / `Admin2026!`: ADMINISTRADOR, entra.
- `diana.flores` (EPIDEMIOLOGO) y `karla.trevino` (CAPTURISTA) son rechazadas con un mensaje.

El escenario «Ola Influenza ZMM - otono 2026» ya está aprobado, así que sirve para lanzar
corridas de inmediato.

## Qué hace

**Sesión**
- Inicio de sesión con captcha contra `auth`.
- Segundo paso para los perfiles críticos (D40): código TOTP o de respaldo (`mfa/verify`), y alta
  con el código que emite un ADMINISTRADOR (`mfa/enroll` y `mfa/confirm`, que muestra una vez los
  códigos de respaldo). Con `EPIDEMIA_DISPOSITIVO=1` manda un identificador estable del equipo
  (D41).
- Revisa el rol con `sesiones` (la sesión está en Redis) y `usuarios`.
- Renueva el token una sola vez cuando el servidor responde `TOKEN_EXPIRADO`.
- Si la sesión fue revocada o cerrada, vuelve al login.
- Los tokens solo viven en memoria.

**Escenarios**
- Lista con búsqueda y detalle.
- Línea de tiempo y tabla de intervenciones.
- Agregar, quitar y mover intervenciones. El formulario se arma con el `param_schema` de cada
  tipo.
- Nueva versión, duplicar, validar con `validacion` y enviar a revisión.
- Exportar `.xml` y abrir un `.xml` local. El archivo se valida contra `escenario.xsd` antes de
  importarlo.

**Simulaciones**
- Cola con pestañas, filtro y avance de cada corrida.
- Rejilla de réplicas por versión.
- Cancelar una corrida o todas las que esperan de una versión.
- **Nuevo lote:** N réplicas × versiones aprobadas, con semillas 1..N. Pide confirmación con
  menos de 30.
- Exportar el historial a CSV.

**Comparación**
- Toma de cada versión una corrida completada por semilla, y solo las semillas comunes a todas.
- Resume en el cliente media, mediana y p5–p95 (D8).
- Frontera sobre medianas contra el costo de `pareto`.
- Curvas de casos activos con banda.
- Exporta CSV (tabla y curvas) y PDF, e imprime.
- Sube el PDF a `evidencias` (`POST /api/v1/reports?runs=…`, con `X-Content-SHA256`) y lo abre con
  la URL firmada de 15 minutos (`/reports/{id}/url`) (RF-F17, D35). En local va al emulador del
  bucket.
- Siempre muestra el aviso del servidor de que no es una predicción.

**Datos** (D6, D53)
- Lista las versiones de los conjuntos observados de `importacion`, con su fuente, licencia, corte,
  huella y puntos (`serie_observada.xsd`).
- Verifica la calidad de un CSV, JSON o XML sin guardarlo (`/datasets/validate`) e importa la
  versión siguiente de su clave (`POST /datasets`).

**Proyectos** (D54, RF-D12, RF-D19)
- Lista, crea, cambia (solo lo que cambió), archiva y restaura proyectos de `escenarios`
  (`/projects`). La enfermedad y la región se bloquean cuando el proyecto tiene escenarios.
- Mete y saca escenarios de la misma enfermedad y región (`PUT /scenarios/{id}/project`), y los
  archiva o restaura (`/scenarios/{id}/archive` y `/restore`).

**Calibración** (D50, RF-E17, RF-F13, RF-F14)
- Lanza, sigue y cancela calibraciones de `seir-ref` por ABC por rechazo contra una serie observada
  (`/calibrations` del servicio `calibracion`), con muestras, semillas, cuantil y semilla del muestreo.
- Muestra el conjunto y su versión, el motor, el método y la huella, los estimados de R₀, ρ y φ, el
  RMSE, el R² y la cobertura de las ventanas de calibración y validación, y la gráfica de lo observado
  contra la mediana y la banda p5–p95 (`/fit`). Evalúa un juego de parámetros sin guardar (`/evaluate`).
- Crea el borrador del escenario calibrado (`/scenario`): escenario, intervenciones y R₀ con su
  fuente. Pasa por revisión como cualquier otro. Declarar un modelo calibrado no se hace desde aquí.

**Además**
- La barra de estado muestra la salud de los servicios, la cola y los avisos de
  `notificaciones`.
- Bitácora local de actividad (`actividad.log` en la carpeta de datos de la app; su ruta se
  imprime al arrancar). Nunca guarda tokens ni contraseñas.

Usa, entre otros, `estado-servicios`, `auth`, `sesiones`, `usuarios`, `enfermedades`,
`regiones`, `tipos-intervencion`, `escenarios`, `intervenciones`, `validacion`, `aprobacion`,
`escenarios-xml`, `corridas`, `resultados`, `comparacion`, `pareto`, `zonas`, `roles`,
`notificaciones`, `evidencias` e `importacion`.

## Qué cambió respecto al Figma

- **Fuera:** Panorama, Mapa, Análisis, Enfermedades y Auditoría. Repetían el tablero web o no
  son del analista.
- **Sin vista previa de β(t):** habría que reimplementar el motor en el cliente. En su lugar
  está la validación del servidor.
- **Línea de tiempo de solo lectura:** `intervenciones` no tiene PUT, así que editar es quitar y
  volver a agregar.
- **Lanzar:** solo versiones aprobadas (D5).
- **Sin** prioridad, reintentos ni tiempo restante: ningún servicio tiene esos datos.
- **Banda p5–p95** en lugar de p25–p75 (D8).
- **Lectura neutra de la frontera:** no recomienda (regla 10).

## Límites conocidos

- **Cada réplica es su propio lote en la base** (`simulation_batches.replicas` = 1). El lote
  real en el servidor queda para cuando D8 se confirme.
- **`GET /runs`** no tiene offset y regresa como mucho 100 corridas. De ahí el máximo de 100
  réplicas por versión. `comparacion` y `pareto` aceptan 50 corridas por llamada, así que la app
  parte la petición.
- **`escenario.xsd`** limita la población a 5 M, pero el motor acepta 20 M. Una versión más
  grande no se puede exportar.
- **Respuestas sin XSD** (catálogos, lista y detalle de escenarios, sesión, validación,
  notificaciones): solo se leen. Se valida contra XSD todo lo que lo tiene: corridas,
  intervenciones, envío, export/import, comparación, pareto y errores.
- **Firma del JWT:** el cliente no la verifica (HS256). La validación real es
  `sessions/current` contra Redis.
- **Regiones:** `regiones` solo lista los 51 municipios. Un escenario nuevo no puede ser de todo
  el estado.

## Pruebas

```bash
python -m pytest frontend_desktop
```

`test_humo.py` levanta la ventana sin pantalla (`QT_QPA_PLATFORM=offscreen`). Sus respuestas
salen de `docs/contratos/*/ejemplos`.

En Windows, sin pantalla Qt no encuentra fuentes y los PDF de las pruebas salen con cuadros en
lugar de letras: fallan las tres que leen el texto del PDF. La app exporta bien; para las pruebas,
indica la carpeta de fuentes (en PowerShell, `$env:QT_QPA_FONTDIR = "C:\Windows\Fonts"`).
