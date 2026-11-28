#!/usr/bin/env bash
# Crea el bucket privado de los archivos de EPIDEMIA en GCP (D30, RNF-K12, RNF-K18) y la cuenta de
# servicio propia de la máquina, epidemia-vm, con lo justo para usarlo. Se corre desde una PC con
# gcloud y permiso en el proyecto, antes de crear la máquina (docs/DESPLIEGUE_GCP.md, §2 y §6):
#
#   bash infra/crea_bucket.sh
#
# La máquina no usa la cuenta de Compute por omisión: esa tiene Editor en todo el proyecto y, con
# el alcance cloud-platform que necesita evidencias, cualquier contenedor sacaría del servidor de
# metadatos un token para casi todo GCP.
#
# Es idempotente: lo que ya existe no se vuelve a crear. No detiene la máquina: si no usa
# epidemia-vm con cloud-platform, imprime los comandos para cambiarla.
set -euo pipefail

PROYECTO=${PROYECTO:-integracion-515321}
REGION=${REGION:-us-central1}
ZONA=${ZONA:-us-central1-c}
MAQUINA=${MAQUINA:-instance-20261120-215738}
# El nombre de un bucket es único en todo GCP: lleva el proyecto.
BUCKET=${BUCKET:-$PROYECTO-archivos}
CUENTA_VM=${CUENTA_VM:-epidemia-vm}
CUENTA=$CUENTA_VM@$PROYECTO.iam.gserviceaccount.com

existe_cuenta() {
    gcloud iam service-accounts describe "$CUENTA" --project "$PROYECTO" > /dev/null 2>&1
}

if existe_cuenta; then
    echo "La cuenta $CUENTA ya existe."
else
    gcloud iam service-accounts create "$CUENTA_VM" --project "$PROYECTO" \
        --display-name "EPIDEMIA, máquina"
    # Una cuenta recién creada tarda unos segundos en verse en IAM.
    for _ in $(seq 30); do existe_cuenta && break; sleep 2; done
    existe_cuenta || { echo "La cuenta $CUENTA no aparece en IAM." >&2; exit 1; }
fi

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
# Cloud Logging (docker-compose.cloud-logging.yml) y las métricas del agente.
for ROL in roles/logging.logWriter roles/monitoring.metricWriter; do
    gcloud projects add-iam-policy-binding "$PROYECTO" --member "serviceAccount:$CUENTA" \
        --role "$ROL" --condition None > /dev/null
done
# Firmar las URLs sin llave privada: signBlob de IAM sobre su propia cuenta.
gcloud services enable iamcredentials.googleapis.com --project "$PROYECTO"
gcloud iam service-accounts add-iam-policy-binding "$CUENTA" --project "$PROYECTO" \
    --member "serviceAccount:$CUENTA" --role roles/iam.serviceAccountTokenCreator > /dev/null

if MAQ=$(gcloud compute instances describe "$MAQUINA" --zone "$ZONA" --project "$PROYECTO" \
         --format 'value(serviceAccounts[0].email,serviceAccounts[0].scopes)' 2> /dev/null); then
    read -r ACTUAL ALCANCES <<< "$MAQ"
    if [ "$ACTUAL" != "$CUENTA" ] || [[ "$ALCANCES" != *"/auth/cloud-platform"* ]]; then
        cat <<AVISO

La máquina usa ${ACTUAL:-ninguna cuenta} y necesita $CUENTA con el alcance cloud-platform
(evidencias escribe en el bucket y firma URLs). No le des cloud-platform a la cuenta de Compute
por omisión: tiene Editor en todo el proyecto. Cambiarla exige detener la máquina (unos minutos
fuera de línea):

  gcloud compute instances stop $MAQUINA --zone $ZONA --project $PROYECTO
  gcloud compute instances set-service-account $MAQUINA --zone $ZONA --project $PROYECTO \\
      --service-account $CUENTA --scopes cloud-platform
  gcloud compute instances start $MAQUINA --zone $ZONA --project $PROYECTO
AVISO
    fi
else
    cat <<AVISO

La máquina $MAQUINA no existe todavía. Créala como dice docs/DESPLIEGUE_GCP.md, §2, con:

  --service-account $CUENTA --scopes cloud-platform
AVISO
fi

cat <<FIN

Listo. En la máquina, agrega a infra/.env:

  BUCKET_NOMBRE=$BUCKET

y vuelve a levantar con bash infra/levanta_nube.sh, que ya suma infra/docker-compose.gcs.yml.
FIN
