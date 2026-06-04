# PostgreSQL Portable (ZIP version)

Run PostgreSQL on Windows without an installer or admin privileges.

This repo holds the database cluster and helper scripts. PostgreSQL binaries are not included — download and point `PG_INSTALL` at them.

## Prerequisites

1. Download [EnterpriseDB PostgreSQL binaries](https://www.enterprisedb.com/download-postgresql-binaries) (Windows x64).

2. Extract the ZIP to any folder you like. Use the inner `pgsql` directory (do not flatten the archive). Copy that path for `PG_INSTALL`, for example:

   `D:\Tools\postgresql-17.6-1-windows-x64-binaries\pgsql`

3. Copy `.env.example` to `.env` and set `PG_INSTALL` to that path:

   ```ini
   PG_INSTALL=D:\Tools\postgresql-17.6-1-windows-x64-binaries\pgsql
   PG_DATA=data
   ```

   `PG_BIN` defaults to `PG_INSTALL\bin`. `PG_DATA` is relative to this repo unless you use an absolute path.

4. For WinCC OA: set `PG_PASSWORD` and all `WINCCOA_*` variables in `.env` — see `.env.example` and [WinCC OA database](#wincc-oa-database) below.

## First-time setup

```bat
scripts\pg-setup.bat
scripts\pg-info.bat
scripts\postgres-init.bat
scripts\postgres-start.bat
scripts\postgres-connect.bat
```

Run scripts from the repo root or from `scripts\`. `pg-setup.bat` creates `.venv` once, then reuses it.

`postgres-init.bat` creates the cluster (UTF-8, English US locale, superuser `postgres`, SCRAM). You will be prompted for a password. To re-init, delete `data\` first.

### WinCC OA database

In `.env` (see `.env.example`):

```ini
PG_PASSWORD=postgres_superuser_password
WINCCOA_USERNAME=winccoa
WINCCOA_PASSWORD="your_password"
WINCCOA_DATABASE=winccoa
WINCCOA_VERSION=3.19
WINCCOA_SCHEMA=C:\Siemens\Automation\WinCC_OA\3.19\data\NGA\PostgreSQL\sql
```

`WINCCOA_VERSION` must be `3.19`, `3.20`, or `3.21` and must match your WinCC OA install. If `WINCCOA_SCHEMA` contains a version segment (e.g. `...\WinCC_OA\3.19\...`), it must equal `WINCCOA_VERSION`.

`WINCCOA_SCHEMA` must point at the folder with Siemens `schema.sql`. Quote passwords that contain `#` or spaces.

| Version | Schema behavior |
|---------|-----------------|
| **3.19** | Tablespaces (`winccoa`, `winccoa_events`, `winccoa_alerts`); `schema.sql` drops and recreates the database |
| **3.20 / 3.21** | No tablespaces; skips bundled `config.sql` (uses `.env` credentials); drops existing DB before create when needed |

After the server is running:

```bat
scripts\winccoa-create.bat
```

Applies the full NGA schema for your `WINCCOA_VERSION`. Set `WINCCOA_FORCE_RECREATE=yes` to drop and recreate (3.20+ drops the database in Python first; 3.19 relies on `schema.sql`).

### Remove WinCC OA database

```bat
scripts\winccoa-drop.bat --yes
```

Requires `PG_PASSWORD` and confirmation (`--yes` or `WINCCOA_CONFIRM=yes` in `.env`). Drops `WINCCOA_DATABASE` and terminates active connections. For `WINCCOA_VERSION=3.19`, also drops tablespaces `winccoa`, `winccoa_events`, and `winccoa_alerts`.

Optional flags:

- `--drop-user` or `WINCCOA_DROP_USER=yes` — also remove `WINCCOA_USERNAME` role
- `--remove-data` — delete local `data_winccoa_tablespaces\` directories after drop

## Daily use

```bat
scripts\postgres-start.bat
scripts\postgres-connect.bat
scripts\postgres-stop.bat
```

Other scripts: `postgres-restart.bat`, `postgres-status.bat`, `pg-info.bat`.

`postgres-status.bat` shows server health, cluster settings, installed databases, and WinCC OA `.env` targets.
`pg-info.bat` shows paths and config only (works when the server is stopped).

Pass extra `psql` arguments through connect:

```bat
scripts\postgres-connect.bat -c "SELECT version();"
```

## Paths

| Item | Path |
|------|------|
| Binaries | `PG_INSTALL\bin` |
| Data directory | `data` (e.g. `D:\dev\postgresql-portable\data` when `PG_DATA=data`) |
| Startup log | `data\log\startup.log` |

## Project layout

```
postgresql-portable/
├── .env                   # local config (gitignored)
├── data/                  # database cluster (gitignored, created by init)
├── pyproject.toml         # package metadata and dependencies
├── scripts/               # Windows batch helpers ({group}-{verb}.bat)
│   ├── pg-setup.bat       # venv + editable install
│   ├── pg-info.bat        # paths and .env (server may be off)
│   ├── postgres-*.bat     # server lifecycle
│   └── winccoa-*.bat      # WinCC OA database
├── src/
│   └── postgresql_portable/   # Python package (CLI)
└── tests/
```

## Python CLI (alternative)

Operational batch scripts call `python -m postgresql_portable` under the hood. Equivalent commands:

| Batch | Python | Notes |
|-------|--------|-------|
| `scripts\postgres-init.bat` | `python -m postgresql_portable init` |
| `scripts\postgres-start.bat` | `python -m postgresql_portable start` |
| `scripts\postgres-stop.bat` | `python -m postgresql_portable stop` |
| `scripts\postgres-restart.bat` | `python -m postgresql_portable restart` |
| `scripts\postgres-status.bat` | `python -m postgresql_portable status` | Server, databases, cluster info |
| `scripts\postgres-connect.bat` | `python -m postgresql_portable connect` |
| `scripts\pg-info.bat` | `python -m postgresql_portable info` | `PG_*` paths and settings (server may be off) |
| `scripts\winccoa-create.bat` | `python -m postgresql_portable create-winccoa` |
| `scripts\winccoa-drop.bat` | `python -m postgresql_portable drop-winccoa --yes` |
| `scripts\pg-setup.bat` | (venv + `pip install -e .`) | First-time environment setup |

You can also use the console script after install: `postgresql-portable info`.

Manual setup without batch scripts:

```powershell
cd D:\dev\postgresql-portable
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -m postgresql_portable info
```

## Troubleshooting

- **Missing `.env`** — copy `.env.example` to `.env` and set `PG_INSTALL`.
- **WinCC OA script fails auth** — set `PG_PASSWORD` in `.env` to the `postgres` superuser password.
- **`pg-setup.bat` permission denied on `.venv`** — `.venv` already exists (often while activated). Setup now reuses it; or deactivate, delete `.venv`, and run setup again for a fresh env.
- **Data not initialized** — run `scripts\postgres-init.bat` before start.
- **`postgres-init.bat`: directory not empty** — delete or empty `data\` (e.g. `Remove-Item -Recurse -Force data`) and run init again. Do not create `data\log\` manually before init.
- **Port 5432 in use** — stop other PostgreSQL instances or change `port` in `data\postgresql.conf`.
- **Start fails** — read `data\log\startup.log`.
- **Upgrade PostgreSQL** — extract a new version folder, update `PG_INSTALL` in `.env`; keep `PG_DATA` and run `pg_upgrade` if needed.

Custom env file:

```powershell
$env:PG_ENV_FILE = "D:\other\.env"
python -m postgresql_portable info
```

## Tests

```powershell
pip install -e .
pytest
```

Tests use temporary directories and mocked subprocess calls — no running PostgreSQL required.
