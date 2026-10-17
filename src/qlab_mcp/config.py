"""Runtime configuration for QLab OSC access."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class QLabConfig:
    host: str = "127.0.0.1"
    osc_port: int = 53000
    reply_port: int = 53001
    timeout: float = 2.0
    cache_ttl: float = 10.0
    passcode: str | None = None
    enable_write: bool = False
    write_dry_run_default: bool = True
    update_debug: bool = False

    @classmethod
    def from_env(cls) -> "QLabConfig":
        return cls(
            host=os.getenv("QLAB_HOST", "127.0.0.1"),
            osc_port=int(os.getenv("QLAB_OSC_PORT", "53000")),
            reply_port=int(os.getenv("QLAB_REPLY_PORT", "53001")),
            timeout=float(os.getenv("QLAB_TIMEOUT", "2.0")),
            cache_ttl=float(os.getenv("QLAB_CACHE_TTL", "10.0")),
            passcode=os.getenv("QLAB_PASSCODE") or None,
            enable_write=_env_bool("QLAB_ENABLE_WRITE", False),
            write_dry_run_default=_env_bool("QLAB_WRITE_DRY_RUN_DEFAULT", True),
            update_debug=_env_bool("QLAB_UPDATE_DEBUG", False),
        )
