# Copilot Instructions for Grug

## Project Overview

Grug is a self-hosted AI agent designed to assist with TTRPGs (Tabletop Role-Playing Games) and generally having a good time. The project aims to provide an interactive, helpful companion for tabletop gaming sessions, world-building, rule lookups, and storytelling.

## Goals and Priorities

- Keep the codebase simple, readable, and maintainable.
- Prioritize features that directly enhance the TTRPG experience (e.g., dice rolling, rule lookups, NPC generation, encounter tables).
- Prefer self-hosted, privacy-respecting solutions over third-party SaaS dependencies where practical.
- Favor user experience: responses should be fun, flavorful, and in the spirit of tabletop gaming.

## Architecture and Tech Stack

- This repository is in early stages; consult the README and any source files for the current stack.
- When adding features, prefer lightweight, dependency-minimal approaches.
- Document any new integrations or external services in the README.

## Coding Standards

- Write clear, self-documenting code with descriptive variable and function names.
- Add docstrings or comments for non-obvious logic, especially for AI/agent behaviour.
- Keep functions small and single-purpose.
- Avoid hardcoding configuration values; use environment variables or config files.

## Tooling and Environment

- This project uses **[uv](https://docs.astral.sh/uv/)** for dependency management and running Python.
- All dependencies are declared in `pyproject.toml` only — there is no `requirements.txt` and one must never be created.
- Dev dependencies (pytest, etc.) live in the `[dependency-groups] dev` section of `pyproject.toml`.
- Always run Python commands with `uv run` (e.g. `uv run pytest tests/`, `uv run python main.py`).
- Add new dependencies with `uv add <package>` (or `uv add --dev <package>` for dev-only).

## Testing

- Use **pytest** for all tests (never `unittest.TestCase` subclasses).
- Use pytest fixtures — shared fixtures go in `tests/conftest.py`.
- Write tests for all new features and bug fixes.
- Tests should cover both happy paths and edge cases.
- Run existing tests before submitting changes: `uv run pytest tests/`.

## Forbidden Practices

- Do not introduce unnecessary dependencies or frameworks.
- Do not commit secrets, API keys, or credentials to the repository.
- Do not break backward compatibility without a clear migration path and documentation.

## Keeping These Instructions Current

When the user corrects a response, points out a mistake, or shares an important pattern, best practice, or project convention, treat it as a signal to update this file and/or the relevant customization artifact (see section below). Specifically:

- If the correction represents a **standing rule, preference, or project context** (e.g. "we always use X", "never do Y in this codebase"), add it to the appropriate section of this file immediately.
- If the correction describes a **repeatable task or workflow** (e.g. "here is how we scaffold a new cog"), consider creating or updating a prompt file under `.github/prompts/` instead.
- If the correction defines a **reusable capability with scripts or multi-step logic** (e.g. "here is our full deploy workflow"), consider creating or updating an agent skill under `.github/skills/`.
- After applying the update, briefly confirm what was changed so the user knows the knowledge has been captured.

The goal is for this file and its companion artifacts to remain a living, accurate record of how Grug is built — so future Copilot sessions start from the right context without re-explaining the same things.

## Instructions vs. Prompt Files vs. Agent Skills

Use the right artifact for the right job. The VS Code customization docs ([code.visualstudio.com/docs/copilot/copilot-customization](https://code.visualstudio.com/docs/copilot/customization/overview)) and the GitHub repository instructions docs ([docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions)) define these three layers:

| Artifact | Location | When it applies | Best for |
|---|---|---|---|
| **Repository instructions** | `.github/copilot-instructions.md` (repo-wide) or `.github/instructions/*.instructions.md` (path-scoped) | Automatically included in every relevant request | Coding standards, project context, architectural decisions, standing rules ("always/never do X") |
| **Prompt files** | `.github/prompts/*.prompt.md` | When you invoke the slash command explicitly | Repeatable single tasks: scaffold a component, prep a PR, generate a test skeleton |
| **Agent skills** | `.github/skills/` (per [agentskills.io](https://agentskills.io) open standard) | Loaded on-demand when the task matches the skill description | Multi-step capabilities with scripts and resources; works across VS Code, GitHub Copilot CLI, and the coding agent |

**Decision guide:**
- _"This is just how we always write code here"_ → **instructions file**
- _"I want a slash command to kick off this task"_ → **prompt file**
- _"This is a complex workflow with scripts that multiple tools should share"_ → **agent skill**

## Additional Notes

- TTRPG terminology and flavour text are encouraged in variable names, comments, and log messages where appropriate — this is a fun project!
- If adding support for specific game systems (D&D, Pathfinder, etc.), keep game-system-specific logic isolated in clearly named modules.
