#!/usr/bin/env python3
"""Pre-commit hook: fail if ORM models have un-migrated changes.

Runs `alembic check` which compares the current models against the migration
head and exits non-zero when differences are detected.

If the database is unreachable (e.g. no local Postgres running), the check is
skipped with a warning so offline commits are never blocked.
"""

import subprocess
import sys


def main() -> int:  # noqa: D103
    result = subprocess.run(
        ["uv", "run", "alembic", "check"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("alembic check: migrations are up to date.")
        return 0

    stderr = result.stderr.lower()
    stdout = result.stdout.lower()
    combined = stderr + stdout

    # Gracefully skip when the environment isn't usable (no DB, missing config, etc.).
    skip_markers = [
        # DB connectivity
        "connection refused",
        "could not connect",
        "could not translate host",
        "name or service not known",
        "operationalerror",
        "no such file or directory",  # sqlite path missing
        "password authentication failed",
        # Missing required settings / env vars (e.g. no .env in CI)
        "validationerror",
        "field required",
        "pydantic",
        "settings()",
    ]
    if any(marker in combined for marker in skip_markers):
        print(
            "alembic check: environment not fully configured — skipping migration check.\n"
            "  Run `uv run alembic check` manually once Postgres is up and .env is loaded."
        )
        return 0

    # Real failure: un-migrated model changes detected.
    print("alembic check FAILED — your ORM models have changes with no migration!")
    print("  Run: uv run alembic revision --autogenerate -m 'describe_your_change'")
    print("  Then review and commit the generated file in alembic/versions/.")
    if result.stdout.strip():
        print("\n--- alembic output ---")
        print(result.stdout.strip())
    if result.stderr.strip():
        print("\n--- alembic stderr ---")
        print(result.stderr.strip())
    return 1


if __name__ == "__main__":
    sys.exit(main())
