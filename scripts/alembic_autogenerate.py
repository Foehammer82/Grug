"""Pre-commit hook: auto-generate an Alembic migration when ORM models change.

Behaviour
---------
* Triggered only when ``grug/db/models.py`` or ``grug/db/pg_models.py`` are
  in the git index (i.e. staged for commit).
* If another file inside ``alembic/versions/`` is *also* already staged, the
  developer has handled the migration themselves — the hook exits cleanly.
* Otherwise it runs ``uv run alembic revision --autogenerate -m "auto"`` and
  stages the generated file, then exits with code 1 so the commit is paused.
  This forces a review pass before the migration lands in history, which is
  important because autogenerate silently omits pgvector ``Vector`` columns,
  ``IVFFlat`` indexes, and ``CREATE EXTENSION`` statements.
* If Postgres is unreachable (autogenerate fails), the hook prints instructions
  and exits 1.

Second-commit flow
------------------
1. Stage model change → hook generates migration, stages it, exits 1.
2. Developer reviews / edits the migration file.
3. ``git commit`` again → hook sees migration already staged → exits 0 → commit succeeds.
"""

import re
import subprocess
import sys
from pathlib import Path

MODEL_FILES = {"grug/db/models.py", "grug/db/pg_models.py"}
VERSIONS_PREFIX = "alembic/versions/"


def _staged_files() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.splitlines())


def main() -> int:
    staged = _staged_files()

    # Only run when ORM model files are being committed.
    models_staged = staged & MODEL_FILES
    if not models_staged:
        return 0

    # If the developer already staged a migration file, trust them.
    migrations_staged = {
        f for f in staged if f.startswith(VERSIONS_PREFIX) and f.endswith(".py")
    }
    if migrations_staged:
        staged_names = ", ".join(Path(f).name for f in migrations_staged)
        print(
            f"[alembic] Migration already staged ({staged_names}). Skipping autogenerate."
        )
        return 0

    print(
        f"[alembic] ORM model(s) changed: {', '.join(sorted(models_staged))}.\n"
        "[alembic] Attempting to auto-generate a migration..."
    )

    result = subprocess.run(
        ["uv", "run", "alembic", "revision", "--autogenerate", "-m", "auto"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[alembic] ERROR: Migration generation failed. Is Postgres running?")
        print(result.stderr or result.stdout)
        print(
            "\nTo generate manually once Postgres is available:\n"
            "  uv run alembic revision --autogenerate -m 'describe_your_change'\n"
            "Then stage the new file and commit again."
        )
        return 1

    # Parse the generated filename from alembic output: "Generating /abs/path.py"
    combined = result.stdout + result.stderr
    match = re.search(r"Generating (.+\.py)", combined)
    if not match:
        print("[alembic] Migration ran but could not determine output filename.")
        print(combined)
        return 1

    new_file = Path(match.group(1).strip())
    subprocess.run(["git", "add", str(new_file)], check=True)

    print(
        f"[alembic] Generated and staged: {new_file.name}\n"
        "\n"
        "  *** REVIEW REQUIRED before committing ***\n"
        "  autogenerate does NOT detect:\n"
        "    - pgvector Vector() columns\n"
        "    - IVFFlat / HNSW indexes\n"
        "    - CREATE EXTENSION statements\n"
        "\n"
        f"  Review: {new_file}\n"
        "\n"
        "  Once satisfied, run git commit again to complete the commit."
    )
    # Exit 1 to pause the commit — second commit will pass (migration now staged).
    return 1


if __name__ == "__main__":
    sys.exit(main())
