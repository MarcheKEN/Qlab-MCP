from __future__ import annotations

import json
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.config import QLabConfig
from qlab_mcp.osc.client import QLabOscClient, QLabReply, _slip_decode, _slip_encode
from qlab_mcp.errors import OscProtocolError
from qlab_mcp.osc import decode_message, encode_message


class OscMessageTests(unittest.TestCase):
    def test_encode_accepts_signed_int32_boundaries(self) -> None:
        self.assertEqual(decode_message(encode_message("/value", -2_147_483_648)).args, (-2_147_483_648,))
        self.assertEqual(decode_message(encode_message("/value", 2_147_483_647)).args, (2_147_483_647,))

    def test_encode_rejects_values_outside_osc_wire_ranges(self) -> None:
        with self.assertRaises(OscProtocolError):
            encode_message("/cue/1/number", 2_147_483_648)
        with self.assertRaises(OscProtocolError):
            encode_message("/cue/1/number", 1e39)
        with self.assertRaises(OscProtocolError):
            encode_message("/cue/1/number", float("nan"))
        with self.assertRaises(OscProtocolError):
            encode_message("/cue/1/number", float("inf"))

    def test_encode_decode_roundtrip(self) -> None:
        packet = encode_message("/cue/1/name", "Intro", 3, 1.5, True, False, None)

        message = decode_message(packet)

        self.assertEqual(message.address, "/cue/1/name")
        self.assertEqual(message.args[0], "Intro")
        self.assertEqual(message.args[1], 3)
        self.assertAlmostEqual(message.args[2], 1.5)
        self.assertEqual(message.args[3:], (True, False, None))

    def test_parse_qlab_reply(self) -> None:
        payload = json.dumps({"status": "ok", "data": "Audio", "workspace_id": "ws-1"})
        packet = encode_message("/reply/workspace/ws-1/cue/1/type", payload)

        reply = QLabOscClient._parse_reply(packet)

        self.assertEqual(reply.invoked_address, "workspace/ws-1/cue/1/type")
        self.assertEqual(reply.status, "ok")
        self.assertEqual(reply.data, "Audio")
        self.assertEqual(reply.workspace_id, "ws-1")

    def test_invalid_reply_json_raises_protocol_error(self) -> None:
        packet = encode_message("/reply/workspaces", "{not json")

        with self.assertRaises(OscProtocolError):
            QLabOscClient._parse_reply(packet)

    def test_invalid_utf8_raises_protocol_error(self) -> None:
        with self.assertRaises(OscProtocolError):
            decode_message(b"/reply/\xff\x00\x00\x00\x00")

    def test_unrelated_messages_can_be_ignored_while_waiting_for_reply(self) -> None:
        non_reply = encode_message("/updates/workspace/ws-1", "{}")
        other_reply = encode_message("/reply/workspace/ws-1/cue/2/name", json.dumps({"status": "ok", "data": "Other"}))

        self.assertIsNone(
            QLabOscClient._parse_reply(
                non_reply,
                expected_address="/workspace/ws-1/cue/1/name",
                ignore_unrelated=True,
            )
        )
        self.assertIsNone(
            QLabOscClient._parse_reply(
                other_reply,
                expected_address="/workspace/ws-1/cue/1/name",
                ignore_unrelated=True,
            )
        )

    def test_reply_match_rejects_suffix_only_workspace_addresses(self) -> None:
        reply = QLabReply(
            invoked_address="evil/workspace/ws-1/showMode",
            reply_address="/reply/evil/workspace/ws-1/showMode",
            status="ok",
        )

        self.assertFalse(QLabOscClient._reply_matches(reply, "/workspace/ws-1/showMode"))

    def test_reply_match_allows_workspace_prefix_for_unqualified_request(self) -> None:
        reply = QLabReply(
            invoked_address="workspace/ws-1/cue/1/name",
            reply_address="/reply/workspace/ws-1/cue/1/name",
            status="ok",
        )

        self.assertTrue(QLabOscClient._reply_matches(reply, "/cue/1/name"))

    def test_slip_roundtrip_escapes_reserved_bytes(self) -> None:
        packet = bytes([0x01, 0xC0, 0x02, 0xDB, 0x03])

        framed = _slip_encode(packet)

        self.assertEqual(framed[0], 0xC0)
        self.assertEqual(framed[-1], 0xC0)
        self.assertEqual(_slip_decode(framed[1:-1]), packet)

    def test_udp_connect_cache_does_not_suppress_tcp_connect(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, reply_port=0, timeout=0.05, passcode="secret")
        )
        client._remember_connected_workspace("ws-1", "udp")
        sent: list[tuple[str, tuple[object, ...]]] = []

        def fake_send(sock: object, address: str, *args: object, **_kwargs: object) -> object:
            sent.append((address, args))
            return SimpleNamespace(status="ok", data="ok")

        fake_sock = Mock()
        fake_sock.__enter__ = Mock(return_value=fake_sock)
        fake_sock.__exit__ = Mock(return_value=False)

        with patch("socket.create_connection", return_value=fake_sock):
            with patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=fake_send):
                reply = client.request_tcp("/workspace/ws-1/settings/light/patch", workspace_id="ws-1")

        self.assertEqual(reply.data, "ok")
        self.assertEqual(
            sent,
            [
                ("/workspace/ws-1/connect", ("secret",)),
                ("/workspace/ws-1/settings/light/patch", ()),
            ],
        )

    def test_tcp_request_connects_each_new_socket(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, reply_port=0, timeout=0.05, passcode="secret")
        )
        sent: list[str] = []

        def fake_send(sock: object, address: str, *args: object, **_kwargs: object) -> object:
            sent.append(address)
            return SimpleNamespace(status="ok", data="ok")

        fake_sock = Mock()
        fake_sock.__enter__ = Mock(return_value=fake_sock)
        fake_sock.__exit__ = Mock(return_value=False)

        with patch("socket.create_connection", return_value=fake_sock):
            with patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=fake_send):
                client.request_tcp("/workspace/ws-1/settings/light/patch", workspace_id="ws-1")
                client.request_tcp("/workspace/ws-1/settings/light/patch", workspace_id="ws-1")

        self.assertEqual(sent.count("/workspace/ws-1/connect"), 2)
        self.assertEqual(sent.count("/workspace/ws-1/settings/light/patch"), 2)

    def test_tcp_request_infers_workspace_and_authenticates_each_call(self) -> None:
        client = QLabOscClient(
            QLabConfig(host="127.0.0.1", osc_port=53000, reply_port=0, timeout=0.05, passcode="secret")
        )
        sent: list[str] = []

        def fake_send(sock: object, address: str, *args: object, **_kwargs: object) -> object:
            sent.append(address)
            return SimpleNamespace(status="ok", data="ok")

        fake_sock = Mock()
        fake_sock.__enter__ = Mock(return_value=fake_sock)
        fake_sock.__exit__ = Mock(return_value=False)

        with patch("socket.create_connection", return_value=fake_sock):
            with patch.object(client, "_send_with_reply_on_tcp_socket", side_effect=fake_send):
                client.request_tcp("/workspace/ws-1/settings/light/patch")
                client.request_tcp("/workspace/ws-1/settings/light/patch")

        self.assertEqual(sent.count("/workspace/ws-1/connect"), 2)
        self.assertEqual(sent.count("/workspace/ws-1/settings/light/patch"), 2)


if __name__ == "__main__":
    unittest.main()
