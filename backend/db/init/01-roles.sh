#!/usr/bin/env bash
# Creates the two OpenCampus database roles and the dev/test databases.
#
#   opencampus_owner  owns the schema; used ONLY by Alembic migrations.
#   opencampus_app    used by the API at runtime. Not superuser, not owner,
#                     NOBYPASSRLS — so row-level security always applies to it.
#
# Runs automatically in the Docker Compose Postgres container on first start,
# or manually against any Postgres 14+ as a superuser:
#   OPENCAMPUS_DB_OWNER_PASSWORD=... OPENCAMPUS_DB_APP_PASSWORD=... \
#     psql -U postgres -v ON_ERROR_STOP=1 -f <(bash db/init/01-roles.sh --print)
set -euo pipefail

: "${OPENCAMPUS_DB_OWNER_PASSWORD:?OPENCAMPUS_DB_OWNER_PASSWORD is required}"
: "${OPENCAMPUS_DB_APP_PASSWORD:?OPENCAMPUS_DB_APP_PASSWORD is required}"

sql=$(cat <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opencampus_owner') THEN
    CREATE ROLE opencampus_owner LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'opencampus_app') THEN
    CREATE ROLE opencampus_app LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
  END IF;
END
\$\$;
ALTER ROLE opencampus_owner PASSWORD '${OPENCAMPUS_DB_OWNER_PASSWORD}';
ALTER ROLE opencampus_app PASSWORD '${OPENCAMPUS_DB_APP_PASSWORD}';
SELECT 'CREATE DATABASE opencampus OWNER opencampus_owner'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'opencampus') \gexec
SELECT 'CREATE DATABASE opencampus_test OWNER opencampus_owner'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'opencampus_test') \gexec
SQL
)

for db in opencampus opencampus_test; do
  sql+=$'\n'"\\connect ${db}"$'\n'"REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT ALL ON SCHEMA public TO opencampus_owner; GRANT USAGE ON SCHEMA public TO opencampus_app; REVOKE ALL ON DATABASE ${db} FROM PUBLIC; GRANT CONNECT ON DATABASE ${db} TO opencampus_owner, opencampus_app;"
done

if [[ "${1:-}" == "--print" ]]; then
  printf '%s\n' "$sql"
else
  printf '%s\n' "$sql" | psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres
fi
