from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.client import QLabOscClient
from qlab_mcp.errors import OscProtocolError
from qlab_mcp.osc import decode_message, encode_message


class OscMessageTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
