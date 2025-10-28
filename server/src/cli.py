from __future__ import annotations

import argparse
import logging
import logging.config
from typing import Any, Dict

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from copy import deepcopy

from .config import Settings
from .core.app import create_app

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monstr log monitoring service")
    parser.add_argument(
        "--node",
        dest="nodes",
        action="append",
        default=[],
        help="Monitor a node specified as NAME:PATH to its log file. Repeat for multiple nodes.",
    )
    parser.add_argument(
        "--remote",
        dest="remotes",
        action="append",
        default=[],
        help="Monitor a remote node specified as NAME:HOST:PORT for TCP log streaming. Repeat for multiple remotes.",
    )
    parser.add_argument("--host", dest="host", help="API host binding override")
    parser.add_argument("--port", dest="port", type=int, help="API port binding override")
    parser.add_argument(
        "--log-level", dest="log_level", help="Override the API log level (info, debug, ...)",
    )
    parser.add_argument(
        "--days-offset",
        dest="days_offset",
        type=int,
        help="Days to subtract from current time when aggregating transfer actuals (default: 0)",
    )
    return parser.parse_args()


def build_settings(args: argparse.Namespace) -> Settings:
    base = Settings()
    overrides: Dict[str, Any] = {}

    if getattr(args, "nodes", None):
        overrides["log_sources"] = args.nodes
    if getattr(args, "remotes", None):
        overrides["remote_sources"] = args.remotes
    if args.host:
        overrides["api_host"] = args.host
    if args.port:
        overrides["api_port"] = args.port
    if args.log_level:
        overrides["api_log_level"] = args.log_level
    if getattr(args, "days_offset", None) is not None:
        overrides["days_offset"] = args.days_offset

    if overrides:
        return base.model_copy(update=overrides)
    return base


def main() -> None:
    args = parse_args()
    settings = build_settings(args)

    log_config = deepcopy(LOGGING_CONFIG)
    desired_level = settings.api_log_level.upper()

    # Ensure required sections exist before overriding levels
    log_config.setdefault("root", {"level": desired_level, "handlers": ["default"]})
    log_config.setdefault("loggers", {})

    log_config["root"]["level"] = desired_level
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger_cfg = log_config["loggers"].setdefault(
            logger_name,
            {
                "handlers": ["default"],
                "level": desired_level,
                "propagate": logger_name != "uvicorn.access",
            },
        )
        logger_cfg["level"] = desired_level

    logging.config.dictConfig(log_config)

    logger.info(
        "Starting API on %s:%s monitoring %d file node(s) and %d remote node(s)",
        settings.api_host,
        settings.api_port,
        len(settings.log_sources),
        len(getattr(settings, "remote_sources", [])),
    )

    app = create_app(settings)

    try:
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.api_log_level,
            log_config=log_config,
        )
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")


if __name__ == "__main__":
    main()
