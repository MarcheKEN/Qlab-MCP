from __future__ import annotations

import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscProtocolError, OscTimeoutError
from qlab_mcp.osc import decode_message, encode_message
from qlab_mcp.osc.client import QLabOscClient, _slip_encode


def reply_packet(address: str, data: Any = None, *, status: str = "ok") -> bytes:
    return encode_message(
        f"/reply/{address.lstrip('/')}",
        json.dumps({"status": status, "data": data}),
    )


class ScheduledUdpServer:
    """Small loopback server that can schedule packets independently."""

    def __init__(
        self,
        action: Callable[[int, str, tuple[str, int], int], list[tuple[float, bytes, int]]],
        *,
        default_reply_port: int | None = None,
        apply_reply_port_updates: bool = True,
    ):
        self.action = action
        self.default_reply_port = default_reply_port
        self.apply_reply_port_updates = apply_reply_port_updates
        self.actual_requests: list[str] = []
        self.control_ports: list[int] = []
        self.client_ports: list[int] = []
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._timers: list[threading.Timer] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self.port: int | None = None
        self._sock: socket.socket | None = None

    def __enter__(self) -> "ScheduledUdpServer":
        self._thread.start()
        if not self._ready.wait(2):
            raise RuntimeError("scheduled UDP server did not start")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._stop.set()
        if self.port is not None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wake:
                wake.sendto(b"", ("127.0.0.1", self.port))
        self._thread.join(2)
        for timer in self._timers:
            timer.join(2)
        self._sock = None

    def _serve(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            self._sock = sock
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
            sock.settimeout(0.05)
            self._ready.set()
            while not self._stop.is_set():
                try:
                    packet, client_addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                if not packet:
                    continue
                message = decode_message(packet)
                if message.address == "/udpReplyPort":
                    if self.apply_reply_port_updates and message.args and isinstance(message.args[0], int):
                        self.control_ports.append(message.args[0])
                    continue
                self.actual_requests.append(message.address)
                self.client_ports.append(client_addr[1])
                request_number = len(self.actual_requests)
                reply_port = self.control_ports[-1] if self.control_ports else self.default_reply_port or client_addr[1]
                for delay, response, port_offset in self.action(
                    request_number,
                    message.address,
                    client_addr,
                    reply_port,
                ):
                    destination = (client_addr[0], client_addr[1] + port_offset)
                    timer = threading.Timer(delay, self._send, args=(response, destination))
                    timer.daemon = True
                    timer.start()
                    self._timers.append(timer)

    def _send(self, packet: bytes, destination: tuple[str, int]) -> None:
        sock = self._sock
        if sock is not None and not self._stop.is_set():
            try:
                sock.sendto(packet, destination)
            except OSError:
                pass


def current_reply_action(
    request_number: int,
    address: str,
    client_addr: tuple[str, int],
    reply_port: int,
) -> list[tuple[float, bytes, int]]:
    return [(0.0, reply_packet(address, f"reply-{request_number}"), reply_port - client_addr[1])]


class UdpTransportTests(unittest.TestCase):
    def client_for(
        self,
        server: ScheduledUdpServer,
        timeout: float = 0.2,
        passcode: str | None = None,
    ) -> QLabOscClient:
        assert server.port is not None
        return QLabOscClient(
            QLabConfig(
                host="127.0.0.1",
                osc_port=server.port,
                reply_port=53001,
                timeout=timeout,
                passcode=passcode,
            )
        )

    def test_every_request_announces_an_isolated_reply_port(self) -> None:
        with ScheduledUdpServer(current_reply_action) as server:
            client = self.client_for(server)
            first = client.request("/version")
            second = client.request("/version")

        self.assertEqual(first.data, "reply-1")
        self.assertEqual(second.data, "reply-2")
        self.assertEqual(len(server.control_ports), 2)
        self.assertEqual(len(set(server.control_ports)), 2)
        self.assertNotEqual(server.client_ports[0], server.client_ports[1])

    def test_workspace_discovery_uses_default_reply_port_before_authentication(self) -> None:
        with ScheduledUdpServer(
            current_reply_action,
            default_reply_port=53001,
            apply_reply_port_updates=False,
        ) as server:
            reply = self.client_for(server, passcode="9540").request("/workspaces")

        self.assertEqual(reply.data, "reply-1")

    def test_workspace_request_authenticates_before_custom_reply_port(self) -> None:
        with ScheduledUdpServer(
            current_reply_action,
            default_reply_port=53001,
            apply_reply_port_updates=False,
        ) as server:
            reply = self.client_for(server, passcode="9540").request(
                "/workspace/ws-1/cueLists",
                workspace_id="ws-1",
            )

        self.assertEqual(reply.data, "reply-2")

    def test_late_identical_reply_cannot_be_consumed_by_next_request(self) -> None:
        def action(number: int, address: str, client_addr: tuple[str, int], reply_port: int) -> list[tuple[float, bytes, int]]:
            delay = 0.15 if number == 1 else 0.01
            value = "stale-first" if number == 1 else "fresh-second"
            return [(delay, reply_packet(address, value), reply_port - client_addr[1])]

        with ScheduledUdpServer(action) as server:
            client = self.client_for(server, timeout=0.05)
            with self.assertRaises(OscTimeoutError):
                client.request("/version")
            reply = client.request("/version", reply_timeout=0.25)

        self.assertEqual(reply.data, "fresh-second")

    def test_duplicate_reply_is_ignored_after_first_reply_and_next_request_is_fresh(self) -> None:
        def action(number: int, address: str, client_addr: tuple[str, int], reply_port: int) -> list[tuple[float, bytes, int]]:
            packet = reply_packet(address, "first" if number == 1 else "second")
            return [
                (0.0, packet, reply_port - client_addr[1]),
                (0.03, packet, reply_port - client_addr[1]),
            ]

        with ScheduledUdpServer(action) as server:
            client = self.client_for(server)
            self.assertEqual(client.request("/version").data, "first")
            self.assertEqual(client.request("/version").data, "second")

    def test_unrelated_and_out_of_order_replies_are_skipped(self) -> None:
        def action(number: int, address: str, client_addr: tuple[str, int], reply_port: int) -> list[tuple[float, bytes, int]]:
            wrong = reply_packet("/other", "wrong")
            right = reply_packet(address, "right")
            return [
                (0.0, wrong, reply_port - client_addr[1]),
                (0.005, right, reply_port - client_addr[1]),
            ]

        with ScheduledUdpServer(action) as server:
            reply = self.client_for(server).request("/version")

        self.assertEqual(reply.data, "right")

    def test_malformed_matching_udp_reply_fails_closed(self) -> None:
        def action(number: int, address: str, client_addr: tuple[str, int], reply_port: int) -> list[tuple[float, bytes, int]]:
            return [(0.0, encode_message(f"/reply/{address.lstrip('/')}", "{bad json"), reply_port - client_addr[1])]

        with ScheduledUdpServer(action) as server:
            with self.assertRaises(OscProtocolError):
                self.client_for(server).request("/version")


class TcpSlipTransportTests(unittest.TestCase):
    def test_fragmented_multiple_frames_and_unrelated_frame(self) -> None:
        ready = threading.Event()
        stop = threading.Event()
        port_holder: list[int] = []

        def serve() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                listener.settimeout(2)
                port_holder.append(listener.getsockname()[1])
                ready.set()
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    return
                with conn:
                    conn.settimeout(2)
                    self._read_one_slip_message(conn)
                    frames = [
                        _slip_encode(reply_packet("/other", "ignored")),
                        _slip_encode(reply_packet("/version", "tcp-ok")),
                    ]
                    blob = b"".join(frames)
                    for start in range(0, len(blob), 3):
                        conn.sendall(blob[start : start + 3])
                stop.set()

        server_thread = threading.Thread(target=serve, daemon=True)
        server_thread.start()
        self.assertTrue(ready.wait(2))
        client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=port_holder[0], timeout=0.5))
        reply = client.request_tcp("/version")
        server_thread.join(2)

        self.assertEqual(reply.data, "tcp-ok")
        self.assertTrue(stop.is_set())

    @staticmethod
    def _read_one_slip_message(conn: socket.socket) -> bytes:
        data = bytearray()
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                raise AssertionError("client closed before request")
            data.extend(chunk)
            if 0xC0 in data[1:]:
                end = data.index(0xC0, 1)
                frame = bytes(data[1:end])
                # Exercise the actual OSC decoder via a harmless sanity check.
                message = decode_message(_unescape_slip(frame))
                if message.address != "/version":
                    raise AssertionError(message.address)
                return frame

    def test_malformed_slip_escape_fails_closed(self) -> None:
        ready = threading.Event()
        port_holder: list[int] = []

        def serve() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                port_holder.append(listener.getsockname()[1])
                ready.set()
                conn, _ = listener.accept()
                with conn:
                    conn.recv(4096)
                    conn.sendall(b"\xc0\xdb\x01\xc0")

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(2))
        client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=port_holder[0], timeout=0.5))
        with self.assertRaises(OscProtocolError):
            client.request_tcp("/version")
        thread.join(2)

    def test_tcp_close_before_reply_is_a_timeout(self) -> None:
        ready = threading.Event()
        port_holder: list[int] = []

        def serve() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                port_holder.append(listener.getsockname()[1])
                ready.set()
                conn, _ = listener.accept()
                conn.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        self.assertTrue(ready.wait(2))
        client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=port_holder[0], timeout=0.2))
        with self.assertRaises(OscTimeoutError):
            client.request_tcp("/version")
        thread.join(2)


def _unescape_slip(frame: bytes) -> bytes:
    output = bytearray()
    index = 0
    while index < len(frame):
        byte = frame[index]
        if byte == 0xDB:
            index += 1
            escaped = frame[index]
            output.append(0xC0 if escaped == 0xDC else 0xDB)
        else:
            output.append(byte)
        index += 1
    return bytes(output)


if __name__ == "__main__":
    unittest.main()
