from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class PgConfig:
    install: Path
    bin_dir: Path
    data_dir: Path
    user: str
    database: str

    @property
    def initdb(self) -> Path:
        return self.bin_dir / "initdb.exe"

    @property
    def pg_ctl(self) -> Path:
        return self.bin_dir / "pg_ctl.exe"

    @property
    def psql(self) -> Path:
        return self.bin_dir / "psql.exe"

    @property
    def startup_log(self) -> Path:
        return self.data_dir / "log" / "startup.log"

    def is_initialized(self) -> bool:
        return (self.data_dir / "PG_VERSION").is_file()


def load_config() -> PgConfig:
    env_file = os.environ.get("PG_ENV_FILE")
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv(ROOT / ".env")

    install = os.environ.get("PG_INSTALL", "").strip()
    data_dir = os.environ.get("PG_DATA", "").strip() or str(DEFAULT_DATA_DIR)

    if not install:
        sys.exit("PG_INSTALL is not set. Copy .env.example to .env and configure paths.")

    install_path = Path(install)
    if not install_path.is_absolute():
        install_path = (ROOT / install_path).resolve()
    else:
        install_path = install_path.resolve()

    bin_dir = Path(os.environ.get("PG_BIN", install_path / "bin"))
    if not bin_dir.is_absolute():
        bin_dir = (install_path / bin_dir).resolve()
    else:
        bin_dir = bin_dir.resolve()

    data_path = Path(data_dir)
    if not data_path.is_absolute():
        data_path = (ROOT / data_path).resolve()
    else:
        data_path = data_path.resolve()
    user = os.environ.get("PG_USER", "postgres").strip() or "postgres"
    database = os.environ.get("PG_DATABASE", "postgres").strip() or "postgres"

    return PgConfig(
        install=install_path,
        bin_dir=bin_dir,
        data_dir=data_path,
        user=user,
        database=database,
    )


def ensure_binary(path: Path, name: str) -> None:
    if not path.is_file():
        sys.exit(f"{name} not found: {path}")
