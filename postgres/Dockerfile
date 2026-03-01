FROM pgvector/pgvector:pg16

# Copy init scripts — run once on first container start (alphabetical order).
# 01-init.sh: enable the vector extension and apply startup tuning.
COPY init-scripts/ /docker-entrypoint-initdb.d/
