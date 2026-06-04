import pytest

from postgresql_portable.config import PgConfig, load_config


@pytest.fixture
def isolated_env(monkeypatch):
    for key in ("PG_INSTALL", "PG_DATA", "PG_BIN", "PG_USER", "PG_DATABASE"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def pg_layout(tmp_path):
    install = tmp_path / "pgsql"
    bin_dir = install / "bin"
    data_dir = tmp_path / "data"
    bin_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    for name in ("initdb.exe", "pg_ctl.exe", "psql.exe"):
        (bin_dir / name).write_text("")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"PG_INSTALL={install}",
                f"PG_DATA={data_dir}",
                "PG_USER=testuser",
                "PG_DATABASE=testdb",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "env_file": env_file,
        "install": install,
        "bin_dir": bin_dir,
        "data_dir": data_dir,
    }


@pytest.fixture
def cfg(pg_layout):
    return PgConfig(
        install=pg_layout["install"],
        bin_dir=pg_layout["bin_dir"],
        data_dir=pg_layout["data_dir"],
        user="testuser",
        database="testdb",
    )
