import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_cli_info(pg_layout):
    env = os.environ.copy()
    env["PG_ENV_FILE"] = str(pg_layout["env_file"])

    result = subprocess.run(
        [sys.executable, "-m", "postgresql_portable", "info"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "testuser" in result.stdout
    assert "testdb" in result.stdout
    assert str(pg_layout["data_dir"]) in result.stdout


def test_cli_requires_command(pg_layout):
    env = os.environ.copy()
    env["PG_ENV_FILE"] = str(pg_layout["env_file"])

    result = subprocess.run(
        [sys.executable, "-m", "postgresql_portable"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "required" in result.stderr.lower()
