from __future__ import annotations

from fastapi import FastAPI

from .config_loader import apply_configured_logger_overrides, load_settings
from .core.app import create_app


def _configured_app() -> FastAPI:
    settings = load_settings()
    apply_configured_logger_overrides(settings)
    return create_app(settings)


app = _configured_app()


def get_application() -> FastAPI:
    """Provide a convenience accessor for application factories."""
    return _configured_app()
