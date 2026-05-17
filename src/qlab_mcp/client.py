"""UDP client for QLab's OSC reply protocol."""

from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import threading
import time
from typing import Any

from .config import QLabConfig
from .errors import OscProtocolError, OscTimeoutError, QLabReplyError
from .osc import decode_message, encode_message


@dataclass(frozen=True)
class QLabReply:
    invoked_address: str
    reply_address: str
    status: str
    data: Any = None
    workspace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.invoked_address,
            "reply_address": self.reply_address,
            "status": self.status,
            "workspace_id": self.workspace_id,
            "data": self.data,
        }


class QLabOscClient:
    """Send one OSC message to QLab and wait for its JSON reply."""

    _locks_guard = threading.Lock()
    _locks: dict[tuple[str, int, int], threading.Lock] = {}

    def __init__(self, config: QLabConfig | None = None):
        self.config = config or QLabConfig.from_env()
        self._lock = self._get_lock(self.config)

    @classmethod
    def _get_lock(cls, config: QLabConfig) -> threading.Lock:
        key = (config.host, config.osc_port, config.reply_port)
        with cls._locks_guard:
            if key not in cls._locks:
                cls._locks[key] = threading.Lock()
            return cls._locks[key]

    def request(self, address: str, *args: Any, workspace_id: str | None = None) -> QLabReply:
        with self._lock:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("", self.config.reply_port))
                if workspace_id and self.config.passcode:
                    self._send_with_reply_on_socket(
                        sock,
                        f"/workspace/{workspace_id}/connect",
                        self.config.passcode,
                    )
                return self._send_with_reply_on_socket(sock, address, *args)

    def _send_with_reply(self, address: str, *args: Any) -> QLabReply:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("", self.config.reply_port))
            return self._send_with_reply_on_socket(sock, address, *args)

    def _send_with_reply_on_socket(self, sock: socket.socket, address: str, *args: Any) -> QLabReply:
        packet = encode_message(address, *args)
        deadline = time.monotonic() + self.config.timeout

        sock.sendto(packet, (self.config.host, self.config.osc_port))

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            sock.settimeout(remaining)

            try:
                data, _ = sock.recvfrom(65535)
            except (socket.timeout, ConnectionResetError) as exc:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}") from exc

            reply = self._parse_reply(data, expected_address=address, ignore_unrelated=True)
            if reply is None:
                continue
            if self._reply_matches(reply, address):
                if reply.status != "ok":
                    raise QLabReplyError(reply.status, reply.data, reply.invoked_address)
                return reply

    @staticmethod
    def _reply_matches(reply: QLabReply, expected_address: str) -> bool:
        expected = expected_address.lstrip("/")
        invoked = reply.invoked_address.lstrip("/")
        return invoked == expected or invoked.endswith(expected)

    @staticmethod
    def _parse_reply(
        packet: bytes,
        expected_address: str | None = None,
        ignore_unrelated: bool = False,
    ) -> QLabReply | None:
        message = decode_message(packet)
        if not message.address.startswith("/reply/"):
            if ignore_unrelated:
                return None
            raise OscProtocolError(f"Unexpected non-reply OSC address: {message.address}")

        invoked = message.address.removeprefix("/reply/")
        if ignore_unrelated and expected_address is not None:
            expected = expected_address.lstrip("/")
            if invoked != expected and not invoked.endswith(expected):
                return None

        if len(message.args) != 1 or not isinstance(message.args[0], str):
            raise OscProtocolError(f"QLab reply must contain one JSON string argument: {message.address}")

        try:
            payload = json.loads(message.args[0])
        except json.JSONDecodeError as exc:
            raise OscProtocolError(f"Invalid QLab reply JSON for {expected_address}: {exc}") from exc

        if not isinstance(payload, dict):
            raise OscProtocolError("QLab reply JSON must be an object")

        status = payload.get("status")
        if not isinstance(status, str):
            raise OscProtocolError("QLab reply JSON missing string status")

        workspace_id = payload.get("workspace_id")
        if workspace_id is not None and not isinstance(workspace_id, str):
            raise OscProtocolError("QLab reply workspace_id must be a string when present")

        return QLabReply(
            invoked_address=invoked,
            reply_address=message.address,
            status=status,
            data=payload.get("data"),
            workspace_id=workspace_id,
        )


