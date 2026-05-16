from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.allowlist import validate_property_path, validate_value_keys
from qlab_mcp.client import QLabOscClient
from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeCuePropertyError
from qlab_mcp.osc import decode_message, encode_message
from qlab_mcp.qlab import QLabReader


class FakeQlabOscServer:
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.received: list[str] = []
        self.received_args: list[tuple[Any, ...]] = []
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self.port: int | None = None

    def __enter__(self) -> "FakeQlabOscServer":
        self._thread.start()
        if not self._ready.wait(timeout=2):
            raise RuntimeError("Fake QLab OSC server did not start")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b"", ("127.0.0.1", self.port or 0))
        self._thread.join(timeout=2)

    def _serve(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
            sock.settimeout(0.1)
            self._ready.set()

            while not self._stop.is_set():
                try:
                    packet, client_addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                if not packet:
                    continue

                message = decode_message(packet)
                self.received.append(message.address)
                self.received_args.append(message.args)
                response = self.responses.get(message.address)
                if callable(response):
                    response = response(message)
                if response is None:
                    payload = {"status": "error", "data": f"No fake response for {message.address}"}
                elif isinstance(response, dict) and "status" in response:
                    payload = response
                else:
                    payload = {"status": "ok", "data": response, "workspace_id": "ws-1"}

                reply_address = f"/reply/{message.address.lstrip('/')}"
                sock.sendto(encode_message(reply_address, json.dumps(payload)), client_addr)


def client_for(server: FakeQlabOscServer, timeout: float = 0.25) -> QLabOscClient:
    assert server.port is not None
    return QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=server.port, reply_port=0, timeout=timeout))


