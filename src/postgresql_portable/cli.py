from __future__ import annotations

import argparse

from postgresql_portable.commands import (
    cmd_connect,
    cmd_info,
    cmd_init,
    cmd_restart,
    cmd_start,
    cmd_status,
    cmd_stop,
)
from postgresql_portable.config import load_config
from postgresql_portable.winccoa import cmd_create_winccoa, cmd_drop_winccoa


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="postgresql_portable",
        description="Manage portable PostgreSQL (ZIP binaries on Windows).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the data directory (once)")
    sub.add_parser("start", help="Start the server")
    sub.add_parser("stop", help="Stop the server")
    sub.add_parser("restart", help="Restart the server")
    sub.add_parser("status", help="Show server status, databases, and cluster info")
    sub.add_parser("info", help="Print configured paths")
    sub.add_parser("create-winccoa", help="Create WinCC OA database and user from .env")

    drop_parser = sub.add_parser("drop-winccoa", help="Drop WinCC OA database (and NGA tablespaces) from .env")
    drop_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm drop without WINCCOA_CONFIRM in .env",
    )
    drop_parser.add_argument(
        "--drop-user",
        action="store_true",
        help="Also drop WINCCOA_USERNAME role (or set WINCCOA_DROP_USER=yes)",
    )
    drop_parser.add_argument(
        "--remove-data",
        action="store_true",
        help="Remove local data_winccoa_tablespaces directories after drop",
    )

    connect_parser = sub.add_parser("connect", help="Open psql")
    connect_parser.add_argument("psql_args", nargs=argparse.REMAINDER, help="Extra psql arguments")

    args = parser.parse_args()
    cfg = load_config()

    if args.command == "drop-winccoa":
        cmd_drop_winccoa(
            cfg,
            assume_yes=args.yes,
            drop_user=args.drop_user,
            remove_data=args.remove_data,
        )
        return

    handlers = {
        "init": lambda: cmd_init(cfg),
        "start": lambda: cmd_start(cfg),
        "stop": lambda: cmd_stop(cfg),
        "restart": lambda: cmd_restart(cfg),
        "status": lambda: cmd_status(cfg),
        "info": lambda: cmd_info(cfg),
        "create-winccoa": lambda: cmd_create_winccoa(cfg),
        "connect": lambda: cmd_connect(cfg, args.psql_args),
    }
    handlers[args.command]()


if __name__ == "__main__":
    main()
