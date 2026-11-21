#!/bin/sh
# Carga la base la primera vez que arranca el contenedor, con el volumen vacío: el dump, las
# dos semillas y los permisos del monolito, en el orden de los pasos 1 a 3 de
# docs/INSTALACION.md. Después pone la contraseña de cada rol. Las contraseñas se leen del
# entorno con \getenv: no aparecen en la línea de comandos ni en ningún archivo. Con el
# volumen ya lleno, PostgreSQL no vuelve a correr este script.
set -eu

base() {
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" "$@"
}

if [ -z "${EPIDEMIA_APP_PASSWORD:-}" ]; then
    echo "Falta EPIDEMIA_APP_PASSWORD en infra/.env (python infra/genera_env.py)" >&2
    exit 1
fi

# El rol del monolito existe antes que el dump, como en el paso 1.
base <<'SQL'
\getenv clave EPIDEMIA_APP_PASSWORD
CREATE ROLE epidemia_app LOGIN PASSWORD :'clave';
SQL

base -f /datos/dump_completo.sql
base -f /datos/semillas/nl_municipios_completos.sql
base -f /datos/semillas/demo_datos_nl.sql

# Paso 3: los permisos del monolito.
base <<'SQL'
GRANT USAGE ON SCHEMA public TO epidemia_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO epidemia_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO epidemia_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO epidemia_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO epidemia_app;
SQL

# La contraseña de cada rol de servicio: DB_PASSWORD_ZONAS es la de svc_zonas.
for variable in $(env | sed -n 's/^\(DB_PASSWORD_[A-Z_]*\)=.*/\1/p' | sort); do
    rol="svc_$(echo "${variable#DB_PASSWORD_}" | tr 'A-Z' 'a-z')"
    if [ -z "$(printenv "$variable")" ]; then
        echo "Aviso: $variable está vacía; $rol queda sin contraseña" >&2
        continue
    fi
    base -v rol="$rol" <<SQL
\\getenv clave $variable
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rol') AS falta \\gset
\\if :falta
\\echo Aviso: no existe el rol :rol
\\else
ALTER ROLE :"rol" PASSWORD :'clave';
\\endif
SQL
done
