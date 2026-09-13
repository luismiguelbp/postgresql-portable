# PostgreSQL Portable

- Read the [README](README.md) for setup, layout, and usage.
- Read relevant documentation before changing application behavior.
- Discover skills under [`.agents/skills/`](.agents/skills/) and read the matching `SKILL.md` when the task fits. Do not load unused skills.

## Engineering Principles

- **KISS — Keep It Simple:** choose the simplest solution that meets the requirements.
- **LEAN:** minimize waste—code, dependencies, steps, and work that add no value.
- **YAGNI — You Aren’t Gonna Need It:** don’t implement features or abstractions until they’re actually needed.
- **DRY — Don’t Repeat Yourself:** keep a single source of truth; link instead of copying.

## Project Constraints

- Windows-first: batch helpers in `scripts/` (`{group}-{verb}.bat`) wrap `python -m postgresql_portable`.
- Batch scripts must run from repo root or `scripts/` and reuse `.venv` if present.
- Python >= 3.10, package in `src/postgresql_portable/`; dependencies only `python-dotenv`, `pytest`.
- Never commit `.env`, `data/`, `data_winccoa_tablespaces/`, `.venv/`, or PostgreSQL binaries.
- Tests use temp dirs and mocked subprocess calls — no running PostgreSQL required.

## Verification

- Tests: `pytest` (after `pip install -e .`)

## Conventional Commits

- Commits: `<type>: <short imperative summary>` (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`).
- Branches: `main` (releasable) and `dev` only.
