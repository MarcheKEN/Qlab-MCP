from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.allowlist import properties_for_profile, validate_property_path, validate_value_keys
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
        self.received_client_ports: list[int] = []
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
                self.received_client_ports.append(client_addr[1])
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

    def test_check_connection_ready_when_workspace_is_readable(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "version": "5.5.10"}]
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-1", "name": "Main"}],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["qlab_reachable"])
        self.assertTrue(result["workspace_available"])
        self.assertTrue(result["workspace_readable"])
        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["workspace_name"], "demo.qlab5")
        self.assertEqual(result["qlab_version"], "5.5.10")
        self.assertEqual(len(result["available_workspaces"]), 1)
        self.assertEqual(result["available_workspaces"][0]["uniqueID"], "ws-1")
        self.assertEqual(result["available_workspaces"][0]["name"], "demo.qlab5")
        self.assertEqual(result["checks"]["read_access"]["cue_list_count"], 1)
        self.assertEqual(result["connection"]["transport"], "udp")
        self.assertTrue(result["capabilities"]["list_workspaces"])
        self.assertTrue(result["capabilities"]["resolve_workspace"])
        self.assertTrue(result["capabilities"]["workspace_overview"])
        self.assertTrue(result["capabilities"]["query_cues"])
        self.assertTrue(result["capabilities"]["cue_details"])
        self.assertIsNone(result["capabilities"]["edit"])
        self.assertIsNone(result["capabilities"]["control"])
        self.assertTrue(result["permissions"]["view"]["ok"])
        self.assertEqual(result["permissions"]["view"]["status"], "confirmed")
        self.assertTrue(result["permissions"]["view"]["safe_to_probe"])
        self.assertIsNone(result["permissions"]["edit"]["ok"])
        self.assertIsNone(result["permissions"]["control"]["ok"])
        self.assertFalse(result["permissions"]["edit"]["safe_to_probe"])
        self.assertFalse(result["permissions"]["control"]["safe_to_probe"])
        self.assertIn("Edit and control permissions", result["warnings"][0])
        self.assertEqual(server.received, ["/workspaces", "/workspace/ws-1/cueLists/shallow"])

    def test_check_connection_reports_no_workspace(self) -> None:
        with FakeQlabOscServer({"/workspaces": []}) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "no_workspace")
        self.assertTrue(result["qlab_reachable"])
        self.assertFalse(result["workspace_available"])
        self.assertEqual(result["workspace_count"], 0)
        self.assertEqual(result["available_workspaces"], [])
        self.assertTrue(result["capabilities"]["list_workspaces"])
        self.assertFalse(result["capabilities"]["resolve_workspace"])
        self.assertIsNone(result["permissions"]["view"]["ok"])

    def test_check_connection_reports_ambiguous_workspace(self) -> None:
        workspaces = [
            {"uniqueID": "ws-1", "displayName": "one.qlab5"},
            {"uniqueID": "ws-2", "displayName": "two.qlab5"},
        ]
        with FakeQlabOscServer({"/workspaces": workspaces}) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_ambiguous")
        self.assertTrue(result["workspace_available"])
        self.assertEqual(result["workspace_count"], 2)
        self.assertEqual(
            [workspace["uniqueID"] for workspace in result["available_workspaces"]],
            ["ws-1", "ws-2"],
        )
        self.assertTrue(result["capabilities"]["list_workspaces"])
        self.assertFalse(result["capabilities"]["resolve_workspace"])

    def test_check_connection_reports_requested_workspace_not_found(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        with FakeQlabOscServer({"/workspaces": workspaces}) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection(workspace_id="missing-workspace")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_not_found")
        self.assertFalse(result["workspace_available"])
        self.assertEqual(result["workspace_count"], 1)
        self.assertEqual(result["available_workspaces"][0]["uniqueID"], "ws-1")
        self.assertFalse(result["capabilities"]["resolve_workspace"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_check_connection_can_skip_read_access(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        with FakeQlabOscServer({"/workspaces": workspaces}) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection(require_read_access=False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["workspace_readable"])
        self.assertTrue(result["checks"]["read_access"]["skipped"])
        self.assertEqual(result["permissions"]["view"]["status"], "skipped")
        self.assertTrue(result["capabilities"]["resolve_workspace"])
        self.assertFalse(result["capabilities"]["read_workspace"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_check_connection_reports_denied_workspace_read(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": {"status": "denied", "data": "badpass"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_denied")
        self.assertEqual(result["passcode_status"], "denied")
        self.assertFalse(result["workspace_readable"])
        self.assertEqual(result["checks"]["read_access"]["status"], "denied")
        self.assertFalse(result["permissions"]["view"]["ok"])
        self.assertEqual(result["permissions"]["view"]["status"], "denied")
        self.assertFalse(result["capabilities"]["read_workspace"])

    def test_check_connection_reports_unreachable_qlab(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            unused_port = sock.getsockname()[1]

        client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=unused_port, reply_port=0, timeout=0.05))
        reader = QLabReader(client)

        result = reader.check_connection()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "qlab_unreachable")
        self.assertFalse(result["qlab_reachable"])
        self.assertIn("Timed out", result["checks"]["workspaces"]["error"])

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
            "/workspaces": [
                {
                    "uniqueID": "ws-1",
                    "displayName": "demo.qlab5",
                    "applicationVersion": "5.5.10",
                    "port": 53000,
                }
            ],
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
                    "number": "1",
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
                    "number": "1.1",
                    "name": "Warm wash",
                    "displayName": "Warm wash",
                    "type": "Light",
                    "armed": False,
                    "flagged": False,
                    "colorName": "blue",
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview(max_depth=2, max_cues=10)

        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["workspace"]["name"], "demo.qlab5")
        self.assertEqual(result["workspace"]["qlab_version"], "5.5.10")
        self.assertEqual(result["cue_count"], 3)
        self.assertEqual(result["summary"]["cue_lists"], 1)
        self.assertEqual(result["summary"]["inspected_cues"], 3)
        self.assertEqual(result["summary"]["types"], {"Cue List": 1, "Group": 1, "Light": 1})
        self.assertEqual(result["summary"]["armed"], 2)
        self.assertEqual(result["summary"]["disarmed"], 1)
        self.assertEqual(result["summary"]["flagged"], 1)
        self.assertFalse(result["limits"]["truncated"])
        self.assertEqual(result["cue_lists"][0]["label"], "Main")
        self.assertEqual(result["cue_lists"][0]["child_count"], 1)
        self.assertEqual(result["cue_lists"][0]["children"][0]["number"], "1")
        self.assertEqual(result["cue_lists"][0]["children"][0]["child_count"], 1)
        self.assertEqual(result["cue_lists"][0]["children"][0]["children"][0]["number"], "1.1")
        self.assertEqual(result["cue_lists"][0]["children"][0]["children"][0]["child_count"], 0)
        self.assertEqual(result["cue_lists"][0]["children"][0]["children"][0]["displayName"], "Warm wash")
        self.assertNotIn("selected_cues", result)
        self.assertNotIn("running_cues", result)
        self.assertNotIn("live_state", result)
        self.assertNotIn("/workspace/ws-1/selectedCues/shallow", server.received)

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

            result = reader.get_workspace_overview("ws-1", max_depth=0, max_cues=10)

        self.assertTrue(result["limits"]["truncated"])
        self.assertEqual(result["limits"]["truncation_reasons"], ["max_depth"])
        self.assertTrue(result["cue_lists"][0]["children_truncated"])
        self.assertNotIn("selected_cues", result)
        self.assertNotIn("running_cues", result)
        self.assertNotIn("live_state", result)
        self.assertNotIn("/workspace/ws-1/selectedCues/shallow", server.received)

    def test_workspace_overview_marks_max_cues_truncation(self) -> None:
        list_1 = "11111111-1111-4111-8111-111111111111"
        list_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": list_1, "name": "Main", "type": "Cue List", "armed": True, "flagged": False},
                {"uniqueID": list_2, "name": "Backup", "type": "Cue List", "armed": True, "flagged": False},
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": [list_1, list_2],
            f"/workspace/ws-1/cue_id/{list_1}/children/shallow": [],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", max_depth=2, max_cues=1)

        self.assertTrue(result["limits"]["truncated"])
        self.assertEqual(result["limits"]["truncation_reasons"], ["max_cues"])
        self.assertEqual(result["summary"]["inspected_cues"], 1)
        self.assertEqual(len(result["cue_lists"]), 1)

    def test_workspace_overview_can_include_live_state_when_requested(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": [],
            "/workspace/ws-1/selectedCues/shallow": [{"uniqueID": "selected-id", "type": "Audio"}],
            "/workspace/ws-1/runningOrPausedCues/shallow": [{"uniqueID": "running-id", "type": "Video"}],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", include_live_state=True)

        self.assertEqual(result["live_state"]["selected_cues"][0]["uniqueID"], "selected-id")
        self.assertEqual(result["live_state"]["running_cues"][0]["uniqueID"], "running-id")
        self.assertTrue(result["live_state"]["running_includes_paused"])
        self.assertIn("/workspace/ws-1/selectedCues/shallow", server.received)

    def test_workspace_overview_labels_cues_without_visible_name(self) -> None:
        list_id = "11111111-1111-4111-8111-111111111111"
        cue_id = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": list_id, "name": "Main", "type": "Cue List", "armed": True, "flagged": False}
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": [list_id, cue_id],
            f"/workspace/ws-1/cue_id/{list_id}/children/shallow": [
                {"uniqueID": cue_id, "number": "10", "type": "Audio", "armed": True, "flagged": False}
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", max_depth=1, max_cues=10)

        self.assertEqual(result["cue_lists"][0]["children"][0]["label"], "10")

    def test_workspace_cue_inventory_can_include_basic_details(self) -> None:
        cue_id = "1B11984A-3EBC-4A9C-A004-B9E3AA32DA6B"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_id],
            f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                "uniqueID": cue_id,
                "number": "10",
                "name": "Intro",
                "displayName": "10 Intro",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
        }

        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_cue_inventory("ws-1", include_details=True)

        self.assertEqual(result["cues"][0]["properties"]["name"], "Intro")
        self.assertEqual(server.received, ["/workspace/ws-1/cueLists/uniqueIDs", f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"])

    def test_query_cues_filters_by_type(self) -> None:
        list_id = "11111111-1111-4111-8111-111111111111"
        audio_id = "22222222-2222-4222-8222-222222222222"
        video_id = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [
                {
                    "uniqueID": list_id,
                    "cues": [{"uniqueID": audio_id, "cues": []}, {"uniqueID": video_id, "cues": []}],
                }
            ],
            f"/workspace/ws-1/cue_id/{list_id}/valuesForKeys": {
                "uniqueID": list_id,
                "number": "",
                "name": "Main",
                "displayName": "Main",
                "type": "Cue List",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
            f"/workspace/ws-1/cue_id/{audio_id}/valuesForKeys": {
                "uniqueID": audio_id,
                "number": "1",
                "name": "Intro",
                "displayName": "1 Intro",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "green",
            },
            f"/workspace/ws-1/cue_id/{video_id}/valuesForKeys": {
                "uniqueID": video_id,
                "number": "2",
                "name": "Projection",
                "displayName": "2 Projection",
                "type": "Video",
                "armed": True,
                "flagged": True,
                "colorName": "red",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues("ws-1", "type", "Audio")

        self.assertEqual(result["scanned_count"], 3)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["returned_count"], 1)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["cues"][0]["uniqueID"], audio_id)
        self.assertEqual(result["cues"][0]["cue_list_id"], list_id)
        self.assertEqual(server.received[0], "/workspace/ws-1/cueLists/uniqueIDs")

    def test_query_cues_combines_filters_with_and(self) -> None:
        audio_1 = "11111111-1111-4111-8111-111111111111"
        audio_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [audio_1, audio_2],
            f"/workspace/ws-1/cue_id/{audio_1}/valuesForKeys": {
                "uniqueID": audio_1,
                "number": "A1",
                "name": "Intro clean",
                "displayName": "A1 Intro clean",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
            f"/workspace/ws-1/cue_id/{audio_2}/valuesForKeys": {
                "uniqueID": audio_2,
                "number": "A2",
                "name": "Intro flagged",
                "displayName": "A2 Intro flagged",
                "type": "Audio",
                "armed": True,
                "flagged": True,
                "colorName": "red",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues(
                "ws-1",
                "type",
                "Audio",
                optional_filters=[{"filter": "flagged", "value": True}],
            )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["cues"][0]["uniqueID"], audio_2)
        self.assertEqual(result["filters"], [{"filter": "type", "value": "Audio"}, {"filter": "flagged", "value": True}])

    def test_query_cues_supports_text_and_color_filters(self) -> None:
        light_1 = "11111111-1111-4111-8111-111111111111"
        light_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [light_1, light_2],
            f"/workspace/ws-1/cue_id/{light_1}/valuesForKeys": {
                "uniqueID": light_1,
                "number": "LX-1",
                "name": "Warm wash",
                "displayName": "LX-1 Warm wash",
                "type": "Light",
                "armed": True,
                "flagged": False,
                "colorName": "blue",
            },
            f"/workspace/ws-1/cue_id/{light_2}/valuesForKeys": {
                "uniqueID": light_2,
                "number": "SFX-1",
                "name": "Cold hit",
                "displayName": "SFX-1 Cold hit",
                "type": "Light",
                "armed": True,
                "flagged": False,
                "colorName": "red",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues(
                "ws-1",
                "name_contains",
                "warm",
                optional_filters=[
                    {"filter": "number_prefix", "value": "LX"},
                    {"filter": "colorName", "value": "blue"},
                ],
            )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["cues"][0]["uniqueID"], light_1)

    def test_query_cues_no_results_is_not_an_error(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_id],
            f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                "uniqueID": cue_id,
                "number": "1",
                "name": "Intro",
                "displayName": "1 Intro",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues("ws-1", "type", "Light")

        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(result["cues"], [])
        self.assertIsNone(result["errors"])

    def test_query_cues_respects_result_and_scan_limits(self) -> None:
        cue_1 = "11111111-1111-4111-8111-111111111111"
        cue_2 = "22222222-2222-4222-8222-222222222222"
        cue_3 = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_1, cue_2, cue_3],
            f"/workspace/ws-1/cue_id/{cue_1}/valuesForKeys": {
                "uniqueID": cue_1,
                "number": "1",
                "name": "One",
                "displayName": "1 One",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
            f"/workspace/ws-1/cue_id/{cue_2}/valuesForKeys": {
                "uniqueID": cue_2,
                "number": "2",
                "name": "Two",
                "displayName": "2 Two",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
            f"/workspace/ws-1/cue_id/{cue_3}/valuesForKeys": {
                "uniqueID": cue_3,
                "number": "3",
                "name": "Three",
                "displayName": "3 Three",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result_limit = reader.query_cues("ws-1", "type", "Audio", max_results=1)
            scan_limit = reader.query_cues("ws-1", "type", "Audio", max_cues_scanned=2)

        self.assertEqual(result_limit["matched_count"], 3)
        self.assertEqual(result_limit["returned_count"], 1)
        self.assertTrue(result_limit["truncated"])
        self.assertEqual(scan_limit["scanned_count"], 2)
        self.assertEqual(scan_limit["total_cue_ids"], 3)
        self.assertTrue(scan_limit["truncated"])

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
        responses = {"/workspace/ws-1/cue/10/valuesForKeys": {"uniqueID": "cue-id", "number": "10", "name": "Intro"}}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10")

        self.assertEqual(result["properties"]["name"], "Intro")
        self.assertNotIn("errors", result)
        self.assertEqual(server.received, ["/workspace/ws-1/cue/10/valuesForKeys"])

    def test_cue_details_falls_back_to_individual_properties_when_batch_fails(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {"status": "error", "data": "values unavailable"},
            "/workspace/ws-1/cue/10/uniqueID": "cue-id",
            "/workspace/ws-1/cue/10/number": "10",
            "/workspace/ws-1/cue/10/name": "Intro",
            "/workspace/ws-1/cue/10/displayName": "10 Intro",
            "/workspace/ws-1/cue/10/type": "Audio",
            "/workspace/ws-1/cue/10/armed": True,
            "/workspace/ws-1/cue/10/flagged": False,
            "/workspace/ws-1/cue/10/colorName": "none",
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "basic_safe")

        self.assertEqual(result["properties"]["name"], "Intro")
        self.assertIn("valuesForKeys", result["errors"])
        self.assertIn("/workspace/ws-1/cue/10/name", server.received)

    def test_type_specific_profile_can_read_network_data(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "message": "/device/standby 10",
                "networkPatchName": "LX Console",
            },
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

    def test_passcode_connect_and_request_share_udp_socket(self) -> None:
        responses = {
            "/workspace/ws-1/connect": [],
            "/workspace/ws-1/selectedCues/shallow": [],
        }
        with FakeQlabOscServer(responses) as server:
            assert server.port is not None
            config = QLabConfig(
                host="127.0.0.1",
                osc_port=server.port,
                reply_port=0,
                timeout=0.25,
                passcode="5983",
            )
            reader = QLabReader(QLabOscClient(config))

            result = reader.get_selected_cues("ws-1", include_children=False)

        self.assertEqual(result["selected_cues"], [])
        self.assertEqual(server.received, ["/workspace/ws-1/connect", "/workspace/ws-1/selectedCues/shallow"])
        self.assertEqual(server.received_args[0], ("5983",))
        self.assertEqual(len(set(server.received_client_ports)), 1)

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

    def test_detail_profiles_separate_safe_technical_health_and_sensitive_keys(self) -> None:
        self.assertNotIn("notes", properties_for_profile("basic_safe"))
        self.assertNotIn("fileTarget", properties_for_profile("basic_safe"))
        self.assertIn("fileTarget", properties_for_profile("technical"))
        self.assertIn("isBroken", properties_for_profile("health"))
        self.assertNotIn("notes", properties_for_profile("full"))
        self.assertNotIn("fileTarget", properties_for_profile("full"))
        self.assertNotIn("scriptSource", properties_for_profile("full"))
        self.assertIn("notes", properties_for_profile("full_sensitive"))
        self.assertIn("fileTarget", properties_for_profile("full_sensitive"))
        self.assertIn("scriptSource", properties_for_profile("full_sensitive"))

    def test_values_for_keys_rejects_action_like_keys(self) -> None:
        self.assertEqual(validate_value_keys(["opacity", "stageName"]), ["opacity", "stageName"])
        for unsafe in (["start"], ["panic"], ["../name"], ["unknownThing"], []):
            with self.assertRaises(UnsafeCuePropertyError):
                validate_value_keys(unsafe)


if __name__ == "__main__":
    unittest.main()

