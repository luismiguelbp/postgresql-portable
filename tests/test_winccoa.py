from pathlib import Path
from unittest.mock import patch

import pytest

from postgresql_portable.winccoa import (
    TablespaceNames,
    WinCCOAConfig,
    _schema_sql_without_config_include,
    _validate_schema_fingerprint,
    _validate_version_matches_path,
    cmd_create_winccoa,
    cmd_drop_winccoa,
    load_winccoa_config,
)


def _write_schema_319(schema_dir: Path) -> None:
    (schema_dir / "schema.sql").write_text(
        "DROP TABLESPACE IF EXISTS winccoa;\n"
        "CREATE TABLESPACE winccoa LOCATION 'd:/db';\n"
        "INSERT INTO configuration VALUES ('dbVersion', '2.0');\n",
        encoding="utf-8",
    )


def _write_schema_320(schema_dir: Path) -> None:
    (schema_dir / "config.sql").write_text(
        "\\set winccoaUsername 'winccoa'\n",
        encoding="utf-8",
    )
    (schema_dir / "schema.sql").write_text(
        "-- read configuration\n"
        "\\ir config.sql\n"
        "INSERT INTO configuration VALUES ('dbVersion', '2.0');\n",
        encoding="utf-8",
    )


def _write_schema_321(schema_dir: Path) -> None:
    (schema_dir / "config.sql").write_text(
        "\\set winccoaUsername 'winccoa'\n",
        encoding="utf-8",
    )
    (schema_dir / "schema.sql").write_text(
        "-- read configuration\n"
        "\\ir config.sql\n"
        "INSERT INTO configuration VALUES ('dbVersion', '3.0');\n",
        encoding="utf-8",
    )


def _set_required_winccoa_env(
    monkeypatch,
    *,
    schema_dir: Path,
    version: str = "3.19",
) -> None:
    monkeypatch.setenv("WINCCOA_USERNAME", "winccoa")
    monkeypatch.setenv("WINCCOA_PASSWORD", "secret")
    monkeypatch.setenv("WINCCOA_DATABASE", "winccoa")
    monkeypatch.setenv("WINCCOA_SCHEMA", str(schema_dir))
    monkeypatch.setenv("WINCCOA_VERSION", version)


@pytest.fixture
def schema_dir_319(tmp_path: Path) -> Path:
    path = tmp_path / "nga_sql"
    path.mkdir()
    _write_schema_319(path)
    return path


def test_load_winccoa_config(schema_dir_319, monkeypatch):
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")

    wc = load_winccoa_config()

    assert wc == WinCCOAConfig(
        username="winccoa",
        password="secret",
        database="winccoa",
        version="3.19",
        schema_sql_dir=schema_dir_319.resolve(),
        pg_schema="winccoa",
        db_host="localhost",
        db_port="5432",
        force_recreate=False,
        tablespace_names=TablespaceNames(
            db="winccoa",
            events="winccoa_events",
            alerts="winccoa_alerts",
        ),
    )


def test_load_winccoa_config_with_schema_dir(schema_dir_319, monkeypatch):
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")

    wc = load_winccoa_config()

    assert wc.schema_sql_dir == schema_dir_319.resolve()
    assert wc.version == "3.19"


def test_load_winccoa_config_missing_schema_sql(monkeypatch, tmp_path):
    schema_dir = tmp_path / "empty"
    schema_dir.mkdir()
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir, version="3.19")

    with pytest.raises(SystemExit, match="schema.sql not found"):
        load_winccoa_config()


def test_load_winccoa_config_missing(monkeypatch):
    monkeypatch.delenv("WINCCOA_USERNAME", raising=False)
    monkeypatch.delenv("WINCCOA_PASSWORD", raising=False)
    monkeypatch.delenv("WINCCOA_DATABASE", raising=False)
    monkeypatch.delenv("WINCCOA_SCHEMA", raising=False)
    monkeypatch.delenv("WINCCOA_VERSION", raising=False)

    with pytest.raises(SystemExit, match="Missing in .env"):
        load_winccoa_config()


def test_load_winccoa_config_invalid_version(schema_dir_319, monkeypatch):
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.18")

    with pytest.raises(SystemExit, match="WINCCOA_VERSION must be one of"):
        load_winccoa_config()


