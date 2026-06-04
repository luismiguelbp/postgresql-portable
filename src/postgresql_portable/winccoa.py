from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from postgresql_portable.config import PgConfig, ROOT, ensure_binary

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_DEFAULT_TABLESPACE_ROOT = ROOT / "data_winccoa_tablespaces"
_DEFAULT_PG_SCHEMA = "winccoa"
_SUPPORTED_VERSIONS = ("3.19", "3.20", "3.21")
WinCCOAVersion = Literal["3.19", "3.20", "3.21"]
_PATH_VERSION_RE = re.compile(r"3\.(19|20|21)")
_PORTABLE_SCHEMA_SCRIPT = "_postgresql_portable_schema.sql"


@dataclass(frozen=True)
class TablespaceNames:
    db: str
    events: str
    alerts: str


@dataclass(frozen=True)
class WinCCOAConfig:
    username: str
    password: str
    database: str
    version: WinCCOAVersion
    schema_sql_dir: Path
    pg_schema: str
    db_host: str
    db_port: str
    force_recreate: bool
    tablespace_names: TablespaceNames


def load_winccoa_config(*, require_password: bool = True) -> WinCCOAConfig:
    username = os.environ.get("WINCCOA_USERNAME", "").strip()
    password = os.environ.get("WINCCOA_PASSWORD", "").strip()
    database = os.environ.get("WINCCOA_DATABASE", "").strip()

    required = [
        ("WINCCOA_USERNAME", username),
        ("WINCCOA_DATABASE", database),
        ("WINCCOA_SCHEMA", os.environ.get("WINCCOA_SCHEMA", "").strip()),
        ("WINCCOA_VERSION", os.environ.get("WINCCOA_VERSION", "").strip()),
    ]
    if require_password:
        required.append(("WINCCOA_PASSWORD", password))

    missing = [name for name, value in required if not value]
    if missing:
        sys.exit(f"Missing in .env: {', '.join(missing)}")

    version = _parse_winccoa_version(os.environ["WINCCOA_VERSION"].strip())
    schema_dir = _load_schema_sql_dir()
    _validate_version_matches_path(version, schema_dir)
    _validate_schema_fingerprint(version, schema_dir)

    pg_schema = os.environ.get("WINCCOA_PG_SCHEMA", _DEFAULT_PG_SCHEMA).strip() or _DEFAULT_PG_SCHEMA
    db_host = os.environ.get("WINCCOA_DB_HOST", "localhost").strip() or "localhost"
    db_port = os.environ.get("WINCCOA_DB_PORT", "5432").strip() or "5432"
    force_recreate = os.environ.get("WINCCOA_FORCE_RECREATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    tablespace_names = _load_tablespace_names()

    return WinCCOAConfig(
        username=_validate_identifier(username, "WINCCOA_USERNAME"),
        password=password,
        database=_validate_identifier(database, "WINCCOA_DATABASE"),
        version=version,
        schema_sql_dir=schema_dir,
        pg_schema=_validate_identifier(pg_schema, "WINCCOA_PG_SCHEMA"),
        db_host=db_host,
        db_port=db_port,
        force_recreate=force_recreate,
        tablespace_names=tablespace_names,
    )


def _parse_winccoa_version(raw: str) -> WinCCOAVersion:
    if raw not in _SUPPORTED_VERSIONS:
        sys.exit(
            f"WINCCOA_VERSION must be one of {', '.join(_SUPPORTED_VERSIONS)}: {raw!r}"
        )
    return raw  # type: ignore[return-value]


def _load_schema_sql_dir() -> Path:
    raw = os.environ.get("WINCCOA_SCHEMA", "").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.is_dir():
        sys.exit(f"WINCCOA_SCHEMA is not a directory: {path}")
    schema_sql = path / "schema.sql"
    if not schema_sql.is_file():
        sys.exit(f"schema.sql not found under WINCCOA_SCHEMA: {schema_sql}")
    return path


def _versions_in_path(path: Path) -> set[str]:
    return {f"3.{match}" for match in _PATH_VERSION_RE.findall(path.as_posix())}


def _validate_version_matches_path(version: WinCCOAVersion, schema_dir: Path) -> None:
    found = _versions_in_path(schema_dir)
    if len(found) > 1:
        sys.exit(
            "WINCCOA_SCHEMA path contains multiple WinCC OA version segments "
            f"({', '.join(sorted(found))}). Use a single-version path."
        )
    if found and version not in found:
        path_version = next(iter(found))
        sys.exit(
            f"WINCCOA_VERSION={version} but WINCCOA_SCHEMA path contains {path_version}:\n"
            f"  {schema_dir}\n"
            "Fix WINCCOA_VERSION or WINCCOA_SCHEMA so they match."
        )


def _validate_schema_fingerprint(version: WinCCOAVersion, schema_dir: Path) -> None:
    schema_text = (schema_dir / "schema.sql").read_text(encoding="utf-8", errors="replace")
    uses_config_include = r"\ir config.sql" in schema_text
    uses_tablespaces = "CREATE TABLESPACE" in schema_text
    db_version_30 = "('dbVersion', '3.0')" in schema_text
    db_version_20 = "('dbVersion', '2.0')" in schema_text

    if version == "3.19":
        if uses_config_include:
            sys.exit(
                "WINCCOA_VERSION=3.19 but schema.sql includes config.sql (3.20+ layout). "
                "Check WINCCOA_SCHEMA or set WINCCOA_VERSION=3.20 or 3.21."
            )
        if not uses_tablespaces:
            sys.exit(
                "WINCCOA_VERSION=3.19 but schema.sql does not create tablespaces. "
                "Check WINCCOA_SCHEMA points at a 3.19 NGA sql folder."
            )
        return

    if not uses_config_include:
        sys.exit(
            f"WINCCOA_VERSION={version} but schema.sql does not include config.sql "
            "(expected 3.20+ layout). Check WINCCOA_SCHEMA."
        )
    if version == "3.21":
        if not db_version_30:
            sys.exit(
                "WINCCOA_VERSION=3.21 but schema.sql does not set dbVersion 3.0. "
                "Check WINCCOA_SCHEMA points at a 3.21 NGA sql folder."
            )
    elif version == "3.20":
        if db_version_30:
            sys.exit(
                "WINCCOA_VERSION=3.20 but schema.sql sets dbVersion 3.0 (3.21). "
                "Set WINCCOA_VERSION=3.21 or use a 3.20 sql folder."
            )
        if not db_version_20:
            sys.exit(
                "WINCCOA_VERSION=3.20 but schema.sql does not set dbVersion 2.0. "
                "Check WINCCOA_SCHEMA."
            )


def _uses_tablespaces(version: WinCCOAVersion) -> bool:
    return version == "3.19"


def _schema_sql_without_config_include(schema_dir: Path) -> str:
    lines = (schema_dir / "schema.sql").read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped in ("-- read configuration", r"\ir config.sql"):
            continue
        out.append(line)
    return "\n".join(out).rstrip() + "\n"


def _modern_schema_script_path(schema_dir: Path) -> Path:
    path = schema_dir / _PORTABLE_SCHEMA_SCRIPT
    path.write_text(_schema_sql_without_config_include(schema_dir), encoding="utf-8")
    return path


def _load_tablespace_names() -> TablespaceNames:
    names = TablespaceNames(
        db=os.environ.get("WINCCOA_TABLESPACE_NAME", "winccoa").strip() or "winccoa",
        events=os.environ.get("WINCCOA_EVENTS_TABLESPACE_NAME", "winccoa_events").strip()
        or "winccoa_events",
        alerts=os.environ.get("WINCCOA_ALERTS_TABLESPACE_NAME", "winccoa_alerts").strip()
        or "winccoa_alerts",
    )
    for label, value in (
        ("WINCCOA_TABLESPACE_NAME", names.db),
        ("WINCCOA_EVENTS_TABLESPACE_NAME", names.events),
        ("WINCCOA_ALERTS_TABLESPACE_NAME", names.alerts),
    ):
        _validate_identifier(value, label)
    return names


def _validate_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        sys.exit(f"{label} must be a valid PostgreSQL identifier: {value!r}")
    return value


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _psql_env() -> dict[str, str]:
    env = os.environ.copy()
    admin_password = os.environ.get("PG_PASSWORD", "").strip()
    if admin_password:
        env["PGPASSWORD"] = admin_password
    return env


def _connection_args(wc: WinCCOAConfig) -> list[str]:
    return ["-h", wc.db_host, "-p", wc.db_port]


def _run_psql(
    cfg: PgConfig,
    wc: WinCCOAConfig,
    *,
    database: str,
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(cfg.psql),
        "-U",
        cfg.user,
        *_connection_args(wc),
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        *args,
    ]
    result = subprocess.run(
        cmd,
        cwd=cwd or cfg.bin_dir,
        env=_psql_env(),
        check=False,
    )
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def _psql_scalar(
    cfg: PgConfig,
    wc: WinCCOAConfig,
    sql: str,
    *,
    database: str = "postgres",
    optional: bool = False,
) -> str:
    result = subprocess.run(
        [
            str(cfg.psql),
            "-U",
            cfg.user,
            *_connection_args(wc),
            "-d",
            database,
            "-tAc",
            sql,
        ],
        cwd=cfg.bin_dir,
        env=_psql_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if optional:
            return ""
        message = result.stderr.strip() or result.stdout.strip() or "psql query failed"
        sys.exit(message)
    return result.stdout.strip()


def _tablespace_paths() -> dict[str, Path]:
    root_raw = os.environ.get("WINCCOA_TABLESPACE_ROOT", "").strip()
    base = Path(root_raw) if root_raw else _DEFAULT_TABLESPACE_ROOT
    if not base.is_absolute():
        base = (ROOT / base).resolve()
    else:
        base = base.resolve()

    keys = ("db", "events", "alerts", "backups")
    env_names = {
        "db": "WINCCOA_TABLESPACE_DB",
        "events": "WINCCOA_TABLESPACE_EVENTS",
        "alerts": "WINCCOA_TABLESPACE_ALERTS",
        "backups": "WINCCOA_TABLESPACE_BACKUPS",
    }
    paths: dict[str, Path] = {}
    for key in keys:
        override = os.environ.get(env_names[key], "").strip()
        paths[key] = Path(override) if override else base / key
        if not paths[key].is_absolute():
            paths[key] = (ROOT / paths[key]).resolve()
    return paths


def _posix_path(path: Path) -> str:
    return path.as_posix()


def _ensure_tablespace_dirs(paths: dict[str, Path]) -> None:
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        print(f"  tablespace {name}: {path}")


def _nga_schema_present(cfg: PgConfig, wc: WinCCOAConfig) -> bool:
    if not _psql_scalar(
        cfg,
        wc,
        f"SELECT 1 FROM pg_database WHERE datname = '{wc.database}'",
        optional=True,
    ):
        return False
    return bool(
        _psql_scalar(
            cfg,
            wc,
            f"SELECT 1 FROM {wc.pg_schema}.configuration WHERE name = 'dbVersion' LIMIT 1",
            database=wc.database,
            optional=True,
        )
    )


def _terminate_db_connections(cfg: PgConfig, wc: WinCCOAConfig) -> None:
    _run_psql(
        cfg,
        wc,
        database="postgres",
        args=[
            "-c",
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{wc.database}' AND pid <> pg_backend_pid();",
        ],
        check=False,
    )


def _psql_var_args(psql_vars: list[tuple[str, str]]) -> list[str]:
    args: list[str] = []
    for key, value in psql_vars:
        args.extend(["-v", f"{key}={value}"])
    return args


def _build_psql_vars_319(
    cfg: PgConfig,
    wc: WinCCOAConfig,
    tablespaces: dict[str, Path],
) -> list[tuple[str, str]]:
    password_var = wc.password.replace('"', '\\"')
    return [
        ("numberType", "DOUBLE PRECISION"),
        ("useBtreeIndexesForSegments", "FALSE"),
        ("useAdditionalBtreeIndexWithBrinForSegments", "TRUE"),
        ("dbName", wc.database),
        ("adminUsername", cfg.user),
        ("dbTableSpaceName", wc.tablespace_names.db),
        ("dbPath", _posix_path(tablespaces["db"])),
        ("dbEventsPath", _posix_path(tablespaces["events"])),
        ("dbAlertsPath", _posix_path(tablespaces["alerts"])),
        ("dbBackupPath", _posix_path(tablespaces["backups"])),
        ("dbEventsTableSpaceName", wc.tablespace_names.events),
        ("dbAlertsTableSpaceName", wc.tablespace_names.alerts),
        ("winccoaUsername", wc.username),
        ("winccoaPassword", password_var),
        ("dbSchema", wc.pg_schema),
    ]


def _build_psql_vars_modern(wc: WinCCOAConfig) -> list[tuple[str, str]]:
    password_var = wc.password.replace('"', '\\"')
    return [
        ("numberType", "DOUBLE PRECISION"),
        ("UseBtreeIndexForSimpleValueTypes", "FALSE"),
        ("useAdditionalBtreeIndexWithBrinForSegments", "TRUE"),
        ("dbName", wc.database),
        ("winccoaUsername", wc.username),
        ("winccoaPassword", password_var),
        ("dbSchema", wc.pg_schema),
    ]


def _apply_nga_schema(cfg: PgConfig, wc: WinCCOAConfig) -> None:
    if not os.environ.get("PG_PASSWORD", "").strip():
        sys.exit("PG_PASSWORD is required in .env for WinCC OA NGA schema (postgres admin).")

    schema_dir = wc.schema_sql_dir

    if _nga_schema_present(cfg, wc) and not wc.force_recreate:
        version = _psql_scalar(
            cfg,
            wc,
            f"SELECT value FROM {wc.pg_schema}.configuration WHERE name = 'dbVersion'",
            database=wc.database,
        )
        print(f"NGA schema already present (dbVersion={version}).")
        print("Set WINCCOA_FORCE_RECREATE=yes to drop and recreate the database.")
        _print_ready(wc)
        return

    if _nga_schema_present(cfg, wc) and wc.force_recreate:
        print("WINCCOA_FORCE_RECREATE=yes: recreating NGA database and schema.")

    print(f"Applying WinCC OA NGA schema (WINCCOA_VERSION={wc.version}) from:")
    if _uses_tablespaces(wc.version):
        print(f"  {schema_dir / 'schema.sql'}")
        print("Tablespace directories:")
        tablespaces = _tablespace_paths()
        _ensure_tablespace_dirs(tablespaces)
        schema_file = schema_dir / "schema.sql"
        psql_vars = _build_psql_vars_319(cfg, wc, tablespaces)
        drop_message = "Running schema.sql (existing NGA database will be dropped)..."
    else:
        schema_file = _modern_schema_script_path(schema_dir)
        print(f"  {schema_file}")
        print("  (config.sql skipped; credentials from .env)")
        psql_vars = _build_psql_vars_modern(wc)
        drop_message = "Running schema.sql (existing database dropped first if present)..."

    _terminate_db_connections(cfg, wc)

    if not _uses_tablespaces(wc.version) and _object_exists(
        cfg,
        wc,
        f"SELECT 1 FROM pg_database WHERE datname = '{wc.database}'",
    ):
        _drop_database(cfg, wc)

    args: list[str] = ["-f", str(schema_file), *_psql_var_args(psql_vars)]

    print()
    print(drop_message)
    result = subprocess.run(
        [
            str(cfg.psql),
            "-U",
            cfg.user,
            *_connection_args(wc),
            *args,
        ],
        cwd=schema_dir,
        env=_psql_env(),
        check=False,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    version = _psql_scalar(
        cfg,
        wc,
        f"SELECT value FROM {wc.pg_schema}.configuration WHERE name = 'dbVersion'",
        database=wc.database,
    )
    print(f"NGA schema applied (dbVersion={version}).")
    _print_ready(wc)


def _print_ready(wc: WinCCOAConfig) -> None:
    print()
    print("WinCC OA database ready.")
    print(f"  version   = {wc.version}")
    print(f"  database  = {wc.database}")
    print(f"  user      = {wc.username}")
    print(f"  host      = {wc.db_host}")
    print(f"  port      = {wc.db_port}")
    print(f"  pg_schema = {wc.pg_schema}")


def _drop_confirmed(*, assume_yes: bool) -> None:
    if assume_yes:
        return
    if os.environ.get("WINCCOA_CONFIRM", "").strip().lower() in ("1", "true", "yes"):
        return
    sys.exit(
        "Refusing to drop WinCC OA database. "
        "Pass --yes or set WINCCOA_CONFIRM=yes in .env."
    )


def _object_exists(cfg: PgConfig, wc: WinCCOAConfig, sql: str) -> bool:
    return bool(_psql_scalar(cfg, wc, sql, optional=True))


def _drop_database(cfg: PgConfig, wc: WinCCOAConfig) -> None:
    if not _object_exists(
        cfg,
        wc,
        f"SELECT 1 FROM pg_database WHERE datname = '{wc.database}'",
    ):
        print(f"Database not found: {wc.database}")
        return

    print(f"Dropping database: {wc.database}")
    _terminate_db_connections(cfg, wc)
    _run_psql(
        cfg,
        wc,
        database="postgres",
        args=["-c", f"DROP DATABASE {wc.database}"],
    )


def _drop_tablespace(cfg: PgConfig, wc: WinCCOAConfig, name: str) -> None:
    if not _object_exists(
        cfg,
        wc,
        f"SELECT 1 FROM pg_tablespace WHERE spcname = '{name}'",
    ):
        print(f"Tablespace not found: {name}")
        return

    print(f"Dropping tablespace: {name}")
    _run_psql(
        cfg,
        wc,
        database="postgres",
        args=["-c", f"DROP TABLESPACE {name}"],
    )


def _drop_role(cfg: PgConfig, wc: WinCCOAConfig) -> None:
    if not _object_exists(cfg, wc, f"SELECT 1 FROM pg_roles WHERE rolname = '{wc.username}'"):
        print(f"Role not found: {wc.username}")
        return

    print(f"Dropping role: {wc.username}")
    _run_psql(
        cfg,
        wc,
        database="postgres",
        args=[
            "-c",
            f"REASSIGN OWNED BY {wc.username} TO {cfg.user}",
            "-c",
            f"DROP OWNED BY {wc.username}",
            "-c",
            f"DROP ROLE {wc.username}",
        ],
    )


def _remove_tablespace_dirs() -> None:
    paths = _tablespace_paths()
    for name, path in paths.items():
        if not path.exists():
            continue
        print(f"Removing directory: {path}")
        for child in sorted(path.iterdir(), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
        try:
            path.rmdir()
        except OSError:
            print(f"  (directory not empty, left on disk: {path})")


def cmd_drop_winccoa(
    cfg: PgConfig,
    *,
    assume_yes: bool = False,
    drop_user: bool = False,
    remove_data: bool = False,
) -> None:
    ensure_binary(cfg.psql, "psql")

    if not cfg.is_initialized():
        sys.exit("Data directory not initialized. Run: scripts\\postgres-init.bat")

    if not os.environ.get("PG_PASSWORD", "").strip():
        sys.exit("PG_PASSWORD is required in .env (postgres admin).")

    _drop_confirmed(assume_yes=assume_yes)

    wc = load_winccoa_config(require_password=False)

    print("Removing WinCC OA database configuration:")
    print(f"  version  = {wc.version}")
    print(f"  database = {wc.database}")
    print(f"  user     = {wc.username}")

    _drop_database(cfg, wc)

    if _uses_tablespaces(wc.version):
        for tablespace in (
            wc.tablespace_names.db,
            wc.tablespace_names.events,
            wc.tablespace_names.alerts,
        ):
            _drop_tablespace(cfg, wc, tablespace)

    env_drop_user = os.environ.get("WINCCOA_DROP_USER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if drop_user or env_drop_user:
        _drop_role(cfg, wc)

    if remove_data and _uses_tablespaces(wc.version):
        _remove_tablespace_dirs()

    print()
    print("WinCC OA database removed.")


def cmd_create_winccoa(cfg: PgConfig) -> None:
    ensure_binary(cfg.psql, "psql")

    if not cfg.is_initialized():
        sys.exit("Data directory not initialized. Run: scripts\\postgres-init.bat")

    if not os.environ.get("PG_PASSWORD", "").strip():
        sys.exit("PG_PASSWORD is required in .env (postgres admin).")

    wc = load_winccoa_config()
    _apply_nga_schema(cfg, wc)
