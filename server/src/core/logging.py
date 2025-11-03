import logging
from typing import Any

def get_logger(name_or_obj: Any) -> logging.Logger:
    """Return a logger using the module name but strip the leading
    "server.src." prefix so examples and overrides can use shorter names.

    Accept either a module/string or an object with __name__.
    """
    if hasattr(name_or_obj, "__name__"):
        name = getattr(name_or_obj, "__name__")
    else:
        name = str(name_or_obj)

    prefix = "server.src."
    if name.startswith(prefix):
        name = name[len(prefix):]

    return logging.getLogger(name)
