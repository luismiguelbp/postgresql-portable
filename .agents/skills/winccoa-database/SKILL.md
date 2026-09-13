---
name: winccoa-database
description: Provision or remove the Siemens WinCC OA NGA database on portable PostgreSQL. Use when creating, recreating, dropping, or troubleshooting the WinCC OA database (WINCCOA_* settings, version-specific schema behavior).
---

# WinCC OA Database

## Prerequisites

- Server running (`scripts\postgres-start.bat`).
- `.env` set: `PG_PASSWORD`, `WINCCOA_USERNAME`, `WINCCOA_PASSWORD`, `WINCCOA_DATABASE`, `WINCCOA_VERSION` (`3.19`, `3.20`, or `3.21`), `WINCCOA_SCHEMA` (folder with Siemens `schema.sql`).
- If `WINCCOA_SCHEMA` contains a version segment (e.g. `...\WinCC_OA\3.19\...`), it must equal `WINCCOA_VERSION`.
- Quote passwords containing `#` or spaces.

## Create

```bat
scripts\winccoa-create.bat
```

- `3.19`: uses tablespaces (`winccoa`, `winccoa_events`, `winccoa_alerts`); `schema.sql` drops and recreates the database.
- `3.20` / `3.21`: no tablespaces; skips bundled `config.sql`; drops existing DB before create when needed.
- Recreate: set `WINCCOA_FORCE_RECREATE=yes` in `.env`.

## Drop

```bat
scripts\winccoa-drop.bat --yes
```

Requires `PG_PASSWORD` plus confirmation (`--yes` or `WINCCOA_CONFIRM=yes`). For `3.19` also drops the three tablespaces. Optional: `--drop-user` (or `WINCCOA_DROP_USER=yes`) removes the role; `--remove-data` deletes local `data_winccoa_tablespaces\` directories.

## Troubleshooting

- Missing-var error names the var — set it in `.env`.
- `WINCCOA_VERSION must be one of ...` — fix the version string.
- Version/path mismatch — align `WINCCOA_SCHEMA` with `WINCCOA_VERSION`.
- Auth failure — `PG_PASSWORD` must be the `postgres` superuser password.
- Python equivalents: `python -m postgresql_portable create-winccoa`, `python -m postgresql_portable drop-winccoa --yes`.
