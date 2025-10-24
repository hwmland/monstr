from __future__ import annotations

from fastapi import FastAPI

from .config import Settings
from .core.app import create_app

settings = Settings()
app = create_app(settings)


def get_application() -> FastAPI:
    """Provide a convenience accessor for application factories."""
    return create_app(Settings())
