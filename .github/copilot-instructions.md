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

## Testing

- Write tests for all new features and bug fixes.
- Tests should cover both happy paths and edge cases.
- Run existing tests before submitting changes to ensure nothing is broken.

## Forbidden Practices

- Do not introduce unnecessary dependencies or frameworks.
- Do not commit secrets, API keys, or credentials to the repository.
- Do not break backward compatibility without a clear migration path and documentation.

## Additional Notes

- TTRPG terminology and flavour text are encouraged in variable names, comments, and log messages where appropriate — this is a fun project!
- If adding support for specific game systems (D&D, Pathfinder, etc.), keep game-system-specific logic isolated in clearly named modules.
