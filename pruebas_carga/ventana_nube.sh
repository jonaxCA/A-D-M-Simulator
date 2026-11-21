#!/usr/bin/env bash
# Ventana para las pruebas de carga en la máquina de GCP (F4). Las pruebas escriben casos,
# fotos y corridas, y para encontrar la saturación hay que quitar un rato los límites de D31.
# Esto deja la base de la demostración como estaba antes de la prueba:
#
#   sudo bash pruebas_carga/ventana_nube.sh abre     respalda y sube los límites
#   ... la prueba de carga desde la PC (pruebas_carga/README.md) ...
#   sudo bash pruebas_carga/ventana_nube.sh cierra   restaura la base, las fotos y los límites
#
# Respalda PostgreSQL (pg_dump), MongoDB (mongodump) y el volumen de las fotos en
# /var/backups/epidemia-carga (700, solo root). Al cerrar detiene los servicios, vacía las colas
# de corridas de Redis, restaura las tres cosas y vuelve a levantar todo. Las sesiones de Redis
# no se tocan: los tokens de la prueba vencen solos. Ninguna contraseña aparece en la línea de
# comandos: cada herramienta la lee del entorno de su contenedor.
set -euo pipefail
cd "$(dirname "$0")/.."

RESPALDO=${RESPALDO:-/var/backups/epidemia-carga}
MARCA="$RESPALDO/abierta"
VOLUMEN_FOTOS=${VOLUMEN_FOTOS:-epidemia_evidencias-datos}
if [ -n "${COMPOSE_CMD:-}" ]; then
    # Para ensayar en otro compose (por ejemplo el de pruebas en la PC).
    read -r -a COMPOSE <<< "$COMPOSE_CMD"
else
    COMPOSE=(docker compose -f infra/docker-compose.yml -f infra/docker-compose.nginx.yml
             -f infra/docker-compose.letsencrypt.yml -f infra/docker-compose.cloud-logging.yml
             --profile identidad --profile catalogos --profile vigilancia --profile escenarios
             --profile simulacion --profile analitica --profile plataforma --profile web)
fi
# Límites durante la ventana: tan altos que no estorban (peticiones/segundos).
LIMITES_ABIERTOS="LIMITE_NORMAL=1000000/60
LIMITE_PERMISIVO=1000000/60
LIMITE_ESTRICTO=1000000/60
LIMITE_PUBLICO=1000000/60"

conteos() {
    "${COMPOSE[@]}" exec -T postgres sh -c 'psql -U postgres -d "$POSTGRES_DB" -At -F " " -c "SELECT (SELECT count(*) FROM cases), (SELECT count(*) FROM simulation_runs), (SELECT count(*) FROM users)"'         | awk '{print $1 " casos, " $2 " corridas, " $3 " usuarios"}'
}

abre() {
    if [ -e "$MARCA" ] && [ "${FORZAR:-}" != "1" ]; then
        echo "Ya hay una ventana abierta desde $(cat "$MARCA"). Ciérrala primero (o FORZAR=1)." >&2
        exit 1
    fi
    (umask 077 && mkdir -p "$RESPALDO")
    echo "Antes: $(conteos)" | tee "$RESPALDO/conteos_antes.txt"

    echo "Respaldando PostgreSQL..."
    "${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U postgres -Fc -d "$POSTGRES_DB"' > "$RESPALDO/postgres.dump"
    echo "Respaldando MongoDB..."
    # La contraseña de root va en un archivo de configuración dentro del contenedor, no en la
    # línea de comandos, y se borra al terminar.
    "${COMPOSE[@]}" exec -T mongodb sh -c 'umask 077; c=$(mktemp); printf "password: %s\n" "$MONGO_INITDB_ROOT_PASSWORD" > "$c"; mongodump --quiet --config "$c" -u root --authenticationDatabase admin --archive --gzip; s=$?; rm -f "$c"; exit $s' > "$RESPALDO/mongo.archive.gz"
    echo "Respaldando las fotos..."
    docker run --rm --user 0 -v "$VOLUMEN_FOTOS":/datos:ro epidemia/base tar czf - -C /datos . > "$RESPALDO/evidencias.tgz"
    cp infra/limites.env "$RESPALDO/limites.env"
    ls -la "$RESPALDO"

    printf '\n# Ventana de pruebas de carga (pruebas_carga/ventana_nube.sh): se quita al cerrar.\n%s\n' \
        "$LIMITES_ABIERTOS" >> infra/limites.env
    date -Is > "$MARCA"
    echo "Subiendo los límites (se recrean los servicios)..."
    "${COMPOSE[@]}" up -d --wait
    echo "Ventana abierta. Al terminar la prueba: sudo bash pruebas_carga/ventana_nube.sh cierra"
}

cierra() {
    [ -e "$MARCA" ] || { echo "No hay ventana abierta (falta $MARCA)." >&2; exit 1; }
    for archivo in postgres.dump mongo.archive.gz evidencias.tgz limites.env; do
        [ -s "$RESPALDO/$archivo" ] || { echo "Falta $RESPALDO/$archivo: no restauro nada." >&2; exit 1; }
    done
    echo "Al cerrar: $(conteos)" | tee "$RESPALDO/conteos_al_cerrar.txt"

    servicios=$("${COMPOSE[@]}" config --services | grep -vxE 'postgres|mongodb|redis|nginx|certbot|base|simulador-gpu')
    echo "Deteniendo los servicios..."
    # shellcheck disable=SC2086
    "${COMPOSE[@]}" stop $servicios

    echo "Vaciando las colas de corridas de Redis..."
    "${COMPOSE[@]}" exec -T redis sh -c 'redis-cli --scan --pattern "queue:*" | while read -r k; do redis-cli DEL "$k" > /dev/null; done'

    echo "Restaurando PostgreSQL..."
    "${COMPOSE[@]}" exec -T postgres sh -c 'pg_restore -U postgres -d "$POSTGRES_DB" --clean --if-exists --single-transaction' < "$RESPALDO/postgres.dump"
    echo "Restaurando MongoDB..."
    "${COMPOSE[@]}" exec -T mongodb sh -c 'umask 077; c=$(mktemp); printf "password: %s\n" "$MONGO_INITDB_ROOT_PASSWORD" > "$c"; mongorestore --quiet --config "$c" -u root --authenticationDatabase admin --drop --archive --gzip; s=$?; rm -f "$c"; exit $s' < "$RESPALDO/mongo.archive.gz"
    echo "Restaurando las fotos..."
    docker run --rm -i --user 0 -v "$VOLUMEN_FOTOS":/datos epidemia/base sh -c 'find /datos -mindepth 1 -delete && tar xzf - -C /datos' < "$RESPALDO/evidencias.tgz"
    cp "$RESPALDO/limites.env" infra/limites.env

    echo "Levantando todo con los límites de siempre..."
    "${COMPOSE[@]}" up -d --wait
    echo "Después: $(conteos)" | tee "$RESPALDO/conteos_despues.txt"
    diff <(sed 's/^[^:]*: //' "$RESPALDO/conteos_antes.txt") <(sed 's/^[^:]*: //' "$RESPALDO/conteos_despues.txt") \
        && echo "La base quedó como antes de la prueba." \
        || echo "OJO: los conteos no coinciden con los de antes." >&2
    mv "$MARCA" "$RESPALDO/cerrada-$(date +%Y%m%d-%H%M%S)"
}

case "${1:-}" in
    abre) abre ;;
    cierra) cierra ;;
    *) echo "Uso: sudo bash $0 abre|cierra" >&2; exit 2 ;;
esac