def test_load_winccoa_config_version_path_mismatch(schema_dir_319, monkeypatch):
    path = Path(r"C:\Siemens\Automation\WinCC_OA\3.20\data\NGA\PostgreSQL\sql")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")

    with patch(
        "postgresql_portable.winccoa._load_schema_sql_dir",
        return_value=path.resolve(),
    ):
        with pytest.raises(SystemExit, match="WINCCOA_VERSION=3.19"):
            load_winccoa_config()


def test_load_winccoa_config_fingerprint_321_on_319_dir(schema_dir_319, monkeypatch):
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.21")

    with pytest.raises(SystemExit, match="WINCCOA_VERSION=3.21"):
        load_winccoa_config()


def test_load_winccoa_config_invalid_identifier(schema_dir_319, monkeypatch):
    monkeypatch.setenv("WINCCOA_USERNAME", "bad-user")
    monkeypatch.setenv("WINCCOA_PASSWORD", "secret")
    monkeypatch.setenv("WINCCOA_DATABASE", "winccoa")
    monkeypatch.setenv("WINCCOA_SCHEMA", str(schema_dir_319))
    monkeypatch.setenv("WINCCOA_VERSION", "3.19")

    with pytest.raises(SystemExit, match="WINCCOA_USERNAME"):
        load_winccoa_config()


def test_load_winccoa_config_custom_tablespace_names(schema_dir_319, monkeypatch):
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("WINCCOA_TABLESPACE_NAME", "custom_db")
    monkeypatch.setenv("WINCCOA_EVENTS_TABLESPACE_NAME", "custom_events")
    monkeypatch.setenv("WINCCOA_ALERTS_TABLESPACE_NAME", "custom_alerts")

    wc = load_winccoa_config()

    assert wc.tablespace_names == TablespaceNames(
        db="custom_db",
        events="custom_events",
        alerts="custom_alerts",
    )


def test_schema_sql_without_config_include(tmp_path):
    schema_dir = tmp_path / "sql"
    schema_dir.mkdir()
    (schema_dir / "schema.sql").write_text(
        "-- read configuration\n"
        "\\ir config.sql\n"
        "CREATE DATABASE :dbName;\n",
        encoding="utf-8",
    )

    result = _schema_sql_without_config_include(schema_dir)

    assert "\\ir config.sql" not in result
    assert "CREATE DATABASE" in result


def test_cmd_create_winccoa_applies_nga_schema_319(cfg, monkeypatch, schema_dir_319):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("PG_PASSWORD", "admin")
    monkeypatch.setenv("WINCCOA_TABLESPACE_NAME", "custom_db")
    monkeypatch.setenv("WINCCOA_EVENTS_TABLESPACE_NAME", "custom_events")
    monkeypatch.setenv("WINCCOA_ALERTS_TABLESPACE_NAME", "custom_alerts")

    with patch("postgresql_portable.winccoa._nga_schema_present", return_value=False):
        with patch("postgresql_portable.winccoa._ensure_tablespace_dirs"):
            with patch("postgresql_portable.winccoa._terminate_db_connections"):
                with patch("postgresql_portable.winccoa.subprocess.run") as run:
                    run.return_value.returncode = 0
                    with patch(
                        "postgresql_portable.winccoa._psql_scalar",
                        return_value="2.0",
                    ):
                        cmd_create_winccoa(cfg)

    assert run.call_count == 1
    cmd = run.call_args[0][0]
    assert str(schema_dir_319 / "schema.sql") in cmd
    assert "dbTableSpaceName=custom_db" in cmd
    assert "useBtreeIndexesForSegments=FALSE" in cmd
    assert "winccoaUsername=winccoa" in cmd


def test_cmd_create_winccoa_applies_nga_schema_320(cfg, monkeypatch, tmp_path):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    schema_dir = tmp_path / "nga_320"
    schema_dir.mkdir()
    _write_schema_320(schema_dir)
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir, version="3.20")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._nga_schema_present", return_value=False):
        with patch("postgresql_portable.winccoa._object_exists", return_value=False):
            with patch("postgresql_portable.winccoa._terminate_db_connections"):
                with patch("postgresql_portable.winccoa._drop_database") as drop_db:
                    with patch("postgresql_portable.winccoa.subprocess.run") as run:
                        run.return_value.returncode = 0
                        with patch(
                            "postgresql_portable.winccoa._psql_scalar",
                            return_value="2.0",
                        ):
                            cmd_create_winccoa(cfg)

    drop_db.assert_not_called()
    cmd = run.call_args[0][0]
    assert "_postgresql_portable_schema.sql" in " ".join(cmd)
    assert "UseBtreeIndexForSimpleValueTypes=FALSE" in cmd
    assert "dbTableSpaceName" not in " ".join(cmd)


