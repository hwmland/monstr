from __future__ import annotations

import argparse
import logging
import logging.config
import os
import time
from copy import deepcopy
from typing import Any, Dict

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from server.src.core.logging import get_logger

from .config import Settings
from .core.app import create_app


logger = get_logger(__name__)


def _sanitize_logger_override_pair(name: str, level: str) -> tuple[str, str] | None:
    """Strip quotes/whitespace and validate the level. Returns (name, level)
    upper-cased level on success or None on invalid input.
    """
    name = name.strip().strip('"').strip("'")
    level = level.strip().strip('"').strip("'").upper()
    try:
        logging._checkLevel(level)
    except Exception:
        logger.warning("Skipping invalid log level '%s' for logger '%s'", level, name)
        return None
    return name, level


def _apply_logger_override(log_config: dict, raw: str) -> None:
    """Parse a raw NAME:LEVEL string, sanitize it and set it on log_config
    if valid. This centralizes the behavior used for both env and CLI input.
    """
    if ":" not in raw:
        return
    name, level = raw.split(":", 1)
    sanitized = _sanitize_logger_override_pair(name, level)
    if sanitized is None:
        return
    name, level = sanitized
    log_config.setdefault("loggers", {}).setdefault(name, {})["level"] = level


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
        "--log",
        dest="log_overrides",
        action="append",
        default=[],
        help="Per-logger override in NAME:LEVEL form (repeatable). CLI overrides take precedence over MONSTR_LOG_OVERRIDES.",
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
    # days_offset removed; nothing to override

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

    # Ensure timestamps and logger name appear before the colored level prefix
    # Normalize formatter strings: if a formatter contains either %(levelprefix)s
    # (uvicorn's colored level) or %(levelname)s, prefix it with %(asctime)s and
    # ensure the logger name appears before the message as "%(name)s: %(message)s".

    # Use UTC for asctime in log output
    logging.Formatter.converter = time.gmtime

    # Use seconds plus milliseconds in the printed timestamp. The Formatter
    # will insert milliseconds via %(msecs)03d; the datefmt therefore only
    # needs to include the seconds part.
    asctime_token = "%(asctime)s.%(msecs)03d"
    datefmt = "%Y-%m-%d %H:%M:%S"

    for fmt in log_config.get("formatters", {}).values():
        try:
            fmt_str = fmt.get("fmt")
        except Exception:
            fmt_str = None
        if not fmt_str:
            continue
        # If formatter already contains asctime and name, skip
        if ("%(asctime)s" in fmt_str or asctime_token in fmt_str) and "%(name)s" in fmt_str:
            fmt.setdefault("datefmt", datefmt)
            continue

        # Many uvicorn/uvloop formatters use %(levelprefix)s or %(levelname)s and
        # may not include %(message)s. For those we prefix or rewrite the
        # formatter so the visible output begins with a UTC timestamp and the
        # logger name.
        if "%(message)s" in fmt_str:
            # only add asctime if not already present
            if "%(asctime)s" not in fmt_str and asctime_token not in fmt_str:
                fmt_str = asctime_token + " " + fmt_str

            # ensure logger name appears before the message
            if "%(name)s" not in fmt_str:
                fmt_str = fmt_str.replace("%(message)s", "%(name)s: %(message)s")
        elif "%(levelprefix)s" in fmt_str or "%(levelname)s" in fmt_str:
            level_token = "%(levelprefix)s" if "%(levelprefix)s" in fmt_str else "%(levelname)s"

            # Remove first occurrence of the level token and any following spaces
            parts = fmt_str.split(level_token, 1)
            # parts -> [before, after]
            after = parts[1].lstrip() if len(parts) > 1 else ""
            prefix = asctime_token + " " + level_token + " %(name)s: "
            fmt_str = prefix + parts[0].rstrip() + (" " + after if after else "")

        fmt["fmt"] = fmt_str
        # set a reasonable date format
        fmt.setdefault("datefmt", datefmt)

    # Apply environment and CLI logger level overrides.
    # MONSTR_LOG_OVERRIDES is a comma-separated list like: "sqlalchemy.engine:WARNING,server:DEBUG"

    env_overrides = os.getenv("MONSTR_LOG_OVERRIDES", "")
    if env_overrides:
        for raw in [p.strip() for p in env_overrides.split(",") if p.strip()]:
            _apply_logger_override(log_config, raw)

    # CLI overrides (args.log_overrides) take precedence
    for pair in (args.log_overrides or []):
        _apply_logger_override(log_config, pair)

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