class QLabReaderTests(unittest.TestCase):
    def test_get_workspaces(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}]
        with FakeQlabOscServer({"/workspaces": workspaces}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspaces()

        self.assertEqual(result["workspaces"], workspaces)
        self.assertEqual(server.received, ["/workspaces"])

    def test_cue_list_uses_workspace_address_and_shallow_variant(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/cueLists/shallow": []}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_lists("ws-1", include_children=False)

        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["cue_lists"], [])
        self.assertEqual(server.received, ["/workspace/ws-1/cueLists/shallow"])

    def test_workspace_cue_ids_use_unique_id_endpoint(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/cueLists/uniqueIDs": ["list-id", "cue-id"]}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_cue_ids("ws-1")

        self.assertEqual(result["cue_count"], 2)
        self.assertEqual(result["cue_ids"], ["list-id", "cue-id"])
        self.assertEqual(server.received, ["/workspace/ws-1/cueLists/uniqueIDs"])

    def test_workspace_cue_ids_flattens_nested_qlab_response(self) -> None:
        qlab_response = [
            {
                "uniqueID": "list-id",
                "cues": [
                    {"uniqueID": "group-id", "cues": [{"uniqueID": "cue-id", "cues": []}]},
                    {"uniqueID": "sibling-id", "cues": []},
                ],
            }
        ]
        with FakeQlabOscServer({"/workspace/ws-1/cueLists/uniqueIDs": qlab_response}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_cue_ids("ws-1")

        self.assertEqual(result["cue_count"], 4)
        self.assertEqual(result["cue_ids"], ["list-id", "group-id", "cue-id", "sibling-id"])

    def test_workspace_cue_inventory_can_return_ids_only(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/cueLists/uniqueIDs": ["list-id", "cue-id"]}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_cue_inventory("ws-1")

        self.assertEqual(result["cue_ids"], ["list-id", "cue-id"])
        self.assertNotIn("cues", result)

    def test_workspace_overview_returns_bounded_first_pass_summary(self) -> None:
        list_id = "11111111-1111-4111-8111-111111111111"
        group_id = "22222222-2222-4222-8222-222222222222"
        cue_id = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {
                    "uniqueID": list_id,
                    "number": "",
                    "name": "Main",
                    "displayName": "Main",
                    "type": "Cue List",
                    "armed": True,
                    "flagged": False,
                    "colorName": "none",
                }
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": [
                {
                    "uniqueID": list_id,
                    "cues": [
                        {"uniqueID": group_id, "cues": [{"uniqueID": cue_id, "cues": []}]},
                    ],
                }
            ],
            f"/workspace/ws-1/cue_id/{list_id}/children/shallow": [
                {
                    "uniqueID": group_id,
                    "name": "Looks",
                    "displayName": "Looks",
                    "type": "Group",
                    "armed": True,
                    "flagged": True,
                    "colorName": "red",
                }
            ],
            f"/workspace/ws-1/cue_id/{group_id}/children/shallow": [
                {
                    "uniqueID": cue_id,
                    "name": "Warm wash",
                    "displayName": "Warm wash",
                    "type": "Light",
                    "armed": False,
                    "flagged": False,
                    "colorName": "blue",
                }
            ],
            "/workspace/ws-1/selectedCues/shallow": [],
            "/workspace/ws-1/runningOrPausedCues/shallow": [],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview(max_depth=2, max_cues=10)

        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["workspace"]["displayName"], "demo.qlab5")
        self.assertEqual(result["cue_count"], 3)
        self.assertEqual(result["stats"]["cue_lists"], 1)
        self.assertEqual(result["stats"]["inspected_cues"], 3)
        self.assertEqual(result["stats"]["types"], {"Cue List": 1, "Group": 1, "Light": 1})
        self.assertEqual(result["stats"]["armed"], 2)
        self.assertEqual(result["stats"]["disarmed"], 1)
        self.assertEqual(result["stats"]["flagged"], 1)
        self.assertFalse(result["limits"]["truncated"])
        self.assertEqual(result["cue_lists"][0]["label"], "Main")
        self.assertEqual(result["cue_lists"][0]["children"][0]["children"][0]["displayName"], "Warm wash")
        self.assertEqual(result["selected_cues"], [])
        self.assertEqual(result["running_cues"], [])

    def test_workspace_overview_marks_depth_truncation(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": "list-id", "name": "Main", "type": "Cue List", "armed": True, "flagged": False}
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": ["list-id", "child-id"],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", max_depth=0, max_cues=10, include_selected_and_running=False)

        self.assertTrue(result["limits"]["truncated"])
        self.assertEqual(result["limits"]["truncation_reasons"], ["max_depth"])
        self.assertTrue(result["cue_lists"][0]["children_truncated"])
        self.assertIsNone(result["selected_cues"])
        self.assertIsNone(result["running_cues"])
        self.assertNotIn("/workspace/ws-1/selectedCues/shallow", server.received)

    def test_workspace_cue_inventory_can_include_basic_details(self) -> None:
        responses = {"/workspace/ws-1/cueLists/uniqueIDs": ["1B11984A-3EBC-4A9C-A004-B9E3AA32DA6B"]}
        cue_id = "1B11984A-3EBC-4A9C-A004-B9E3AA32DA6B"
        for prop, value in {
            "uniqueID": cue_id,
            "number": "10",
            "name": "Intro",
            "displayName": "10 Intro",
            "type": "Audio",
            "armed": True,
            "flagged": False,
            "colorName": "none",
            "notes": "",
        }.items():
            responses[f"/workspace/ws-1/cue_id/{cue_id}/{prop}"] = value

        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_cue_inventory("ws-1", include_details=True)

        self.assertEqual(result["cues"][0]["properties"]["name"], "Intro")

    def test_running_cues_variants(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/runningOrPausedCues/shallow": []}) as server:
            reader = QLabReader(client_for(server))

            reader.get_running_cues("ws-1", include_paused=True, include_children=False)

        self.assertEqual(server.received, ["/workspace/ws-1/runningOrPausedCues/shallow"])

    def test_cue_children_ids_only_shallow(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/cue/10/children/uniqueIDs/shallow": ["child-1"]}) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_children("ws-1", "10", shallow=True, ids_only=True)

        self.assertEqual(result["children"], ["child-1"])
        self.assertEqual(server.received, ["/workspace/ws-1/cue/10/children/uniqueIDs/shallow"])

    def test_cue_uuid_uses_cue_id_address(self) -> None:
        cue_id = "1B11984A-3EBC-4A9C-A004-B9E3AA32DA6B"
        address = f"/workspace/ws-1/cue_id/{cue_id}/name"
        with FakeQlabOscServer({address: "Intro"}) as server:
            reader = QLabReader(client_for(server))

            result = reader.read_cue_property("ws-1", cue_id, "name")

        self.assertEqual(result["value"], "Intro")
        self.assertEqual(server.received, [address])

    def test_basic_cue_details(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/uniqueID": "cue-id",
            "/workspace/ws-1/cue/10/number": "10",
            "/workspace/ws-1/cue/10/name": "Intro",
            "/workspace/ws-1/cue/10/displayName": "10 Intro",
            "/workspace/ws-1/cue/10/type": "Audio",
            "/workspace/ws-1/cue/10/armed": True,
            "/workspace/ws-1/cue/10/flagged": False,
            "/workspace/ws-1/cue/10/colorName": "none",
            "/workspace/ws-1/cue/10/notes": "",
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10")

        self.assertEqual(result["properties"]["name"], "Intro")
        self.assertNotIn("errors", result)

    def test_type_specific_profile_can_read_network_data(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/message": "/device/standby 10",
            "/workspace/ws-1/cue/10/networkPatchName": "LX Console",
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "type_specific")

        self.assertEqual(result["properties"]["message"], "/device/standby 10")
        self.assertEqual(result["properties"]["networkPatchName"], "LX Console")

    def test_read_cue_values_uses_values_for_keys_json_argument(self) -> None:
        def response(message):
            self.assertEqual(json.loads(message.args[0]), ["opacity", "stageName"])
            return {"opacity": 1, "stageName": "Main"}

        with FakeQlabOscServer({"/workspace/ws-1/cue/10/valuesForKeys": response}) as server:
            reader = QLabReader(client_for(server))

            result = reader.read_cue_values("ws-1", "10", ["opacity", "stageName"])

        self.assertEqual(result["values"], {"opacity": 1, "stageName": "Main"})
        self.assertEqual(server.received_args[0][0], '["opacity", "stageName"]')

    def test_denied_reply_raises(self) -> None:
        with FakeQlabOscServer({"/workspace/ws-1/selectedCues": {"status": "denied", "data": "badpass"}}) as server:
            reader = QLabReader(client_for(server))

            with self.assertRaises(QLabReplyError):
                reader.get_selected_cues("ws-1")

    def test_timeout_raises(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            unused_port = sock.getsockname()[1]

        client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=unused_port, reply_port=0, timeout=0.05))

        with self.assertRaises(OscTimeoutError):
            client.request("/workspaces")

    def test_property_allowlist_rejects_actions_and_unknowns(self) -> None:
        self.assertEqual(validate_property_path("/name"), "name")
        for unsafe in ("start", "stop", "go", "panic", "delete", "../name", "unknownThing"):
            with self.assertRaises(UnsafeCuePropertyError):
                validate_property_path(unsafe)

    def test_values_for_keys_rejects_action_like_keys(self) -> None:
        self.assertEqual(validate_value_keys(["opacity", "stageName"]), ["opacity", "stageName"])
        for unsafe in (["start"], ["panic"], ["../name"], ["unknownThing"], []):
            with self.assertRaises(UnsafeCuePropertyError):
                validate_value_keys(unsafe)


if __name__ == "__main__":
    unittest.main()

