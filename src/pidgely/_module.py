"""Module-level API in the style of the Resend Python SDK:

    import pidgely
    pidgely.api_key = os.environ["PIDGELY_API_KEY"]
    pidgely.Emails.send({...})

Each ``pidgely.<Resource>`` is a proxy to the matching resource of a default
:class:`~pidgely.Pidgely` client, built from ``pidgely.api_key`` / ``pidgely.base_url``
(or the environment) and rebuilt when they change.
"""

from __future__ import annotations

import inspect
import os
import sys
import threading
from typing import Any, Optional, Tuple

from ._client import Pidgely

_lock = threading.Lock()
_cached: Optional[Tuple[Tuple[Any, ...], Pidgely]] = None


def default_client() -> Pidgely:
    """The client behind the module-level API."""
    global _cached
    mod = sys.modules["pidgely"]
    config = (
        getattr(mod, "api_key", None),
        getattr(mod, "base_url", None),
        getattr(mod, "timeout", None),
        getattr(mod, "max_retries", None),
        os.environ.get("PIDGELY_API_KEY"),
        os.environ.get("PIDGELY_BASE_URL"),
    )
    with _lock:
        if _cached is None or _cached[0] != config:
            client = Pidgely(config[0], base_url=config[1], timeout=config[2], max_retries=config[3])
            if _cached is not None:
                _cached[1].close()
            _cached = (config, client)
        return _cached[1]


class ResourceProxy:
    """Forwards attribute access to ``default_client().<path>``."""

    __slots__ = ("_cls", "_path")

    def __init__(self, path: str, cls: type) -> None:
        self._path = path
        self._cls = cls

    def __getattr__(self, name: str) -> Any:
        # Static helpers (Webhooks.verify) need no client, so no API key.
        static = inspect.getattr_static(self._cls, name, None)
        if isinstance(static, staticmethod):
            return getattr(self._cls, name)
        target: Any = default_client()
        for part in self._path.split("."):
            target = getattr(target, part)
        return getattr(target, name)

    def __repr__(self) -> str:
        return f"<pidgely.{self._cls.__name__} (module API)>"
