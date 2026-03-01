---
name: alembic-migrations
description: Create, run, inspect, and roll back Alembic database migrations for the Grug project. Use this skill whenever the user asks to add a migration, change a database schema, run alembic upgrade or downgrade, generate a new revision, or troubleshoot migration state. Applies only to Postgres deployments — SQLite uses create_all and does not use Alembic.
compatibility: Requires a Postgres DATABASE_URL set in .env and uv available in PATH.
metadata:
  author: blake
  version: "1.0"
---

# Alembic Migrations — Grug Project

## Context

Alembic is used **only for Postgres deployments**. When `DATABASE_URL` starts with `postgresql`, `init_db()` in `grug/db/session.py` calls `alembic upgrade head` automatically on startup. SQLite deployments use `create_all` and are unaffected.

Key paths:
- `alembic.ini` — Alembic config at the workspace root
- `alembic/env.py` — async env using `asyncpg` + `NullPool`; pulls `DATABASE_URL` from `grug.config.settings`
- `alembic/versions/` — versioned migration files
- `grug/db/models.py` — standard ORM tables (imported by `alembic/env.py`)
- `grug/db/pg_models.py` — pgvector embedding tables (also imported)

All commands use `uv run`.

---

## Common Commands

### Check current migration state
```bash
uv run alembic current
```

### Show migration history
```bash
uv run alembic history --verbose
```

### Apply all pending migrations
```bash
uv run alembic upgrade head
```

### Upgrade by N steps
```bash
uv run alembic upgrade +1
```

### Downgrade by one step
```bash
uv run alembic downgrade -1
```

### Downgrade to a specific revision
```bash
uv run alembic downgrade 0001
```

### Show pending migrations (what `upgrade head` would run)
```bash
uv run alembic heads
uv run alembic show head
```

---

## Creating a New Migration

### Auto-generate from model changes (recommended starting point)
```bash
uv run alembic revision --autogenerate -m "add_foo_column"
```
**Always review the generated file** — autogenerate misses pgvector `Vector` columns, IVFFlat indexes, and `CREATE EXTENSION`. Add those manually.

### Create a blank migration
```bash
uv run alembic revision -m "describe_the_change"
```

Generated files land in `alembic/versions/` with a timestamp+slug filename.

---

## Migration File Template

```python
"""Short description.

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-...
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "xxxx"
down_revision: Union[str, None] = "yyyy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("my_table", sa.Column("new_col", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("my_table", "new_col")
```

---

## Adding a pgvector Column

```python
from pgvector.sqlalchemy import Vector
from grug.rag.embedder import EMBEDDING_DIM  # 384

def upgrade() -> None:
    op.add_column(
        "my_table",
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )
    # IVFFlat cosine index (needs data to train — create after bulk insert if empty)
    op.execute(
        sa.text(
            "CREATE INDEX ix_my_table_vector "
            "ON my_table "
            "USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )

def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_my_table_vector"))
    op.drop_column("my_table", "embedding")
```

---

## Adding a New Table with a Vector Column

```python
from pgvector.sqlalchemy import Vector
from grug.rag.embedder import EMBEDDING_DIM

def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))  # idempotent
    op.create_table(
        "my_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_my_embeddings_vector "
            "ON my_embeddings USING ivfflat (embedding vector_cosine_ops) "
            "WITH (lists = 100)"
        )
    )
    # Register in grug/db/pg_models.py if the ORM should own this table.

def downgrade() -> None:
    op.drop_table("my_embeddings")
```

---

## Changing a Boolean Default (SQLite → Postgres safe)

Postgres rejects `server_default="0"` or `server_default="1"` on boolean columns. Always use:

```python
# Correct
sa.Column("active", sa.Boolean(), server_default=sa.true())   # TRUE
sa.Column("archived", sa.Boolean(), server_default=sa.false()) # FALSE

# Or as text
sa.Column("active", sa.Boolean(), server_default=sa.text("true"))
```

---

## Workflow for Schema Changes

1. **Update the ORM model** in `grug/db/models.py` or `grug/db/pg_models.py`.
2. **Generate a migration**:
   ```bash
   uv run alembic revision --autogenerate -m "brief_description"
   ```
3. **Review and edit** the generated file — especially for:
   - `Vector` columns (autogenerate won't know the type without extra config)
   - `IVFFlat` indexes
   - `CREATE EXTENSION` statements
   - `server_default` values on boolean columns
4. **Apply** against a local Postgres instance:
   ```bash
   uv run alembic upgrade head
   ```
5. **Verify** with `uv run alembic current` — should show the new revision.
6. **Test downgrade**:
   ```bash
   uv run alembic downgrade -1
   uv run alembic upgrade head  # re-apply
   ```

---

## If `alembic current` Shows Nothing (Fresh DB)

The migration history table (`alembic_version`) doesn't exist yet. Run:
```bash
uv run alembic upgrade head
```
This creates the table and stamps the db at `head`.

## If `alembic current` Shows a Diverged State

Inspect with `uv run alembic history --verbose`. If two heads, merge them:
```bash
uv run alembic merge heads -m "merge_heads"
uv run alembic upgrade head
```

## Running Migrations in Docker

The `grug` service runs `init_db()` on startup which calls `alembic upgrade head` automatically when `DATABASE_URL` is Postgres. To run manually inside the container:
```bash
docker compose exec grug uv run alembic upgrade head
docker compose exec grug uv run alembic current
```

See [references/REFERENCE.md](references/REFERENCE.md) for a full command cheatsheet.
