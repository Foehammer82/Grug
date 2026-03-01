#!/usr/bin/env bash
# Runs once when the Postgres data directory is first initialised.
# Enables the pgvector extension in the grug database and applies
# conservative memory tuning suited for a small self-hosted server.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable the pgvector extension so we can store and query embeddings.
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Tune memory settings for a modest self-hosted deployment.
    -- These are written to postgresql.auto.conf and survive restarts.
    ALTER SYSTEM SET shared_buffers       = '256MB';
    ALTER SYSTEM SET work_mem             = '16MB';
    ALTER SYSTEM SET maintenance_work_mem = '256MB';
    ALTER SYSTEM SET effective_cache_size = '512MB';

    SELECT pg_reload_conf();
EOSQL

echo "Grug DB initialised — pgvector enabled, memory tuned. GRUG STRONG."
