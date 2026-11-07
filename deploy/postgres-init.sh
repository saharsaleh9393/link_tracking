#!/usr/bin/env bash
set -euo pipefail
# psql quotes variables as literals/identifiers; never interpolate secrets into SQL text.
export LINKSPACE_OWNER_PASSWORD="$(cat /run/secrets/owner_password)"
export LINKSPACE_APP_PASSWORD="$(cat /run/secrets/app_password)"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
    --set=db="$POSTGRES_DB" <<'SQL'
\getenv owner_password LINKSPACE_OWNER_PASSWORD
\getenv app_password LINKSPACE_APP_PASSWORD
CREATE ROLE linkspace_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'owner_password';
CREATE ROLE linkspace_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER DATABASE :"db" OWNER TO linkspace_owner;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO linkspace_owner, linkspace_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
