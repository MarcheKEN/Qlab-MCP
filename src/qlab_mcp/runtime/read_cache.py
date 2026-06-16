"""Short-lived shared cache for repeated read-only QLab OSC calls."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Hashable


SENSITIVE_CACHE_PROFILES = {"technical", "full_sensitive"}


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


@dataclass
class _InflightEntry:
    event: threading.Event
    value: Any = None
    error: BaseException | None = None


class ReadCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[Hashable, _CacheEntry] = {}
        self._inflight: dict[Hashable, _InflightEntry] = {}

    def get_or_set(self, key: Hashable, ttl: float, factory: Callable[[], Any]) -> Any:
        if ttl <= 0:
            return factory()

        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value
            if entry is not None:
                self._entries.pop(key, None)
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = _InflightEntry(event=threading.Event())
                self._inflight[key] = inflight
                owner = True
            else:
                owner = False

        if not owner:
            inflight.event.wait()
            if inflight.error is not None:
                raise inflight.error
            return inflight.value

        try:
            value = factory()
        except BaseException as exc:
            with self._lock:
                inflight.error = exc
                self._inflight.pop(key, None)
                inflight.event.set()
            raise
        with self._lock:
            self._entries[key] = _CacheEntry(expires_at=now + ttl, value=value)
            inflight.value = value
            self._inflight.pop(key, None)
            inflight.event.set()
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            inflight = list(self._inflight.values())
            self._inflight.clear()
        for entry in inflight:
            entry.error = RuntimeError("Read cache cleared while request was in flight")
            entry.event.set()


_SHARED_CACHE = ReadCache()


def shared_read_cache() -> ReadCache:
    return _SHARED_CACHE


def cache_profile_is_safe(profile: str | None) -> bool:
    if profile is None:
        return True
    return profile.strip().lower() not in SENSITIVE_CACHE_PROFILES


def client_cache_namespace(client: Any) -> tuple[Any, ...]:
    config = getattr(client, "config", None)
    if config is None:
        return (client,)
    if client.__class__.__module__ != "qlab_mcp.osc.client":
        return (client,)
    passcode = getattr(config, "passcode", None)
    return (
        getattr(config, "host", None),
        getattr(config, "osc_port", None),
        getattr(config, "reply_port", None),
        None if not passcode else hash(passcode),
    )
