"""Domain errors surfaced by the QLab MCP tools."""

from __future__ import annotations


class QLabMcpError(Exception):
    """Base error for QLab MCP operations."""


class OscTimeoutError(QLabMcpError):
    """Raised when QLab does not reply before the configured timeout."""


class OscProtocolError(QLabMcpError):
    """Raised when an OSC packet cannot be encoded, decoded, or matched."""


class QLabReplyError(QLabMcpError):
    """Raised when QLab returns an error or denied reply."""

    def __init__(self, status: str, data: object = None, address: str | None = None):
        self.status = status
        self.data = data
        self.address = address
        detail = f"QLab reply status={status!r}"
        if address:
            detail += f" for {address}"
        if data is not None:
            detail += f": {data!r}"
        super().__init__(detail)


class UnsafeCuePropertyError(QLabMcpError):
    """Raised when a property path is not in the read-only allowlist."""