def test_cmd_create_winccoa_drops_existing_db_on_recreate_320(cfg, monkeypatch, tmp_path):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    schema_dir = tmp_path / "nga_320"
    schema_dir.mkdir()
    _write_schema_320(schema_dir)
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir, version="3.20")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._nga_schema_present", return_value=True):
        with patch("postgresql_portable.winccoa._terminate_db_connections"):
            with patch("postgresql_portable.winccoa._drop_database") as drop_db:
                with patch("postgresql_portable.winccoa._object_exists", return_value=True):
                    with patch("postgresql_portable.winccoa.subprocess.run") as run:
                        run.return_value.returncode = 0
                        with patch(
                            "postgresql_portable.winccoa._psql_scalar",
                            return_value="2.0",
                        ):
                            monkeypatch.setenv("WINCCOA_FORCE_RECREATE", "yes")
                            cmd_create_winccoa(cfg)

    drop_db.assert_called_once()


def test_cmd_create_winccoa_skips_when_nga_present(cfg, monkeypatch, schema_dir_319):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._nga_schema_present", return_value=True):
        with patch("postgresql_portable.winccoa.subprocess.run") as run:
            with patch("postgresql_portable.winccoa._psql_scalar", return_value="2.0"):
                cmd_create_winccoa(cfg)

    run.assert_not_called()


def test_cmd_drop_winccoa_requires_confirmation(cfg, monkeypatch, schema_dir_319):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("PG_PASSWORD", "admin")
    monkeypatch.delenv("WINCCOA_CONFIRM", raising=False)

    with pytest.raises(SystemExit, match="Refusing to drop"):
        cmd_drop_winccoa(cfg)


def test_cmd_drop_winccoa_drops_database(cfg, monkeypatch, schema_dir_319):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._object_exists", return_value=True):
        with patch("postgresql_portable.winccoa._terminate_db_connections") as terminate:
            with patch("postgresql_portable.winccoa._run_psql") as run_psql:
                cmd_drop_winccoa(cfg, assume_yes=True)

    terminate.assert_called_once()
    drop_calls = [c.kwargs["args"][1] for c in run_psql.call_args_list]
    assert any("DROP DATABASE winccoa" in sql for sql in drop_calls)


def test_cmd_drop_winccoa_drops_tablespaces_319(cfg, monkeypatch, schema_dir_319):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir_319, version="3.19")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._object_exists", return_value=True):
        with patch("postgresql_portable.winccoa._terminate_db_connections"):
            with patch("postgresql_portable.winccoa._run_psql") as run_psql:
                cmd_drop_winccoa(cfg, assume_yes=True)

    drop_calls = [c.kwargs["args"][1] for c in run_psql.call_args_list]
    assert any("DROP TABLESPACE winccoa" in sql for sql in drop_calls)
    assert any("DROP TABLESPACE winccoa_events" in sql for sql in drop_calls)
    assert any("DROP TABLESPACE winccoa_alerts" in sql for sql in drop_calls)


def test_cmd_drop_winccoa_skips_tablespaces_320(cfg, monkeypatch, tmp_path):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    schema_dir = tmp_path / "nga_320"
    schema_dir.mkdir()
    _write_schema_320(schema_dir)
    _set_required_winccoa_env(monkeypatch, schema_dir=schema_dir, version="3.20")
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.winccoa._object_exists", return_value=True):
        with patch("postgresql_portable.winccoa._terminate_db_connections"):
            with patch("postgresql_portable.winccoa._run_psql") as run_psql:
                cmd_drop_winccoa(cfg, assume_yes=True)

    drop_calls = [c.kwargs["args"][1] for c in run_psql.call_args_list]
    assert not any("DROP TABLESPACE" in sql for sql in drop_calls)


def test_validate_schema_fingerprint_320_vs_321(tmp_path):
    dir_320 = tmp_path / "v320"
    dir_321 = tmp_path / "v321"
    dir_320.mkdir()
    dir_321.mkdir()
    _write_schema_320(dir_320)
    _write_schema_321(dir_321)

    _validate_schema_fingerprint("3.20", dir_320)
    _validate_schema_fingerprint("3.21", dir_321)

    with pytest.raises(SystemExit, match="dbVersion 3.0"):
        _validate_schema_fingerprint("3.20", dir_321)
