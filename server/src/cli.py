from __future__ import annotations

import argparse
import logging
from typing import Any, Dict

import uvicorn

from .config import Settings
from .core.app import create_app

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monstr log monitoring service")
    parser.add_argument(
        "--log",
        dest="logs",
        action="append",
        default=[],
        help="Absolute path to a log file to monitor. Repeat for multiple files.",
    )
    parser.add_argument("--host", dest="host", help="API host binding override")
    parser.add_argument("--port", dest="port", type=int, help="API port binding override")
    parser.add_argument(
        "--log-level", dest="log_level", help="Override the API log level (info, debug, ...)",
    )
    return parser.parse_args()


def build_settings(args: argparse.Namespace) -> Settings:
    base = Settings()
    overrides: Dict[str, Any] = {}

    if args.logs:
        overrides["log_sources"] = args.logs
    if args.host:
        overrides["api_host"] = args.host
    if args.port:
        overrides["api_port"] = args.port
    if args.log_level:
        overrides["api_log_level"] = args.log_level

    if overrides:
        return base.model_copy(update=overrides)
    return base


def main() -> None:
    args = parse_args()
    settings = build_settings(args)

    logging.basicConfig(level=getattr(logging, settings.api_log_level.upper(), logging.INFO))

    logger.info(
        "Starting API on %s:%s monitoring %d log file(s)",
        settings.api_host,
        settings.api_port,
        len(settings.log_sources),
    )

    app = create_app(settings)
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_level=settings.api_log_level)


if __name__ == "__main__":
    main()
