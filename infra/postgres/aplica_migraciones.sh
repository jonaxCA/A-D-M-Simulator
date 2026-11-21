#!/usr/bin/env bash
# Aplica migraciones a una base que ya existe. 10-inicializa.sh solo corre la primera vez, con el
# volumen vacío; la base de la máquina de GCP (o la del compose en tu PC) no recibe sola las
# migraciones nuevas. Desde la raíz del repositorio:
#
#   sudo bash infra/postgres/aplica_migraciones.sh 050 051 052 053 054 055
#
# Antes de tocar nada respalda la base (pg_dump) en /var/backups/epidemia-migraciones. Cada
# migración del repositorio trae su BEGIN ... COMMIT, y corre con ON_ERROR_STOP: si una falla, esa
# se deshace completa y el script se detiene sin aplicar las siguientes. Corre como el superusuario
# postgres dentro del contenedor, así que ninguna contraseña pasa por la línea de comandos.
#
# Variables: COMPOSE_CMD (otro compose, por ejemplo el de pruebas), BASE_DATOS (otra base del
# mismo servidor; por omisión, la POSTGRES_DB del contenedor) y RESPALDO_DIR.
set -euo pipefail
cd "$(dirname "$0")/../.."

[ $# -gt 0 ] || { echo "Uso: sudo bash $0 <número> [<número>...]   (por ejemplo 050 051)" >&2; exit 2; }
RESPALDO_DIR=${RESPALDO_DIR:-/var/backups/epidemia-migraciones}
if [ -n "${COMPOSE_CMD:-}" ]; then
    read -r -a COMPOSE <<< "$COMPOSE_CMD"
else
    COMPOSE=(docker compose -f infra/docker-compose.yml)
fi

# Los archivos, en el orden pedido, antes de tocar nada: si falta uno, no se aplica ninguno.
archivos=()
for numero in "$@"; do
    coincidencias=(datos/postgres/migraciones/"$numero"_*.sql)
    if [ ! -e "${coincidencias[0]}" ] || [ ${#coincidencias[@]} -ne 1 ]; then
        echo "La migración $numero no existe o es ambigua en datos/postgres/migraciones/." >&2
        exit 1
    fi
    archivos+=("${coincidencias[0]}")
done

base='"${BASE_DATOS:-$POSTGRES_DB}"'
en_postgres() {
    "${COMPOSE[@]}" exec -T -e BASE_DATOS="${BASE_DATOS:-}" postgres sh -c "$1"
}

(umask 077 && mkdir -p "$RESPALDO_DIR")
respaldo="$RESPALDO_DIR/antes-de-$(date +%Y%m%d-%H%M%S).dump"
echo "Respaldando la base en $respaldo..."
en_postgres "pg_dump -U postgres -Fc -d $base" > "$respaldo"
[ -s "$respaldo" ] || { echo "El respaldo quedó vacío: no aplico nada." >&2; exit 1; }

for archivo in "${archivos[@]}"; do
    echo "Aplicando $(basename "$archivo")..."
    en_postgres "psql -U postgres -d $base -v ON_ERROR_STOP=1 -q -f -" < "$archivo"
done
echo "Listo: ${#archivos[@]} migración(es). Si algo salió mal, el respaldo está en $respaldo"
echo "(se restaura con pg_restore --clean --if-exists)."
