#!/usr/bin/env bash
# Construye y levanta EPIDEMIA en la máquina de GCP (docs/DESPLIEGUE_GCP.md): el compose principal
# con nginx, Let's Encrypt y Cloud Logging, y todos los perfiles con la web, menos gpu (el
# simulador de abm-gpu corre en una PC con GPU, D23). Deja la salida en ~/levanta.log y al final
# el estado de cada contenedor.
#
#   bash infra/levanta_nube.sh
#
# infra/.env tiene que tener DOMINIO (el certificado de Let's Encrypt ya emitido) y las
# contraseñas de genera_env.py. Corre docker con sudo.
set -uo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f infra/docker-compose.yml -f infra/docker-compose.nginx.yml
         -f infra/docker-compose.letsencrypt.yml -f infra/docker-compose.cloud-logging.yml
         --profile identidad --profile catalogos --profile vigilancia --profile escenarios
         --profile simulacion --profile analitica --profile plataforma --profile web)
LOG=${LOG:-$HOME/levanta.log}
{
  echo "inicio: $(date -Is)"
  sudo "${COMPOSE[@]}" up -d --build --wait
  echo "salida=$?"
  echo "fin: $(date -Is)"
  sudo "${COMPOSE[@]}" ps --format '{{.Service}} {{.State}} {{.Health}}' | sort
} > "$LOG" 2>&1
grep -E "^salida=" "$LOG"
