from unittest.mock import patch

import pytest

from postgresql_portable.commands import cmd_connect, cmd_info, cmd_init, cmd_start, cmd_status, cmd_stop


def test_cmd_init_runs_initdb(cfg):
    with patch("postgresql_portable.commands.subprocess.run") as run:
        run.return_value.returncode = 0
        cmd_init(cfg)

    run.assert_called_once()
    args, kwargs = run.call_args
    assert args[0][0] == str(cfg.initdb)
    assert "-D" in args[0]
    assert str(cfg.data_dir) in args[0]
    assert "-U" in args[0]
    assert cfg.user in args[0]
    assert "-E" in args[0]
    assert "UTF8" in args[0]
    assert "--locale" in args[0]
    assert "English_United States.1252" in args[0]
    assert kwargs["cwd"] == cfg.bin_dir
    assert not (cfg.data_dir / "log").exists()


def test_cmd_init_rejects_non_empty_data_dir(cfg):
    (cfg.data_dir / "log").mkdir(parents=True, exist_ok=True)

    with pytest.raises(SystemExit, match="not empty"):
        cmd_init(cfg)


def test_cmd_init_already_initialized(cfg):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="already initialized"):
        cmd_init(cfg)


def test_cmd_init_missing_binary(cfg):
    cfg.bin_dir.joinpath("initdb.exe").unlink()

    with pytest.raises(SystemExit, match="initdb not found"):
        cmd_init(cfg)


def test_cmd_start_runs_pg_ctl(cfg):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")

    with patch("postgresql_portable.commands.subprocess.run") as run:
        run.return_value.returncode = 0
        cmd_start(cfg)

    assert run.call_count == 2
    start_call = run.call_args_list[0].args[0]
    assert start_call[-1] == "start"
    assert str(cfg.startup_log) in start_call


def test_cmd_start_not_initialized(cfg):
    with pytest.raises(SystemExit, match="not initialized"):
        cmd_start(cfg)


def test_cmd_stop_runs_pg_ctl(cfg):
    with patch("postgresql_portable.commands.subprocess.run") as run:
        run.return_value.returncode = 0
        cmd_stop(cfg)

    run.assert_called_once()
    assert run.call_args.args[0][-1] == "stop"


def test_cmd_connect_runs_psql(cfg, monkeypatch):
    monkeypatch.setenv("PG_PASSWORD", "admin")

    with patch("postgresql_portable.commands.subprocess.call", return_value=0) as call:
        with pytest.raises(SystemExit) as exc:
            cmd_connect(cfg, ["-c", "SELECT 1"])

    assert exc.value.code == 0
    call.assert_called_once()
    cmd = call.call_args.args[0]
    assert cmd[0] == str(cfg.psql)
    assert "-U" in cmd
    assert cfg.user in cmd
    assert "-c" in cmd
    assert call.call_args.kwargs["env"]["PGPASSWORD"] == "admin"


def test_cmd_status_not_initialized(cfg, capsys):
    with patch("postgresql_portable.commands._server_is_ready", return_value=False):
        cmd_status(cfg)

    out = capsys.readouterr().out
    assert "initialized = False" in out
    assert "postgres-init.bat" in out


def test_cmd_status_server_running(cfg, monkeypatch, capsys):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")
    monkeypatch.setenv("WINCCOA_USERNAME", "winccoa")
    monkeypatch.setenv("WINCCOA_DATABASE", "winccoa")

    ctl = type("R", (), {"returncode": 0, "stdout": "pg_ctl: server is running", "stderr": ""})()

    with patch("postgresql_portable.commands._capture", return_value=ctl):
        with patch("postgresql_portable.commands._server_is_ready", return_value=True):
            with patch("postgresql_portable.commands._psql_scalar") as scalar:
                scalar.side_effect = [
                    "PostgreSQL test-version",
                    "UTF8",
                    "English_United States.1252",
                    "5432",
                    "postgres (owner: postgres)\nwinccoa (owner: winccoa)",
                ]
                cmd_status(cfg)

    out = capsys.readouterr().out
    assert "accepting connections" in out
    assert "PostgreSQL test-version" in out
    assert "winccoa (owner: winccoa)" in out
    assert "WinCC OA (.env)" in out
    assert "user     = winccoa" in out


def test_cmd_status_server_stopped(cfg, capsys):
    (cfg.data_dir / "PG_VERSION").write_text("18\n", encoding="utf-8")

    ctl = type("R", (), {"returncode": 3, "stdout": "", "stderr": "pg_ctl: no server running"})()

    with patch("postgresql_portable.commands._capture", return_value=ctl):
        with patch("postgresql_portable.commands._server_is_ready", return_value=False):
            cmd_status(cfg)

    out = capsys.readouterr().out
    assert "no server running" in out
    assert "not accepting connections" in out
    assert "postgres-start.bat" in out


def test_cmd_info_prints(cfg, capsys):
    cmd_info(cfg)
    out = capsys.readouterr().out

    assert str(cfg.install) in out
    assert str(cfg.bin_dir) in out
    assert str(cfg.data_dir) in out
    assert "testuser" in out
    assert "testdb" in out
    assert "initialized = False" in out
