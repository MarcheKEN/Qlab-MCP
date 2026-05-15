"""Runtime configuration for QLab OSC access."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class QLabConfig:
    host: str = "127.0.0.1"
    osc_port: int = 53000
    reply_port: int = 53001
    timeout: float = 2.0
    passcode: str | None = None

    @classmethod
    def from_env(cls) -> "QLabConfig":
        return cls(
            host=os.getenv("QLAB_HOST", "127.0.0.1"),
            osc_port=int(os.getenv("QLAB_OSC_PORT", "53000")),
            reply_port=int(os.getenv("QLAB_REPLY_PORT", "53001")),
            timeout=float(os.getenv("QLAB_TIMEOUT", "2.0")),
            passcode=os.getenv("QLAB_PASSCODE") or None,
        )
