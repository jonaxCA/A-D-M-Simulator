#!/usr/bin/env bash
# Crea el bucket privado de los archivos de EPIDEMIA en GCP (D30, RNF-K12, RNF-K18) y le da a la
# cuenta de servicio de la máquina lo justo para usarlo. Se corre una vez, desde una PC con gcloud
# y permiso en el proyecto (docs/DESPLIEGUE_GCP.md, §6):
#
#   bash infra/crea_bucket.sh
#
# Es idempotente: lo que ya existe no se vuelve a crear. No detiene la máquina: si le falta el
# alcance cloud-platform, imprime los comandos para dárselo.
set -euo pipefail

PROYECTO=${PROYECTO:-integracion-515321}
REGION=${REGION:-us-central1}
ZONA=${ZONA:-us-central1-c}
MAQUINA=${MAQUINA:-instance-20261120-215738}
# El nombre de un bucket es único en todo GCP: lleva el proyecto.
BUCKET=${BUCKET:-$PROYECTO-archivos}

CUENTA=$(gcloud compute instances describe "$MAQUINA" --zone "$ZONA" --project "$PROYECTO" \
         --format 'value(serviceAccounts[0].email)')
[ -n "$CUENTA" ] || { echo "La máquina $MAQUINA no tiene cuenta de servicio." >&2; exit 1; }
echo "Cuenta de servicio de la máquina: $CUENTA"

if gcloud storage buckets describe "gs://$BUCKET" --project "$PROYECTO" > /dev/null 2>&1; then
    echo "El bucket gs://$BUCKET ya existe."
else
    # Privado: acceso uniforme (sin ACL por objeto) y prevención de acceso público.
    gcloud storage buckets create "gs://$BUCKET" --project "$PROYECTO" --location "$REGION" \
        --uniform-bucket-level-access --public-access-prevention
fi

# Leer, escribir y borrar objetos, solo en este bucket.
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --project "$PROYECTO" \
    --member "serviceAccount:$CUENTA" --role roles/storage.objectAdmin > /dev/null
# Firmar las URLs sin llave privada: signBlob de IAM sobre su propia cuenta.
gcloud services enable iamcredentials.googleapis.com --project "$PROYECTO"
gcloud iam service-accounts add-iam-policy-binding "$CUENTA" --project "$PROYECTO" \
    --member "serviceAccount:$CUENTA" --role roles/iam.serviceAccountTokenCreator > /dev/null

ALCANCES=$(gcloud compute instances describe "$MAQUINA" --zone "$ZONA" --project "$PROYECTO" \
           --format 'value(serviceAccounts[0].scopes)')
if [[ "$ALCANCES" != *"/auth/cloud-platform"* ]]; then
    cat <<AVISO

La máquina no tiene el alcance cloud-platform: con los de omisión solo lee Cloud Storage y no
puede firmar URLs. Cambiarlo exige detenerla (unos minutos fuera de línea):

  gcloud compute instances stop $MAQUINA --zone $ZONA --project $PROYECTO
  gcloud compute instances set-service-account $MAQUINA --zone $ZONA --project $PROYECTO \\
      --service-account $CUENTA --scopes cloud-platform
  gcloud compute instances start $MAQUINA --zone $ZONA --project $PROYECTO
AVISO
fi

cat <<FIN

Listo. En la máquina, agrega a infra/.env:

  BUCKET_NOMBRE=$BUCKET

y vuelve a levantar con bash infra/levanta_nube.sh, que ya suma infra/docker-compose.gcs.yml.
FIN
