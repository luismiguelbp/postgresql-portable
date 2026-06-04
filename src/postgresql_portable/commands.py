from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from postgresql_portable.config import PgConfig, ensure_binary

INIT_ENCODING = "UTF8"
INIT_LOCALE = "English_United States.1252"


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result


def _admin_env() -> dict[str, str]:
    env = os.environ.copy()
    admin_password = os.environ.get("PG_PASSWORD", "").strip()
    if admin_password:
        env["PGPASSWORD"] = admin_password
    return env


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_winccoa_env_summary() -> None:
    username = os.environ.get("WINCCOA_USERNAME", "").strip()
    database = os.environ.get("WINCCOA_DATABASE", "").strip()
    schema_dir = os.environ.get("WINCCOA_SCHEMA", "").strip()
    version = os.environ.get("WINCCOA_VERSION", "").strip()
    if not username and not database and not schema_dir and not version:
        return
    _print_section("WinCC OA (.env)")
    if version:
        print(f"  version  = {version}")
    if username:
        print(f"  user     = {username}")
    if database:
        print(f"  database = {database}")
    if schema_dir:
        print(f"  nga_sql  = {schema_dir}")


def _capture(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=_admin_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def _psql_scalar(cfg: PgConfig, sql: str) -> str | None:
    result = _capture(
        [str(cfg.psql), "-U", cfg.user, "-d", "postgres", "-tAc", sql],
        cwd=cfg.bin_dir,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _server_is_ready(cfg: PgConfig) -> bool:
    pg_isready = cfg.bin_dir / "pg_isready.exe"
    if not pg_isready.is_file():
        return False
    result = _capture(
        [str(pg_isready), "-U", cfg.user, "-d", "postgres"],
        cwd=cfg.bin_dir,
    )
    return result.returncode == 0


def _ensure_empty_data_dir(data_dir: Path) -> None:
    if not data_dir.exists():
        return
    if any(data_dir.iterdir()):
        sys.exit(
            f"Data directory exists but is not empty: {data_dir}\n"
            "Remove or empty it, then run init again."
        )


def cmd_init(cfg: PgConfig) -> None:
    ensure_binary(cfg.initdb, "initdb")

    if cfg.is_initialized():
        sys.exit(f"Data directory already initialized: {cfg.data_dir}")

    _ensure_empty_data_dir(cfg.data_dir)

    _run(
        [
            str(cfg.initdb),
            "-D",
            str(cfg.data_dir),
            "-U",
            cfg.user,
            "-E",
            INIT_ENCODING,
            "--locale",
            INIT_LOCALE,
            "-A",
            "scram-sha-256",
            "-W",
        ],
        cwd=cfg.bin_dir,
    )
    print("\nSuccess. Run: python -m postgresql_portable start")


def cmd_start(cfg: PgConfig) -> None:
    ensure_binary(cfg.pg_ctl, "pg_ctl")

    if not cfg.is_initialized():
        sys.exit("Data directory not initialized. Run: python -m postgresql_portable init")

    (cfg.data_dir / "log").mkdir(parents=True, exist_ok=True)

    _run(
        [
            str(cfg.pg_ctl),
            "-D",
            str(cfg.data_dir),
            "-l",
            str(cfg.startup_log),
            "start",
        ],
        cwd=cfg.bin_dir,
    )
    _run([str(cfg.pg_ctl), "-D", str(cfg.data_dir), "status"], cwd=cfg.bin_dir)
    print("\nRun scripts\\postgres-status.bat for databases and cluster details.")


def cmd_stop(cfg: PgConfig) -> None:
    ensure_binary(cfg.pg_ctl, "pg_ctl")
    _run([str(cfg.pg_ctl), "-D", str(cfg.data_dir), "stop"], cwd=cfg.bin_dir)


def cmd_restart(cfg: PgConfig) -> None:
    ensure_binary(cfg.pg_ctl, "pg_ctl")
    _run([str(cfg.pg_ctl), "-D", str(cfg.data_dir), "restart"], cwd=cfg.bin_dir)


def cmd_status(cfg: PgConfig) -> None:
    ensure_binary(cfg.pg_ctl, "pg_ctl")

    _print_section("Config")
    print(f"initialized = {cfg.is_initialized()}")
    print(f"PG_DATA     = {cfg.data_dir}")
    print(f"PG_USER     = {cfg.user}")

    if not cfg.is_initialized():
        print("\nCluster not initialized. Run: scripts\\postgres-init.bat")
        _print_winccoa_env_summary()
        return

    _print_section("Server")
    ctl = _capture(
        [str(cfg.pg_ctl), "-D", str(cfg.data_dir), "status"],
        cwd=cfg.bin_dir,
    )
    ctl_output = "\n".join(part for part in (ctl.stdout.strip(), ctl.stderr.strip()) if part)
    if ctl_output:
        print(ctl_output)

    if _server_is_ready(cfg):
        print("pg_isready: accepting connections")
    else:
        print("pg_isready: not accepting connections")
        print("\nServer is not ready. Run: scripts\\postgres-start.bat")
        _print_winccoa_env_summary()
        return

    ensure_binary(cfg.psql, "psql")

    _print_section("Cluster")
    version = _psql_scalar(cfg, "SELECT version()")
    encoding = _psql_scalar(cfg, "SHOW server_encoding")
    collate = _psql_scalar(cfg, "SHOW lc_collate")
    port = _psql_scalar(cfg, "SHOW port")

    if version is None:
        print("Could not query cluster details.")
        print("Set PG_PASSWORD in .env if authentication is required.")
        _print_winccoa_env_summary()
        return

    print(f"version  = {version}")
    if encoding:
        print(f"encoding = {encoding}")
    if collate:
        print(f"lc_collate = {collate}")
    if port:
        print(f"port     = {port}")

    _print_section("Databases")
    databases = _psql_scalar(
        cfg,
        "SELECT datname || ' (owner: ' || pg_get_userbyid(datdba) || ')' "
        "FROM pg_database WHERE datistemplate = false ORDER BY datname",
    )
    if databases:
        for line in databases.splitlines():
            print(f"  {line}")
    else:
        print("  (none found)")

    _print_winccoa_env_summary()


def cmd_connect(cfg: PgConfig, extra_args: list[str]) -> None:
    ensure_binary(cfg.psql, "psql")
    cmd = [str(cfg.psql), "-U", cfg.user, "-d", cfg.database, *extra_args]
    sys.exit(subprocess.call(cmd, cwd=cfg.bin_dir, env=_admin_env()))


def cmd_info(cfg: PgConfig) -> None:
    print(f"PG_INSTALL  = {cfg.install}")
    print(f"PG_BIN      = {cfg.bin_dir}")
    print(f"PG_DATA     = {cfg.data_dir}")
    print(f"PG_USER     = {cfg.user}")
    print(f"PG_DATABASE = {cfg.database}")
    print(f"initialized = {cfg.is_initialized()}")
    print(f"psql        = {cfg.psql}")
    print(f"pg_ctl      = {cfg.pg_ctl}")
    print(f"initdb      = {cfg.initdb}")
