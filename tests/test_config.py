import pytest

from postgresql_portable.config import PgConfig, ensure_binary, load_config


def test_load_config_from_env_file(pg_layout, isolated_env, monkeypatch):
    monkeypatch.setenv("PG_ENV_FILE", str(pg_layout["env_file"]))
    monkeypatch.delenv("PG_INSTALL", raising=False)
    monkeypatch.delenv("PG_DATA", raising=False)

    cfg = load_config()

    assert cfg.install == pg_layout["install"]
    assert cfg.bin_dir == pg_layout["bin_dir"]
    assert cfg.data_dir == pg_layout["data_dir"]
    assert cfg.user == "testuser"
    assert cfg.database == "testdb"


def test_load_config_derives_bin_dir(pg_layout, isolated_env, monkeypatch):
    env_file = pg_layout["env_file"]
    env_file.write_text(
        f"PG_INSTALL={pg_layout['install']}\nPG_DATA={pg_layout['data_dir']}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))

    cfg = load_config()

    assert cfg.bin_dir == pg_layout["install"] / "bin"


def test_load_config_custom_bin_dir(pg_layout, isolated_env, monkeypatch):
    custom_bin = pg_layout["install"] / "custom-bin"
    custom_bin.mkdir()
    env_file = pg_layout["env_file"]
    env_file.write_text(
        "\n".join(
            [
                f"PG_INSTALL={pg_layout['install']}",
                f"PG_BIN={custom_bin}",
                f"PG_DATA={pg_layout['data_dir']}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))

    cfg = load_config()

    assert cfg.bin_dir == custom_bin


def test_load_config_resolves_relative_install_and_bin(pg_layout, isolated_env, monkeypatch):
    from postgresql_portable.config import ROOT

    env_file = pg_layout["env_file"]
    env_file.write_text(
        "\n".join(
            [
                "PG_INSTALL=pgsql",
                "PG_BIN=custom-bin",
                f"PG_DATA={pg_layout['data_dir']}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))

    cfg = load_config()

    assert cfg.install == ROOT / "pgsql"
    assert cfg.bin_dir == ROOT / "pgsql" / "custom-bin"


def test_load_config_missing_pg_install(pg_layout, isolated_env, monkeypatch):
    env_file = pg_layout["env_file"]
    env_file.write_text(f"PG_DATA={pg_layout['data_dir']}\n", encoding="utf-8")
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))
    monkeypatch.delenv("PG_INSTALL", raising=False)

    with pytest.raises(SystemExit, match="PG_INSTALL"):
        load_config()


def test_load_config_defaults_data_dir(pg_layout, isolated_env, monkeypatch):
    from postgresql_portable.config import ROOT

    env_file = pg_layout["env_file"]
    env_file.write_text(f"PG_INSTALL={pg_layout['install']}\n", encoding="utf-8")
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))
    monkeypatch.delenv("PG_DATA", raising=False)

    cfg = load_config()

    assert cfg.data_dir == ROOT / "data"


def test_load_config_relative_data_dir(pg_layout, isolated_env, monkeypatch):
    from postgresql_portable.config import ROOT

    env_file = pg_layout["env_file"]
    env_file.write_text(
        f"PG_INSTALL={pg_layout['install']}\nPG_DATA=data\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PG_ENV_FILE", str(env_file))

    cfg = load_config()

    assert cfg.data_dir == ROOT / "data"


def test_pg_config_executable_paths(cfg):
    assert cfg.initdb == cfg.bin_dir / "initdb.exe"
    assert cfg.pg_ctl == cfg.bin_dir / "pg_ctl.exe"
    assert cfg.psql == cfg.bin_dir / "psql.exe"
    assert cfg.startup_log == cfg.data_dir / "log" / "startup.log"


def test_is_initialized_false(cfg):
    assert cfg.is_initialized() is False


def test_is_initialized_true(cfg):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    assert cfg.is_initialized() is True


def test_ensure_binary_missing(cfg):
    missing = cfg.bin_dir / "missing.exe"
    with pytest.raises(SystemExit, match="initdb not found"):
        ensure_binary(missing, "initdb")


def test_ensure_binary_exists(cfg):
    ensure_binary(cfg.initdb, "initdb")
