# Despliegue en GCP

Cómo está desplegado EPIDEMIA en Google Cloud y cómo se repite desde cero (F1, F6). El diagrama
de distribución está en la [arquitectura v3, §8](arquitectura/arquitectura_v3.md#8-despliegue-y-seguridad);
las decisiones, en D23 (GPU), D25 (nginx) y D26 (certificado).

| Pieza | Valor (2026-11-21) |
|---|---|
| Dirección | **https://epidemos.app** (DNS en name.com, registro A a la IP fija) |
| Proyecto y zona | `integracion-515321`, `us-central1-c` |
| Máquina | `instance-20261120-215738`, **e2-standard-4** (4 vCPU, 15 GB), Debian 13, disco de 50 GB |
| IP | `35.222.19.202`, estática |
| Contenedores | 37: nginx, certbot, la web, los 29 servicios, la consola, dos simuladores y las tres bases |
| GPU | No hay en GCP: el simulador de `abm-gpu` corre en una PC con GPU por un túnel (D23, §8) |

Con todo arriba la máquina usa unos 2.6 GB de memoria. Con 2 vCPU (e2-highmem-2) se saturaba con
unos 40 usuarios; con 4 vCPU y las conexiones a PostgreSQL reutilizadas aguanta unos 80 a 100
([`docs/pruebas/carga/2026-11-21_nube_perfiles_conexiones`](pruebas/carga/2026-11-21_nube_perfiles_conexiones/LEEME.md)).

## 1. Lo que necesitas en tu PC

- El SDK de Google Cloud con tu sesión: `gcloud auth login` (la corre cada quien; la sesión de la
  UDEM vence y la vuelve a pedir) y `gcloud config set project integracion-515321`.
- Permiso en el proyecto para Compute Engine e IAP.
- **En Windows**, gcloud usa PuTTY. Para un `gcloud compute ssh --tunnel-through-iap` desde Git
  Bash, pon `CLOUDSDK_PYTHON` con la ruta de `google-cloud-sdk/platform/bundledpython/python.exe`:
  con el Python de MSYS2 la conexión se cierra con «Remote side unexpectedly closed network
  connection». `infra/tunel_gpu.py` ya lo hace solo.

## 2. La máquina

Primero, desde tu PC, `bash infra/crea_bucket.sh` (§6): crea la cuenta de servicio de la máquina,
`epidemia-vm`, y el bucket. Luego, en la consola (Compute Engine → Crear instancia, con esa cuenta
y «Permitir acceso total a todas las API de Cloud») o con gcloud:

```bash
gcloud compute addresses create epidemia-ip --region us-central1
gcloud compute instances create epidemia --zone us-central1-c --machine-type e2-standard-4 \
  --image-family debian-13 --image-project debian-cloud --boot-disk-size 50GB \
  --address epidemia-ip --tags http-server,https-server \
  --service-account epidemia-vm@integracion-515321.iam.gserviceaccount.com --scopes cloud-platform
```

- **El alcance `cloud-platform`** lo necesita `evidencias` para escribir en el bucket y firmar las
  URLs (§6); con los alcances por omisión solo lee Cloud Storage. Con `cloud-platform` el alcance
  ya no limita nada: lo que la máquina puede hacer lo deciden solo los roles de IAM de su cuenta.
- **Por eso no la cuenta de Compute por omisión** (`<número>-compute@developer.gserviceaccount.com`):
  tiene Editor en todo el proyecto. Con `cloud-platform`, cualquier contenedor que lea el servidor
  de metadatos (todos pueden) sacaría un token para modificar casi todo en GCP. `epidemia-vm` solo
  tiene los cuatro roles de §6.
- Para cambiar el tipo de máquina: detenerla, **Editar → Configuración de la máquina**, guardar y
  encender. Conserva la IP, el disco y el certificado; Docker y los contenedores arrancan solos.

## 3. Firewall e IAP

Solo 80 y 443 abiertos a internet; SSH solo por IAP.

```bash
gcloud services enable iap.googleapis.com
gcloud compute firewall-rules create permitir-ssh-iap --direction INGRESS \
  --source-ranges 35.235.240.0/20 --allow tcp:22
gcloud compute firewall-rules delete default-allow-ssh default-allow-rdp
```

`default-allow-http` y `default-allow-https` se quedan (las etiquetas `http-server` y
`https-server` de la máquina). Para entrar:

```bash
gcloud compute ssh instance-20261120-215738 --zone us-central1-c --tunnel-through-iap
```

Sin `--tunnel-through-iap`, gcloud intenta el 22 directo y el firewall no contesta.

## 4. Docker, el repositorio y los secretos

Docker Engine y Compose desde el repositorio oficial de Docker para Debian
(`docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`),
y `systemctl enable --now docker` para que arranque con la máquina. Luego:

```bash
git clone --branch feat/tercer-parcial https://github.com/jonaxCA/A-D-M-Simulator.git epidemia
cd epidemia
python3 infra/genera_env.py      # crea infra/.env con contraseñas aleatorias; no las imprime
chmod 600 infra/.env
```

En `infra/.env`, además de lo que llena `genera_env.py`:

- `MOTORES_HABILITADOS=abm-ref,abm-gpu`: `corridas` acepta `abm-gpu` porque su simulador está en la
  PC con GPU.
- `DOMINIO=epidemos.app`, después de sacar el certificado (§5).

Los secretos viven solo en ese archivo, con permisos 600, fuera del repositorio y de las imágenes.
Si pasan a Secret Manager está por decidirse (S5).

## 5. Dominio y certificado

1. **DNS** (lo administra Rolando en name.com): un registro **A** de `epidemos.app` a la IP fija.
   **Sin AAAA** (la máquina no tiene IPv6 y Let's Encrypt lo preferiría) y, si se agrega un CAA,
   que permita `letsencrypt.org`. Nada de reenvío de URL ni página de estacionamiento.
2. **Certificado**, en la máquina, primero contra el servidor de pruebas de Let's Encrypt:

   ```bash
   sudo LETSENCRYPT_PRUEBA=1 DOMINIO=epidemos.app bash infra/nginx/letsencrypt.sh   # ensayo
   sudo NUEVO=1 DOMINIO=epidemos.app bash infra/nginx/letsencrypt.sh                 # el real
   ```

3. `DOMINIO=epidemos.app` en `infra/.env` y levantar todo (§6), para que nginx y el directorio de
   `estado-servicios` lo tomen.

La renovación es sola: certbot lo intenta cada 12 h y nginx recarga cada 6 h. Para comprobarla:

```bash
sudo docker exec epidemia-certbot-1 certbot renew --dry-run --webroot -w /var/www/certbot
```

`.app` exige HTTPS en todos los navegadores (HSTS precargado): sin certificado no abre nada. La
cadena llega a ISRG Root X1, que la app móvil y el escritorio ya traen. Más en
[INSTALACION.md §7](INSTALACION.md) y D26.

## 6. Levantar todo

**La primera vez, el bucket de los archivos (D30, D2).** Desde tu PC, con gcloud:

```bash
bash infra/crea_bucket.sh
```

- Crea, si no existe, la cuenta de servicio de la máquina,
  `epidemia-vm@integracion-515321.iam.gserviceaccount.com`, con solo estos roles:

  | Rol | Sobre | Para |
  |---|---|---|
  | `roles/storage.objectAdmin` | El bucket, nada más | Subir, leer y borrar los archivos |
  | `roles/logging.logWriter` | El proyecto | Mandar los registros a Cloud Logging (§7) |
  | `roles/monitoring.metricWriter` | El proyecto | Las métricas del agente de la máquina |
  | `roles/iam.serviceAccountTokenCreator` | La propia cuenta | Firmar las URLs con signBlob, sin llaves |

- Crea `gs://integracion-515321-archivos`, privado: acceso uniforme y sin acceso público.
- Si la máquina no existe, recuerda crearla con esa cuenta (§2). Si existe y no usa `epidemia-vm`
  con `cloud-platform`, imprime cómo cambiarla; eso exige detenerla unos minutos.
- Al final dice qué poner en `infra/.env` de la máquina: `BUCKET_NOMBRE=integracion-515321-archivos`.

En la nube no se levanta el emulador: `docker-compose.gcs.yml` apunta `evidencias` al bucket
real. Las URLs firmadas son de `storage.googleapis.com` y vencen a los 15 minutos.

```bash
bash infra/levanta_nube.sh
```

Construye y levanta el compose principal con `docker-compose.nginx.yml`,
`docker-compose.letsencrypt.yml`, `docker-compose.cloud-logging.yml` y `docker-compose.gcs.yml`,
y todos los perfiles con `web`, menos `gpu`. Deja la salida en `~/levanta.log` y termina con `salida=0` si todos los
contenedores quedaron sanos. Para comprobar desde fuera:

```bash
for s in auth sesiones usuarios casos corridas estado-servicios; do
  curl -s -o /dev/null -w "$s %{http_code}\n" "https://epidemos.app/$s/health?format=json"
done
curl -s https://epidemos.app/estado-servicios/api/v1/services?format=json   # las URL de cada servicio
```

nginx manda a cada servicio solo sus rutas (`/<servicio>/api/...`, `/health`, `/docs`,
`/openapi.json`); lo demás es la web, porque varias de sus páginas se llaman como un servicio
(`/usuarios`, `/escenarios/3`). La consola está en `/consola/`.

## 7. Registros en Cloud Logging

`docker-compose.cloud-logging.yml` manda lo que escribe cada contenedor a Cloud Logging, al
registro `gcplogs-docker-driver`. La web y los servicios anotan cada petición con su
`X-Correlation-ID`, y la web pasa el suyo a cada servicio que llama, así que una petición se
sigue de punta a punta. Escribe con `roles/logging.logWriter` de `epidemia-vm` (§6):

```bash
gcloud logging read 'logName="projects/integracion-515321/logs/gcplogs-docker-driver" AND jsonPayload.message:"<id>"' --freshness 1h
```

En la consola: **Logging → Explorador de registros**. `docker logs` sigue funcionando en la
máquina. Los primeros 50 GiB al mes no se cobran.

Además, si un servicio cae, se degrada o se recupera y el cambio dura 30 s, los ADMINISTRADOR
reciben un aviso `SYSTEM` en su bandeja (alertas técnicas de `estado-servicios`, F7);
`ALERTAS_TECNICAS=0` en `infra/.env` las apaga. Las colas y los simuladores vivos por motor,
incluido el de la PC con GPU, están en `https://epidemos.app/estado-servicios/api/v1/services/capacity`
y en la consola.

## 8. Actualizar

```bash
cd ~/epidemia
git pull --ff-only
git diff --name-only HEAD@{1} HEAD -- datos/postgres/migraciones   # ¿migraciones nuevas?
sudo bash infra/aplica_migraciones.sh <números>                    # si las hay; respalda antes
python3 infra/genera_env.py                                        # si el compose pide secretos nuevos
bash infra/levanta_nube.sh
```

**Las migraciones van antes de reconstruir**: la base de la máquina ya existe y
`infra/postgres/10-inicializa.sh` no vuelve a correr. Si el código nuevo usa una columna o una
tabla que la base no tiene, falla en cuanto se levanta. `aplica_migraciones.sh` respalda la base
en `/var/backups/epidemia-migraciones` y aplica cada migración en su transacción; si una falla, se
detiene. Las 050 a 055 se ensayaron dos veces seguidas sobre una copia de la base de la máquina
sin daño; de otras, revisa antes si son repetibles.

Después de actualizar la máquina, el simulador de `abm-gpu` de la PC también se reconstruye
(`up -d --build`, §9).

**Al pasar a D2 (el bucket, 2026-11-22):** antes de `levanta_nube.sh`, crea el bucket (§6), agrega
`BUCKET_NOMBRE` a `infra/.env` y aplica la 039 (`sudo bash infra/aplica_migraciones.sh 039`). Las
fotos que ya estaban en el volumen `epidemia_evidencias-datos` no se mudan solas. Para subirlas
con la misma ruta, desde la máquina:

```bash
sudo docker run --rm -v epidemia_evidencias-datos:/datos:ro google/cloud-sdk:slim \
  gcloud storage cp -r /datos/evidence gs://integracion-515321-archivos/
```

## 9. El simulador de `abm-gpu` en una PC con GPU (D23)

La PC abre un túnel SSH por IAP a la máquina y su simulador toma las corridas de `abm-gpu` de
Redis, como si estuviera adentro. Paso a paso en [INSTALACION.md §8](INSTALACION.md): el
`infra/.env.gpu-remoto` con los secretos de la máquina y
`SERVICIO_NOTIFICACIONES_URL=https://epidemos.app/notificaciones`, `python infra/tunel_gpu.py`
y `docker compose ... -f infra/docker-compose.gpu-remoto.yml up -d --build`. Las corridas de
`abm-gpu` solo se atienden mientras la PC esté encendida con el túnel abierto; si no, esperan en
su cola.

## 10. Pruebas de carga y respaldos

- **Pruebas de carga** en la nube, con una ventana que respalda la base, sube los límites y al
  cerrar la restaura: [`pruebas_carga/README.md`](../pruebas_carga/README.md)
  (`pruebas_carga/ventana_nube.sh abre|cierra`). Durante la prueba, nadie use las mismas cuentas
  en otro lado: cada una admite 3 sesiones (D41).
- **Respaldos:** los de la ventana (`/var/backups/epidemia-carga`) y los de las migraciones
  (`/var/backups/epidemia-migraciones`), en la máquina. No hay un respaldo programado.

## 11. Costos

Se paga por hora mientras la máquina está encendida (revisa el precio de e2-standard-4 en la
calculadora de GCP); la IP estática cobra un poco más mientras la máquina está apagada. Para
apagarla cuando no se usa:

```bash
gcloud compute instances stop instance-20261120-215738 --zone us-central1-c
gcloud compute instances start instance-20261120-215738 --zone us-central1-c
```

Al encender, Docker levanta los contenedores solo (`restart: unless-stopped`).

## 12. Problemas conocidos

| Síntoma | Causa y salida |
|---|---|
| `Reauthentication failed` en gcloud | La sesión venció: `gcloud auth login`. |
| PuTTY «inactive» al entrar por SSH | Falta `--tunnel-through-iap`: el 22 solo está abierto para IAP. |
| `additional privileges requested ... fs.read` al construir | La ruta de la carpeta con otras mayúsculas (`downloads` en vez de `Downloads`): entra con la ruta exacta. |
| La base nueva no arranca («unhealthy», luego «Skipping initialization») | Un `.sh` que no es de inicio en `infra/postgres/`: esa carpeta se ejecuta al crear la base. Solo va `10-inicializa.sh` (hay prueba). |
| Páginas de la web con 404 en la nube | nginx mandaba al servicio todo `/<servicio>/...`; corregido (§6). |
| `test_interoperabilidad` falla a veces en `auth .../mfa/{id}/enrollment-code` | La ruta no lee el cuerpo; depende de si Redis y la base contestan en esa corrida. Del bloque E. |
