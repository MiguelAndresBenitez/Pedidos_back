#!/bin/sh
# Fija las contraseñas de los roles creados por 01-roles.sql, desde el entorno.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v clave_owner="$MINUTAS_CLAVE_OWNER" -v clave_app="$MINUTAS_CLAVE_APP" <<'SQL'
ALTER ROLE minutas_owner PASSWORD :'clave_owner';
ALTER ROLE minutas_app PASSWORD :'clave_app';
SQL
