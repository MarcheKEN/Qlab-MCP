from __future__ import annotations

import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscProtocolError, OscTimeoutError, QLabReplyError
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

    def test_different_configured_reply_ports_share_the_udp_endpoint_lock(self) -> None:
        first = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, reply_port=53001)
        )
        second = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, reply_port=53002)
        )
        self.assertIs(first._lock, second._lock)

        ready = threading.Barrier(2)
        sent = threading.Event()
        errors: list[BaseException] = []
        sock = MagicMock()
        sock.__enter__.return_value = sock

        def run() -> None:
            try:
                ready.wait()
                second.request("/version")
            except BaseException as exc:
                errors.append(exc)

        def send(*_args: Any, **_kwargs: Any) -> Any:
            sent.set()
            return type("Reply", (), {"status": "ok", "data": "ok"})()

        with (
            patch("socket.socket", return_value=sock),
            patch.object(second, "_prepare_udp_socket"),
            patch.object(second, "_send_with_reply_on_socket", side_effect=send),
        ):
            with first._lock:
                thread = threading.Thread(target=run)
                thread.start()
                ready.wait()
                self.assertFalse(sent.is_set())
            thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(sent.is_set())

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


class ProtectedTcpSessionTests(unittest.TestCase):
    def test_application_request_runs_before_workspace_authentication(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sent: list[str] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append(address)
            return type("Reply", (), {"status": "ok", "data": []})()

        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            client.request("/workspaces")

        self.assertEqual(sent, ["/workspaces"])
        self.assertEqual(client._tcp_connected_workspaces, set())

    def test_protected_request_uses_tcp_without_opening_udp(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sock = MagicMock()
        sent: list[tuple[str, tuple[Any, ...]]] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append((address, args))
            return type("Reply", (), {"status": "ok", "data": "ok"})()

        with (
            patch("socket.create_connection", return_value=sock),
            patch("socket.socket", side_effect=AssertionError("protected request opened UDP")),
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            reply = client.request("/workspace/ws-1/showMode", workspace_id="ws-1")

        self.assertEqual(reply.data, "ok")
        self.assertEqual(
            sent,
            [
                ("/workspace/ws-1/connect", ("secret",)),
                ("/workspace/ws-1/showMode", ()),
            ],
        )

    def test_two_protected_requests_reuse_connection_and_authentication(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sock = MagicMock()
        sent: list[str] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append(address)
            return type("Reply", (), {"status": "ok", "data": address})()

        with (
            patch("socket.create_connection", return_value=sock) as connect,
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            client.request("/workspace/ws-1/showMode", workspace_id="ws-1")
            client.request("/workspace/ws-1/cueLists", workspace_id="ws-1")

        self.assertEqual(connect.call_count, 1)
        self.assertEqual(sent.count("/workspace/ws-1/connect"), 1)
        self.assertEqual(sent[-2:], ["/workspace/ws-1/showMode", "/workspace/ws-1/cueLists"])

    def test_always_reply_and_workspace_action_share_session(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sent: list[str] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append(address)
            return type("Reply", (), {"status": "ok", "data": "ok"})()

        with (
            patch("socket.create_connection", return_value=MagicMock()) as connect,
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            client.request("/alwaysReply", 1)
            client.request("/workspace/ws-1/showMode")

        self.assertEqual(connect.call_count, 1)
        self.assertEqual(
            sent,
            ["/alwaysReply", "/workspace/ws-1/connect", "/workspace/ws-1/showMode"],
        )

    def test_protected_request_infers_workspace_from_address(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sent: list[str] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append(address)
            return type("Reply", (), {"status": "ok", "data": address})()

        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            client.request("/workspace/ws-1/showMode")

        self.assertEqual(sent, ["/workspace/ws-1/connect", "/workspace/ws-1/showMode"])

    def test_workspace_mismatch_fails_before_network_io(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )

        with patch("socket.create_connection") as connect:
            with self.assertRaisesRegex(ValueError, "workspace_id"):
                client.request("/workspace/ws-address/showMode", workspace_id="ws-explicit")

        connect.assert_not_called()

    def test_direct_connect_sends_only_caller_request(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="configured")
        )
        sent: list[tuple[str, tuple[Any, ...]]] = []

        def send(_sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
            sent.append((address, args))
            return type("Reply", (), {"status": "ok", "data": "ok"})()

        with (
            patch("socket.create_connection", return_value=MagicMock()),
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            client.request("/workspace/ws-1/connect", "caller-passcode")

        self.assertEqual(sent, [("/workspace/ws-1/connect", ("caller-passcode",))])

    def test_pre_request_buffered_frame_cannot_satisfy_next_request(self) -> None:
        first_address = "/workspace/ws-1/showMode"
        second_address = "/workspace/ws-1/cueLists"
        coalesced = b"".join(
            [
                _slip_encode(reply_packet("/other", "ignored")),
                _slip_encode(reply_packet(first_address, "first")),
                _slip_encode(reply_packet(second_address, "stale")),
            ]
        )

        class FakeSocket:
            def __init__(self) -> None:
                self.chunks = [
                    _slip_encode(reply_packet("/workspace/ws-1/connect", "ok:view")),
                    coalesced,
                    _slip_encode(reply_packet(second_address, "fresh")),
                ]

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, _packet: bytes) -> None:
                pass

            def recv(self, _size: int) -> bytes:
                if not self.chunks:
                    raise socket.timeout
                return self.chunks.pop(0)

        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        with patch("socket.create_connection", return_value=FakeSocket()):
            first = client.request(first_address)
            second = client.request(second_address)

        self.assertEqual((first.data, second.data), ("first", "fresh"))

    def test_invalid_utf8_discards_session_and_next_request_reauthenticates(self) -> None:
        action = "/workspace/ws-1/showMode"

        class FakeSocket:
            def __init__(self, action_reply: bytes) -> None:
                self.sent: list[str] = []
                self.closed = False
                self.chunks = [
                    _slip_encode(reply_packet("/workspace/ws-1/connect", "ok:view")),
                    action_reply,
                ]

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, packet: bytes) -> None:
                self.sent.append(decode_message(_unescape_slip(packet[1:-1])).address)

            def recv(self, _size: int) -> bytes:
                return self.chunks.pop(0)

            def close(self) -> None:
                self.closed = True

        malformed = _slip_encode(b"/reply/\xff\x00\x00\x00\x00")
        first_socket = FakeSocket(malformed)
        second_socket = FakeSocket(_slip_encode(reply_packet(action, "fresh")))
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )

        with patch("socket.create_connection", side_effect=[first_socket, second_socket]) as connect:
            with self.assertRaises(OscProtocolError):
                client.request(action)

            self.assertTrue(first_socket.closed)
            self.assertIsNone(client._tcp_socket)
            self.assertEqual(client._tcp_buffer, bytearray())
            self.assertEqual(client._tcp_connected_workspaces, set())
            reply = client.request(action)

        self.assertEqual(reply.data, "fresh")
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(first_socket.sent, ["/workspace/ws-1/connect", action])
        self.assertEqual(second_socket.sent, ["/workspace/ws-1/connect", action])

    def test_each_send_resets_socket_timeout_to_current_request_budget(self) -> None:
        first_action = "/workspace/ws-1/showMode"
        second_action = "/workspace/ws-1/cueLists"

        class FakeSocket:
            def __init__(self) -> None:
                self.timeout: float | None = None
                self.send_timeouts: list[tuple[str, float | None]] = []
                self.chunks = [
                    _slip_encode(reply_packet("/workspace/ws-1/connect", "ok:view")),
                    _slip_encode(reply_packet(first_action, "first")),
                    _slip_encode(reply_packet(second_action, "second")),
                ]

            def settimeout(self, timeout: float) -> None:
                self.timeout = timeout

            def sendall(self, packet: bytes) -> None:
                address = decode_message(_unescape_slip(packet[1:-1])).address
                self.send_timeouts.append((address, self.timeout))

            def recv(self, _size: int) -> bytes:
                return self.chunks.pop(0)

        sock = FakeSocket()
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        with patch("socket.create_connection", return_value=sock):
            client.request(first_action, reply_timeout=0.01)
            client.request(second_action)

        self.assertAlmostEqual(sock.send_timeouts[1][1] or 0.0, 0.01, delta=0.002)
        self.assertAlmostEqual(sock.send_timeouts[2][1] or 0.0, 0.2, delta=0.002)

    def test_reply_timeout_is_shared_by_tcp_creation_authentication_and_action(self) -> None:
        action = "/workspace/ws-1/showMode"
        clock = [0.0]

        class FakeSocket:
            def __init__(self) -> None:
                self.timeout: float | None = None
                self.sent: list[str] = []
                self.send_timeouts: list[float | None] = []

            def settimeout(self, timeout: float) -> None:
                self.timeout = timeout

            def sendall(self, packet: bytes) -> None:
                self.sent.append(decode_message(_unescape_slip(packet[1:-1])).address)
                self.send_timeouts.append(self.timeout)

            def recv(self, _size: int) -> bytes:
                if len(self.sent) == 1:
                    clock[0] += 0.3
                return _slip_encode(reply_packet(self.sent[-1], "ok"))

        sock = FakeSocket()
        connect_timeouts: list[float] = []

        def create_connection(_endpoint: object, *, timeout: float) -> FakeSocket:
            connect_timeouts.append(timeout)
            clock[0] += 0.2
            return sock

        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=5.0, passcode="secret")
        )
        with (
            patch("qlab_mcp.osc.client.time.monotonic", side_effect=lambda: clock[0]),
            patch("socket.create_connection", side_effect=create_connection),
        ):
            reply = client.request(action, reply_timeout=1.0)

        self.assertEqual(reply.data, "ok")
        self.assertEqual(sock.sent, ["/workspace/ws-1/connect", action])
        self.assertAlmostEqual(connect_timeouts[0], 1.0)
        self.assertAlmostEqual(sock.send_timeouts[0] or 0.0, 0.8)
        self.assertAlmostEqual(sock.send_timeouts[1] or 0.0, 0.5)

    def test_one_shot_tcp_uses_the_same_end_to_end_reply_timeout(self) -> None:
        action = "/workspace/ws-1/showMode"
        clock = [0.0]
        connect_timeouts: list[float] = []
        send_timeouts: list[tuple[str, float]] = []
        sock = MagicMock()
        sock.__enter__.return_value = sock

        def create_connection(_endpoint: object, *, timeout: float) -> MagicMock:
            connect_timeouts.append(timeout)
            clock[0] += 0.2
            return sock

        def send(
            _sock: object,
            address: str,
            *_args: Any,
            reply_timeout: float | None = None,
            reply_deadline: float | None = None,
            **_kwargs: Any,
        ) -> Any:
            effective_timeout = (
                (reply_deadline - clock[0])
                if reply_deadline is not None
                else (client.config.timeout if reply_timeout is None else reply_timeout)
            )
            send_timeouts.append((address, effective_timeout))
            if address.endswith("/connect"):
                clock[0] += 0.3
            return type("Reply", (), {"status": "ok", "data": "ok"})()

        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=5.0, passcode="secret")
        )
        with (
            patch("qlab_mcp.osc.client.time.monotonic", side_effect=lambda: clock[0]),
            patch("socket.create_connection", side_effect=create_connection),
            patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=send),
        ):
            reply = client.request_tcp(action, reply_timeout=1.0)

        self.assertEqual(reply.data, "ok")
        self.assertAlmostEqual(connect_timeouts[0], 1.0)
        self.assertEqual([address for address, _timeout in send_timeouts], [
            "/workspace/ws-1/connect",
            action,
        ])
        self.assertAlmostEqual(send_timeouts[0][1], 0.8)
        self.assertAlmostEqual(send_timeouts[1][1], 0.5)

    def test_expired_reply_timeout_after_auth_does_not_send_action_or_retry(self) -> None:
        action = "/workspace/ws-1/showMode"
        clock = [0.0]

        class FakeSocket:
            def __init__(self) -> None:
                self.sent: list[str] = []
                self.closed = False

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, packet: bytes) -> None:
                self.sent.append(decode_message(_unescape_slip(packet[1:-1])).address)

            def recv(self, _size: int) -> bytes:
                clock[0] += 0.9
                return _slip_encode(reply_packet(self.sent[-1], "ok"))

            def close(self) -> None:
                self.closed = True

        sock = FakeSocket()

        def create_connection(_endpoint: object, *, timeout: float) -> FakeSocket:
            self.assertAlmostEqual(timeout, 1.0)
            clock[0] += 0.2
            return sock

        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=5.0, passcode="secret")
        )
        with (
            patch("qlab_mcp.osc.client.time.monotonic", side_effect=lambda: clock[0]),
            patch("socket.create_connection", side_effect=create_connection) as connect,
        ):
            with self.assertRaisesRegex(
                OscTimeoutError,
                "Timed out waiting for QLab TCP reply to /workspace/ws-1/showMode",
            ):
                client.request(action, reply_timeout=1.0)

        self.assertEqual(sock.sent, ["/workspace/ws-1/connect"])
        self.assertTrue(sock.closed)
        self.assertEqual(connect.call_count, 1)
        self.assertIsNone(client._tcp_socket)
        self.assertEqual(client._tcp_connected_workspaces, set())

    def test_all_persistent_reply_failures_discard_and_reauthenticate_without_retry(self) -> None:
        action = "/workspace/ws-1/showMode"
        failures = {
            "reply_error": (
                _slip_encode(reply_packet(action, "denied", status="denied")),
                QLabReplyError,
            ),
            "clean_eof": (b"", OscTimeoutError),
            "protocol_error": (b"\xc0\xdb\x01\xc0", OscProtocolError),
            "timeout": (socket.timeout(), OscTimeoutError),
        }

        class FakeSocket:
            def __init__(self, action_reply: bytes | BaseException) -> None:
                self.sent: list[str] = []
                self.closed = False
                self.chunks: list[bytes | BaseException] = [
                    _slip_encode(reply_packet("/workspace/ws-1/connect", "ok:view")),
                    action_reply,
                ]

            def settimeout(self, _timeout: float) -> None:
                pass

            def sendall(self, packet: bytes) -> None:
                self.sent.append(decode_message(_unescape_slip(packet[1:-1])).address)

            def recv(self, _size: int) -> bytes:
                item = self.chunks.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item

            def close(self) -> None:
                self.closed = True

        for label, (failure, expected_error) in failures.items():
            with self.subTest(label=label):
                first_socket = FakeSocket(failure)
                second_socket = FakeSocket(_slip_encode(reply_packet(action, "fresh")))
                client = QLabOscClient(
                    QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
                )

                with patch("socket.create_connection", side_effect=[first_socket, second_socket]) as connect:
                    with self.assertRaises(expected_error):
                        client.request(action)

                    self.assertTrue(first_socket.closed)
                    self.assertIsNone(client._tcp_socket)
                    self.assertEqual(client._tcp_buffer, bytearray())
                    self.assertEqual(client._tcp_connected_workspaces, set())
                    reply = client.request(action)

                self.assertEqual(reply.data, "fresh")
                self.assertEqual(connect.call_count, 2)
                self.assertEqual(first_socket.sent, ["/workspace/ws-1/connect", action])
                self.assertEqual(second_socket.sent, ["/workspace/ws-1/connect", action])

    def test_timeout_discards_session_without_retry_and_next_request_reauthenticates(self) -> None:
        action = "/workspace/ws-1/showMode"

        class FakeSocket:
            def __init__(self, *, succeed: bool) -> None:
                self.sent: list[str] = []
                self.closed = False
                self.timeouts: list[float] = []
                self.chunks: list[bytes | BaseException] = [
                    _slip_encode(reply_packet("/workspace/ws-1/connect", "ok:view")),
                    (
                        _slip_encode(reply_packet(action, "fresh"))
                        if succeed
                        else socket.timeout()
                    ),
                ]

            def settimeout(self, timeout: float) -> None:
                self.timeouts.append(timeout)

            def sendall(self, packet: bytes) -> None:
                self.sent.append(decode_message(_unescape_slip(packet[1:-1])).address)

            def recv(self, _size: int) -> bytes:
                item = self.chunks.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item

            def close(self) -> None:
                self.closed = True

        first_socket = FakeSocket(succeed=False)
        second_socket = FakeSocket(succeed=True)
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )

        with patch("socket.create_connection", side_effect=[first_socket, second_socket]) as connect:
            with self.assertRaises(OscTimeoutError):
                client.request(action, reply_timeout=0.01)
            self.assertIsNone(client._tcp_socket)
            self.assertEqual(client._tcp_buffer, bytearray())
            self.assertEqual(client._tcp_connected_workspaces, set())
            reply = client.request(action)

        self.assertEqual(reply.data, "fresh")
        self.assertTrue(first_socket.closed)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(first_socket.sent, ["/workspace/ws-1/connect", action])
        self.assertEqual(second_socket.sent, ["/workspace/ws-1/connect", action])
        self.assertLessEqual(first_socket.timeouts[-1], 0.01)

    def test_close_discards_persistent_session(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sock = MagicMock()

        with (
            patch("socket.create_connection", return_value=sock),
            patch.object(
                client,
                "_send_with_reply_on_tcp_socket",
                return_value=type("Reply", (), {"status": "ok", "data": "ok"})(),
            ),
        ):
            client.request("/workspaces")
            client.close()

        sock.close.assert_called_once_with()

    def test_context_manager_closes_persistent_session(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        )
        sock = MagicMock()

        with (
            patch("socket.create_connection", return_value=sock),
            patch.object(
                client,
                "_send_with_reply_on_tcp_socket",
                return_value=type("Reply", (), {"status": "ok", "data": "ok"})(),
            ),
        ):
            with client:
                client.request("/workspaces")

        sock.close.assert_called_once_with()

    def test_concurrent_clients_use_independent_tcp_sessions(self) -> None:
        config = QLabConfig(host="127.0.0.1", osc_port=53000, timeout=0.2, passcode="secret")
        clients = [QLabOscClient(config), QLabOscClient(config)]
        sockets = [MagicMock(), MagicMock()]
        barrier = threading.Barrier(2)
        seen_sockets: list[list[object]] = [[], []]
        errors: list[BaseException] = []

        def send_for(index: int) -> Callable[..., Any]:
            def send(sock: object, address: str, *args: Any, **_kwargs: Any) -> Any:
                seen_sockets[index].append(sock)
                if address.endswith("/showMode"):
                    barrier.wait(timeout=1)
                return type("Reply", (), {"status": "ok", "data": "ok"})()

            return send

        def run(index: int) -> None:
            try:
                clients[index].request("/workspace/ws-1/showMode")
            except BaseException as exc:
                errors.append(exc)

        with (
            patch("socket.create_connection", side_effect=sockets),
            patch.object(clients[0], "_send_with_reply_on_tcp_socket", side_effect=send_for(0)),
            patch.object(clients[1], "_send_with_reply_on_tcp_socket", side_effect=send_for(1)),
        ):
            threads = [threading.Thread(target=run, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual({id(sock) for sock in seen_sockets[0]}, {id(seen_sockets[0][0])})
        self.assertEqual({id(sock) for sock in seen_sockets[1]}, {id(seen_sockets[1][0])})
        self.assertIsNot(seen_sockets[0][0], seen_sockets[1][0])


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
