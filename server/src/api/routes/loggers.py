from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin/loggers", tags=["admin", "loggers"])


class LoggerInfo(BaseModel):
    name: str
    level: str


class SetLoggerRequest(BaseModel):
    name: str = Field(..., description="Logger name, e.g. 'root' or 'services.cleanup'")
    level: str = Field(..., description="One of CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET")


def _normalize_level(level: str) -> int:
    try:
        return getattr(logging, level.upper())
    except Exception:
        raise ValueError(f"Unknown level: {level}")


@router.get("/", response_model=list[LoggerInfo])
async def list_loggers() -> list[LoggerInfo]:
    """Return known loggers and their effective levels. This enumerates the logging
    manager's loggerDict for convenience; it does not create new loggers.
    """
    manager = logging.root.manager
    out: list[LoggerInfo] = []
    for name, logger_obj in manager.loggerDict.items():
        # loggerDict can contain PlaceHolder objects for packages. Skip those.
        if isinstance(logger_obj, logging.Logger):
            level = logging.getLevelName(logger_obj.getEffectiveLevel())
            out.append(LoggerInfo(name=name, level=level))
    # add root
    out.insert(0, LoggerInfo(name="root", level=logging.getLevelName(logging.getLogger().getEffectiveLevel())))
    return out


@router.post("/", response_model=LoggerInfo)
async def set_logger(req: SetLoggerRequest) -> LoggerInfo:
    """Set the named logger's level at runtime. Returns the new level value."""
    try:
        level_value = _normalize_level(req.level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger = logging.getLogger(req.name)
    logger.setLevel(level_value)
    return LoggerInfo(name=req.name, level=logging.getLevelName(logger.getEffectiveLevel()))


# Debug request-finish endpoints removed; middleware now inspects the
# `api.call` logger's level (isEnabledFor(logging.DEBUG)) to decide whether
# to emit the request-finish message.
