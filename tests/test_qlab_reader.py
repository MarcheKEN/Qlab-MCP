from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qlab_mcp.allowlist import properties_for_profile, validate_property_path, validate_value_keys
from qlab_mcp.osc.client import QLabOscClient
from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeCuePropertyError
from qlab_mcp.osc import decode_message, encode_message
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache


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
    def setUp(self) -> None:
        shared_read_cache().clear()

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

    def test_read_cache_reuses_workspace_cue_ids_between_overview_and_query(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"

        class CountingClient:
            config = QLabConfig(cache_ttl=10)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                responses = {
                    "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
                    "/workspace/ws-1/cueLists/shallow": [],
                    "/workspace/ws-1/cueLists/uniqueIDs": [cue_id],
                    f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                        "uniqueID": cue_id,
                        "number": "1",
                        "name": "Intro",
                        "displayName": "1 Intro",
                        "listName": "Main",
                        "type": "Audio",
                        "armed": True,
                        "flagged": False,
                        "colorName": "none",
                    },
                }
                return SimpleNamespace(data=responses[address], status="ok")

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        reader.get_workspace_overview("ws-1", include_cue_index=False)
        reader.query_cues("ws-1", "type", "Audio")

        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/uniqueIDs"), 1)

    def test_read_cache_can_be_disabled_with_zero_ttl(self) -> None:
        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                return SimpleNamespace(data=["cue-id"], status="ok")

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        reader.get_workspace_cue_ids("ws-1")
        reader.get_workspace_cue_ids("ws-1")

        self.assertEqual(client.requests, ["/workspace/ws-1/cueLists/uniqueIDs", "/workspace/ws-1/cueLists/uniqueIDs"])

    def test_read_cache_bypasses_live_state_and_sensitive_profiles(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"

        class CountingClient:
            config = QLabConfig(cache_ttl=10)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[], status="ok")
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=[cue_id], status="ok")
                if address in {"/workspace/ws-1/selectedCues/shallow", "/workspace/ws-1/runningOrPausedCues/shallow"}:
                    return SimpleNamespace(data=[], status="ok")
                return SimpleNamespace(
                    data={
                        "uniqueID": cue_id,
                        "number": "1",
                        "name": "Intro",
                        "displayName": "1 Intro",
                        "type": "Audio",
                        "notes": "private note",
                        "fileTarget": "/private/media.wav",
                    },
                    status="ok",
                )

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        reader.get_workspace_overview("ws-1", include_live_state=True, include_cue_index=False)
        reader.get_workspace_overview("ws-1", include_live_state=True, include_cue_index=False)
        reader.get_cue_details("ws-1", cue_id, "technical")
        reader.get_cue_details("ws-1", cue_id, "technical")

        self.assertEqual(client.requests.count("/workspace/ws-1/selectedCues/shallow"), 2)
        self.assertEqual(client.requests.count("/workspace/ws-1/runningOrPausedCues/shallow"), 2)
        self.assertEqual(client.requests.count(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"), 2)

    def test_query_cues_bypasses_cache_for_live_state_filters(self) -> None:
        shared_read_cache().clear()
        cue_id = "11111111-1111-4111-8111-111111111111"

        class CountingClient:
            config = QLabConfig(cache_ttl=10)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=[cue_id], status="ok")
                return SimpleNamespace(
                    data={
                        "uniqueID": cue_id,
                        "number": "1",
                        "name": "Intro",
                        "displayName": "1 Intro",
                        "listName": "Main",
                        "type": "Audio",
                        "armed": True,
                        "flagged": False,
                        "colorName": "none",
                        "isRunning": True,
                    },
                    status="ok",
                )

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        reader.query_cues("ws-1", "isRunning", True)
        reader.query_cues("ws-1", "isRunning", True)

        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/uniqueIDs"), 2)
        self.assertEqual(client.requests.count(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"), 2)

    def test_active_cue_details_bypass_cache(self) -> None:
        shared_read_cache().clear()

        class CountingClient:
            config = QLabConfig(cache_ttl=10)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                return SimpleNamespace(
                    data={
                        "uniqueID": "active-id",
                        "number": "1",
                        "name": "Active",
                        "displayName": "1 Active",
                        "listName": "Main",
                        "type": "Audio",
                        "armed": True,
                        "flagged": False,
                        "colorName": "none",
                    },
                    status="ok",
                )

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        reader.get_cue_details("ws-1", "active", "auto")
        reader.get_cue_details("ws-1", "active", "auto")

        self.assertEqual(client.requests.count("/workspace/ws-1/cue/active/valuesForKeys"), 4)

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

    def test_workspace_overview_includes_complete_cue_index_when_tree_is_truncated(self) -> None:
        list_id = "11111111-1111-4111-8111-111111111111"
        group_id = "22222222-2222-4222-8222-222222222222"
        cue_id = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": list_id, "name": "Main", "type": "Cue List", "armed": True, "flagged": False}
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": [
                {"uniqueID": list_id, "cues": [{"uniqueID": group_id, "cues": [{"uniqueID": cue_id, "cues": []}]}]}
            ],
            f"/workspace/ws-1/cue_id/{list_id}/valuesForKeys": {
                "uniqueID": list_id,
                "number": "",
                "name": "Main",
                "displayName": "Main",
                "type": "Cue List",
                "listName": "Main",
                "armed": True,
                "flagged": False,
                "colorName": "none",
                "isBroken": False,
                "isWarning": False,
                "continueMode": 0,
            },
            f"/workspace/ws-1/cue_id/{group_id}/valuesForKeys": {
                "uniqueID": group_id,
                "number": "1",
                "name": "Looks",
                "displayName": "Looks",
                "type": "Group",
                "listName": "Looks",
                "armed": True,
                "flagged": False,
                "colorName": "red",
                "isBroken": False,
                "isWarning": False,
                "continueMode": 1,
            },
            f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                "uniqueID": cue_id,
                "number": "1.1",
                "name": "Warm wash",
                "displayName": "Warm wash",
                "type": "Light",
                "listName": "Warm wash",
                "armed": False,
                "flagged": True,
                "colorName": "blue",
                "isBroken": True,
                "isWarning": False,
                "continueMode": 2,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview(
                "ws-1",
                max_depth=0,
                max_cues=1,
                max_index_cues=10,
                cue_index_profile="health",
            )

        self.assertTrue(result["limits"]["truncated"])
        self.assertEqual(len(result["cue_lists"]), 1)
        self.assertEqual(result["cue_index"]["profile"], "health")
        self.assertEqual(result["cue_index"]["columns"], [
            "uniqueID",
            "number",
            "name",
            "displayName",
            "type",
            "listName",
            "cue_list_id",
            "parent_id",
            "depth",
            "armed",
            "flagged",
            "colorName",
            "isBroken",
            "isWarning",
            "continueMode",
            "continueModeLabel",
        ])
        self.assertEqual(result["cue_index"]["total_cue_ids"], 3)
        self.assertEqual(result["cue_index"]["indexed_count"], 3)
        self.assertFalse(result["cue_index"]["truncated"])
        self.assertIsNone(result["cue_index"]["errors"])
        self.assertEqual(
            result["cue_index"]["rows"],
            [
                [list_id, "", "Main", "Main", "Cue List", "Main", list_id, None, 0, True, False, "none", False, False, 0, "do_not_continue"],
                [group_id, "1", "Looks", "Looks", "Group", "Looks", list_id, list_id, 1, True, False, "red", False, False, 1, "auto_continue"],
                [cue_id, "1.1", "Warm wash", "Warm wash", "Light", "Warm wash", list_id, group_id, 2, False, True, "blue", True, False, 2, "auto_follow"],
            ],
        )
        self.assertEqual(result["editorial_health"]["source"], "cue_index")
        self.assertEqual(result["editorial_health"]["inspected_cues"], 3)
        self.assertEqual(result["editorial_health"]["number_empty"]["count"], 1)
        self.assertEqual(result["editorial_health"]["ambiguous_label"]["count"], 0)

    def test_workspace_overview_cue_index_minimal_profile_is_default(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_id],
            f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                "uniqueID": cue_id,
                "number": "1",
                "name": "Intro",
                "displayName": "1 Intro",
                "type": "Audio",
                "listName": "Main",
                "armed": False,
                "isBroken": True,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1")

        self.assertEqual(result["cue_index"]["profile"], "minimal")
        self.assertEqual(
            result["cue_index"]["columns"],
            ["uniqueID", "number", "name", "displayName", "type", "listName", "cue_list_id", "parent_id", "depth"],
        )
        self.assertEqual(result["cue_index"]["rows"], [[cue_id, "1", "Intro", "1 Intro", "Audio", "Main", None, None, 0]])
        self.assertEqual(result["editorial_health"]["name_empty"]["count"], 0)
        self.assertEqual(
            json.loads(server.received_args[-1][0]),
            ["uniqueID", "number", "name", "displayName", "type", "listName"],
        )

    def test_workspace_overview_editorial_health_finds_empty_duplicate_and_ambiguous_labels(self) -> None:
        cue_1 = "11111111-1111-4111-8111-111111111111"
        cue_2 = "22222222-2222-4222-8222-222222222222"
        cue_3 = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_1, cue_2, cue_3],
            f"/workspace/ws-1/cue_id/{cue_1}/valuesForKeys": {
                "uniqueID": cue_1,
                "number": "",
                "name": "",
                "displayName": "",
                "type": "Audio",
                "listName": "Main",
            },
            f"/workspace/ws-1/cue_id/{cue_2}/valuesForKeys": {
                "uniqueID": cue_2,
                "number": "1",
                "name": "Hit",
                "displayName": "Hit",
                "type": "Audio",
                "listName": "Main",
            },
            f"/workspace/ws-1/cue_id/{cue_3}/valuesForKeys": {
                "uniqueID": cue_3,
                "number": "1",
                "name": "Hit",
                "displayName": "¿?",
                "type": "Audio",
                "listName": "Main",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1")

        editorial = result["editorial_health"]
        self.assertEqual(editorial["name_empty"]["count"], 1)
        self.assertEqual(editorial["displayName_empty"]["count"], 1)
        self.assertEqual(editorial["number_empty"]["count"], 1)
        self.assertEqual(editorial["ambiguous_label"]["count"], 1)
        self.assertEqual(editorial["duplicate_names"]["group_count"], 1)
        self.assertEqual(editorial["duplicate_names"]["cue_count"], 2)
        self.assertEqual(editorial["duplicate_numbers"]["group_count"], 1)

    def test_workspace_overview_marks_cue_index_truncation(self) -> None:
        cue_1 = "11111111-1111-4111-8111-111111111111"
        cue_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_1, cue_2],
            f"/workspace/ws-1/cue_id/{cue_1}/valuesForKeys": {
                "uniqueID": cue_1,
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "isBroken": False,
                "isWarning": False,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", max_index_cues=1)

        self.assertTrue(result["cue_index"]["truncated"])
        self.assertEqual(result["cue_index"]["total_cue_ids"], 2)
        self.assertEqual(result["cue_index"]["indexed_count"], 1)

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
        self.assertIn("Tree preview is partial (max_depth)", result["warnings"][0])
        self.assertIn("cue_index", result["warnings"][0])
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

    def test_workspace_settings_safe_reads_selected_sections_and_redacts_destinations(self) -> None:
        responses = {
            "/workspace/ws-1/settings/video/inputPatchList": [
                {"name": "Camera 1", "uniqueID": "input-1", "deviceName": "ATEM"}
            ],
            "/workspace/ws-1/settings/video/routes": [
                {
                    "name": "Projector",
                    "uniqueID": "route-1",
                    "size": {"width": 1920, "height": 1080},
                    "connected": False,
                    "destinationInfo": {
                        "destinationType": "Display",
                        "screenSerialNumber": "SECRET-SERIAL",
                        "deckLinkHandle": "SECRET-HANDLE",
                    },
                }
            ],
            "/workspace/ws-1/settings/video/stages": [
                {"name": "Main Stage", "uniqueID": "stage-1", "size": {"width": 1920, "height": 1080}}
            ],
            "/workspace/ws-1/settings/video/stageID/stage-1/regions": [
                {"name": "A", "uniqueID": "region-1"}
            ],
            "/workspace/ws-1/settings/network/patchList": [
                {
                    "name": "EOS",
                    "uniqueID": "network-1",
                    "type": "OSC",
                    "destinations": [
                        {"ipAddress": "192.168.1.50", "port": 8000, "passcode": "1234"}
                    ],
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings("ws-1", sections=["network", "video"])

        self.assertEqual(result["profile"], "safe")
        self.assertEqual(set(result["sections"]), {"video", "network"})
        self.assertEqual(result["summary"]["video_route_count"], 1)
        self.assertEqual(result["summary"]["video_stage_count"], 1)
        self.assertEqual(result["summary"]["network_patch_count"], 1)
        self.assertTrue(result["sections"]["video"]["routes"][0]["destination_present"])
        self.assertFalse(result["sections"]["video"]["routes"][0]["connected"])
        self.assertEqual(result["sections"]["video"]["routes"][0]["attention"]["status"], "disconnected")
        self.assertEqual(result["sections"]["video"]["stages"][0]["region_count"], 1)
        self.assertTrue(result["sections"]["network"]["patches"][0]["destination_present"])
        self.assertTrue(result["sections"]["network"]["patches"][0]["passcode_present"])
        serialized = json.dumps(result)
        self.assertNotIn("192.168.1.50", serialized)
        self.assertNotIn("8000", serialized)
        self.assertNotIn("SECRET-SERIAL", serialized)
        self.assertNotIn("SECRET-HANDLE", serialized)
        self.assertNotIn("1234", serialized)
        self.assertTrue(all("impact" in redaction for redaction in result["redactions"]))
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/video/inputPatchList",
                "/workspace/ws-1/settings/video/routes",
                "/workspace/ws-1/settings/video/stages",
                "/workspace/ws-1/settings/video/stageID/stage-1/regions",
                "/workspace/ws-1/settings/network/patchList",
            ],
        )

    def test_workspace_setting_details_technical_keeps_network_details_but_redacts_passcodes(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {
                    "name": "QLab Loopback",
                    "uniqueID": "network-1",
                    "destinations": [
                        {"ipAddress": "127.0.0.1", "port": 53000, "passcode": "9999"}
                    ],
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details(
                "ws-1",
                section="network",
                kind="network_patch",
                ref="QLab Loopback",
                profile="technical",
            )

        serialized = json.dumps(result)
        self.assertIn("127.0.0.1", serialized)
        self.assertIn("53000", serialized)
        self.assertNotIn("9999", serialized)
        self.assertEqual(result["details"]["destinations"][0]["passcode"], "[redacted]")
        self.assertEqual(result["redactions"][0]["reason"], "credential")
        self.assertIn("credential", result["redactions"][0]["impact"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_settings_overview_skips_light_patch(self) -> None:
        responses = {
            "/workspace/ws-1/settings/general/minGoTime": 0.4,
            "/workspace/ws-1/settings/general/selectionIsPlayhead": True,
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings("ws-1", sections=["light", "general"])

        self.assertEqual(result["sections"]["general"]["minGoTime"], 0.4)
        self.assertTrue(result["sections"]["general"]["selectionIsPlayhead"])
        self.assertEqual(result["sections"]["light"]["summary"]["details_available"], True)
        self.assertEqual(result["sections"]["light"]["summary"]["patch_read"], "skipped")
        self.assertIsNone(result["errors"])
        self.assertEqual(result["summary"]["error_count"], 0)
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/general/minGoTime",
                "/workspace/ws-1/settings/general/selectionIsPlayhead",
            ],
        )

    def test_workspace_setting_details_video_stage_returns_regions_and_route(self) -> None:
        responses = {
            "/workspace/ws-1/settings/video/stages": [
                {"name": "Main Stage", "uniqueID": "stage-1", "width": 1920, "height": 1080}
            ],
            "/workspace/ws-1/settings/video/stageID/stage-1/regions": [
                {
                    "name": "A",
                    "uniqueID": "region-1",
                    "boundsOnStage": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                    "route": {
                        "name": "Projector",
                        "uniqueID": "route-1",
                        "connected": False,
                        "destinationInfo": {"destinationType": "Display", "screenSerialNumber": "SERIAL"},
                    },
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details(
                "ws-1",
                section="video",
                kind="stage",
                ref="Main Stage",
                profile="technical",
            )

        self.assertEqual(result["section"], "video")
        self.assertEqual(result["kind"], "stage")
        self.assertEqual(result["details"]["stage"]["uniqueID"], "stage-1")
        self.assertEqual(result["details"]["regions"][0]["route"]["destinationInfo"]["screenSerialNumber"], "SERIAL")
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/video/stages",
                "/workspace/ws-1/settings/video/stageID/stage-1/regions",
            ],
        )

    def test_workspace_setting_details_video_route_returns_destination_info(self) -> None:
        responses = {
            "/workspace/ws-1/settings/video/routes": [
                {
                    "name": "Projector",
                    "uniqueID": "route-1",
                    "connected": False,
                    "destinationInfo": {"destinationType": "Display", "screenSerialNumber": "SERIAL"},
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details(
                "ws-1",
                section="video",
                kind="route",
                ref="route-1",
                profile="technical",
            )

        self.assertEqual(result["details"]["destinationInfo"]["screenSerialNumber"], "SERIAL")
        self.assertFalse(result["details"]["connected"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/video/routes"])

    def test_workspace_setting_details_safe_video_stage_returns_compact_regions(self) -> None:
        responses = {
            "/workspace/ws-1/settings/video/stages": [
                {"name": "Main Stage", "uniqueID": "stage-1", "width": 1920, "height": 1080}
            ],
            "/workspace/ws-1/settings/video/stageID/stage-1/regions": [
                {
                    "name": "A",
                    "uniqueID": "region-1",
                    "boundsOnStage": {"x": 0, "y": 0, "width": 1920, "height": 1080},
                    "controlPoints": [{"x": 0, "y": 0}],
                    "shadowControlPoints": [{"x": 1, "y": 1}],
                    "meshSubregions": [{"large": "mesh payload"}],
                    "route": {
                        "name": "Projector",
                        "uniqueID": "route-1",
                        "connected": False,
                        "destinationInfo": {"destinationType": "Display", "screenSerialNumber": "SERIAL"},
                    },
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details("ws-1", section="video", kind="stage", ref="Main Stage")

        serialized = json.dumps(result)
        self.assertEqual(result["profile"], "safe")
        self.assertEqual(result["details"]["stage"]["uniqueID"], "stage-1")
        self.assertEqual(result["details"]["regions"][0]["uniqueID"], "region-1")
        self.assertEqual(result["details"]["regions"][0]["control_point_count"], 1)
        self.assertEqual(result["details"]["regions"][0]["shadow_control_point_count"], 1)
        self.assertEqual(result["details"]["regions"][0]["mesh_subregion_count"], 1)
        self.assertEqual(result["details"]["regions"][0]["route"]["destination_type"], "Display")
        self.assertNotIn("\"controlPoints\"", serialized)
        self.assertNotIn("\"shadowControlPoints\"", serialized)
        self.assertNotIn("\"meshSubregions\"", serialized)
        self.assertNotIn("\"destinationInfo\"", serialized)
        self.assertNotIn("screenSerialNumber", serialized)
        self.assertNotIn("SERIAL", serialized)
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/video/stages",
                "/workspace/ws-1/settings/video/stageID/stage-1/regions",
            ],
        )

    def test_workspace_setting_details_safe_audio_map_omits_level_arrays(self) -> None:
        responses = {
            "/workspace/ws-1/settings/audio/maps": [
                {
                    "name": "Stereo",
                    "uniqueID": "map-1",
                    "width": 1000,
                    "height": 1000,
                    "marks": [
                        {"name": "Left", "uniqueID": "mark-1", "levels": [0, -60, -60], "position": {"x": -400, "y": 0}}
                    ],
                    "objects": [{"name": "Narrator", "uniqueID": "object-1"}],
                    "filters": [{"name": "Front", "uniqueID": "filter-1"}],
                }
            ]
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details("ws-1", section="audio", kind="audio_map", ref="Stereo")

        serialized = json.dumps(result)
        self.assertEqual(result["profile"], "safe")
        self.assertEqual(result["details"]["summary"]["uniqueID"], "map-1")
        self.assertEqual(result["details"]["marks"][0]["level_count"], 3)
        self.assertEqual(result["details"]["marks"][0]["active_output_count"], 1)
        self.assertNotIn("\"levels\"", serialized)
        self.assertEqual(server.received, ["/workspace/ws-1/settings/audio/maps"])

    def test_workspace_setting_details_safe_light_patch_returns_compact_index(self) -> None:
        class FallbackClient:
            config = QLabConfig()

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                raise OscTimeoutError("udp too small")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                return SimpleNamespace(
                    data={
                        "instruments": [
                            {
                                "name": "1",
                                "comment": "L-101",
                                "patched": True,
                                "conflicted": False,
                                "definition": {
                                    "manufacturer": "Generic",
                                    "name": "Dimmer",
                                    "parameters": {"0": {"name": "intensity"}},
                                },
                                "parameters": [{"name": "intensity", "definitionParameter": {"large": "payload"}}],
                            }
                        ],
                        "groups": [
                            {
                                "name": "Front",
                                "instruments": [
                                    {
                                        "name": "1",
                                        "comment": "L-101",
                                        "patched": True,
                                        "conflicted": False,
                                        "definition": {
                                            "manufacturer": "Generic",
                                            "name": "Dimmer",
                                            "parameters": {"0": {"name": "intensity"}},
                                        },
                                        "parameters": [{"name": "intensity", "definitionParameter": {"large": "payload"}}],
                                    }
                                ],
                            }
                        ]
                    }
                )

        reader = QLabReader(FallbackClient())  # type: ignore[arg-type]

        result = reader.get_workspace_setting_details("ws-1", section="light", kind="light_patch")

        serialized = json.dumps(result)
        self.assertEqual(result["profile"], "safe")
        self.assertEqual(result["details"]["summary"]["instrument_count"], 1)
        self.assertEqual(result["details"]["summary"]["read_transport"], "tcp_fallback")
        self.assertIn("large response", result["details"]["summary"]["read_transport_meaning"])
        self.assertEqual(result["details"]["groups"][0]["instrument_names"], ["1"])
        self.assertEqual(result["details"]["instrument_index"]["rows"][0][0], "1")
        self.assertEqual(len(result["details"]["instrument_index"]["rows"]), 1)
        self.assertEqual(result["details"]["definition_counts"], {"Generic Dimmer": 1})
        self.assertNotIn('"large": "payload"', serialized)
        self.assertNotIn("\"patch\"", serialized)
        self.assertNotIn("\"patch_sheet\"", serialized)

    def test_workspace_setting_details_safe_patch_kinds_return_normalized_summaries(self) -> None:
        responses = {
            "/workspace/ws-1/settings/audio/patchList": [
                {
                    "name": "Main Out",
                    "uniqueID": "audio-1",
                    "routing": [{"source": 1, "destination": 1}],
                    "deviceName": "Secret Audio Device",
                }
            ],
            "/workspace/ws-1/settings/video/routes": [
                {
                    "name": "Projector",
                    "uniqueID": "route-1",
                    "connected": True,
                    "destinationInfo": {"destinationType": "Display", "screenSerialNumber": "SERIAL"},
                }
            ],
            "/workspace/ws-1/settings/video/inputPatchList": [
                {"name": "Camera", "uniqueID": "input-1", "deviceName": "Camera Device"}
            ],
            "/workspace/ws-1/settings/network/patchList": [
                {
                    "name": "OSC",
                    "uniqueID": "network-1",
                    "destinations": [{"ipAddress": "192.168.0.10", "port": 53000, "passcode": "pw"}],
                }
            ],
            "/workspace/ws-1/settings/midi/patchList": [
                {"name": "MIDI", "uniqueID": "midi-1", "deviceName": "MIDI Device"}
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            audio = reader.get_workspace_setting_details("ws-1", "audio", "output_patch", "Main Out")
            route = reader.get_workspace_setting_details("ws-1", "video", "route", "route-1")
            video_input = reader.get_workspace_setting_details("ws-1", "video", "video_input_patch", "Camera")
            network = reader.get_workspace_setting_details("ws-1", "network", "network_patch", "OSC")
            midi = reader.get_workspace_setting_details("ws-1", "midi", "midi_patch", "MIDI")

        self.assertEqual(audio["details"]["routing_count"], 1)
        self.assertTrue(audio["details"]["device_present"])
        self.assertEqual(route["details"]["destination_type"], "Display")
        self.assertTrue(route["details"]["destination_present"])
        self.assertEqual(route["details"]["technical_payloads_omitted"], ["destinationInfo"])
        self.assertTrue(video_input["details"]["device_present"])
        self.assertTrue(network["details"]["destination_present"])
        self.assertTrue(network["details"]["passcode_present"])
        self.assertTrue(midi["details"]["destination_present"])
        serialized = json.dumps([audio, route, video_input, network, midi])
        self.assertNotIn("Secret Audio Device", serialized)
        self.assertNotIn("SERIAL", serialized)
        self.assertNotIn("192.168.0.10", serialized)
        self.assertNotIn("53000", serialized)
        self.assertNotIn("pw", serialized)
        self.assertNotIn("MIDI Device", serialized)
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/audio/patchList",
                "/workspace/ws-1/settings/video/routes",
                "/workspace/ws-1/settings/video/inputPatchList",
                "/workspace/ws-1/settings/network/patchList",
                "/workspace/ws-1/settings/midi/patchList",
            ],
        )

    def test_workspace_setting_details_missing_ref_returns_choices(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {"name": "OSC A", "uniqueID": "network-1"},
                {"name": "OSC B", "uniqueID": "network-2"},
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details("ws-1", section="network", kind="network_patch")

        self.assertIsNone(result["details"])
        self.assertEqual(len(result["choices"]), 2)
        self.assertIn("Multiple settings items", result["message"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_setting_details_light_patch_records_error(self) -> None:
        responses = {
            "/workspace/ws-1/settings/light/patch": {"status": "error", "data": "light patch unavailable"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details("ws-1", section="light", kind="light_patch")

        self.assertIn("light.patch", result["errors"])
        self.assertEqual(
            result["details"]["summary"],
            {"patch_present": False, "instrument_count": 0, "group_count": 0},
        )
        self.assertEqual(server.received, ["/workspace/ws-1/settings/light/patch"])

    def test_workspace_setting_details_light_patch_falls_back_to_tcp_after_udp_timeout(self) -> None:
        class FallbackClient:
            config = QLabConfig()

            def __init__(self) -> None:
                self.udp_requests: list[str] = []
                self.tcp_requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.udp_requests.append(address)
                raise OscTimeoutError("udp too small")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.tcp_requests.append(address)
                return SimpleNamespace(data={"instruments": [{"name": "front"}], "definitions": []})

        client = FallbackClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_setting_details("ws-1", section="light", kind="light_patch")

        self.assertEqual(client.udp_requests, ["/workspace/ws-1/settings/light/patch"])
        self.assertEqual(client.tcp_requests, ["/workspace/ws-1/settings/light/patch"])
        self.assertIsNone(result["errors"])
        self.assertEqual(result["details"]["summary"]["instrument_count"], 1)
        self.assertEqual(result["details"]["summary"]["read_transport"], "tcp_fallback")
        self.assertIn("does not imply output failure", result["details"]["summary"]["read_transport_meaning"])

    def test_workspace_setting_details_light_patch_tcp_fallback_handles_large_payload(self) -> None:
        class FallbackClient:
            config = QLabConfig()

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                raise OscTimeoutError("udp too small")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                return SimpleNamespace(
                    data={
                        "instruments": [
                            {"name": str(index), "patched": True, "definition": {"name": "Dimmer"}}
                            for index in range(250)
                        ],
                        "groups": [{"name": "All"}],
                        "definitions": [{"name": "Dimmer"}],
                    }
                )

        reader = QLabReader(FallbackClient())  # type: ignore[arg-type]

        result = reader.get_workspace_setting_details("ws-1", section="light", kind="light_patch")

        self.assertIsNone(result["errors"])
        self.assertEqual(result["details"]["summary"]["instrument_count"], 250)
        self.assertEqual(result["details"]["summary"]["read_transport"], "tcp_fallback")
        self.assertIn("TCP was used", result["details"]["summary"]["read_transport_meaning"])
        self.assertEqual(len(result["details"]["instrument_index"]["rows"]), 250)

    def test_agent_style_read_flow(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"

        class FlowClient:
            config = QLabConfig(cache_ttl=10)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": "list-1", "name": "Main", "type": "Cue List", "armed": True}],
                        status="ok",
                    )
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=[cue_id], status="ok")
                if address == "/workspace/ws-1/settings/network/patchList":
                    return SimpleNamespace(
                        data=[{"uniqueID": "net-1", "name": "OSC Out", "host": "10.0.0.5", "port": 53000}],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys":
                    return SimpleNamespace(
                        data={
                            "uniqueID": cue_id,
                            "number": "1",
                            "name": "Intro",
                            "displayName": "1 Intro",
                            "listName": "Main",
                            "type": "Audio",
                            "armed": True,
                            "flagged": False,
                            "colorName": "green",
                            "isBroken": False,
                            "isWarning": False,
                            "hasFileTargets": True,
                            "audioOutputPatchName": "Main Out",
                            "audioOutputPatchID": "patch-1",
                        },
                        status="ok",
                    )
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(FlowClient())  # type: ignore[arg-type]

        check = reader.check_connection("ws-1")
        overview = reader.get_workspace_overview("ws-1", include_cue_index=False)
        settings = reader.get_workspace_settings("ws-1", sections=["network"])
        query = reader.query_cues("ws-1", "type", "Audio")
        details = reader.get_cue_details("ws-1", cue_id)
        setting_details = reader.get_workspace_setting_details("ws-1", "network", "network_patch")

        self.assertEqual(check["status"], "ready")
        self.assertEqual(overview["cue_count"], 1)
        self.assertEqual(settings["sections"]["network"]["patches"][0]["name"], "OSC Out")
        self.assertEqual(query["returned_count"], 1)
        self.assertEqual(details["sections"]["type_specific"]["audioOutputPatchName"], "Main Out")
        self.assertEqual(setting_details["details"]["uniqueID"], "net-1")

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
                "isBroken": True,
                "isWarning": False,
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
        self.assertEqual(result["truncation_reasons"], [])
        self.assertTrue(result["scanned_all_cues"])
        self.assertFalse(result["result_limited"])
        self.assertEqual(result["cues"][0]["uniqueID"], audio_id)
        self.assertEqual(result["cues"][0]["cue_list_id"], list_id)
        self.assertEqual(result["cues"][0]["depth"], 1)
        self.assertTrue(result["cues"][0]["isBroken"])
        self.assertFalse(result["cues"][0]["isWarning"])
        self.assertEqual(result["limits"], {"max_results": 500, "max_cues_scanned": 500})
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

    def test_query_cues_supports_safe_state_and_target_filters(self) -> None:
        audio_1 = "11111111-1111-4111-8111-111111111111"
        audio_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [audio_1, audio_2],
            f"/workspace/ws-1/cue_id/{audio_1}/valuesForKeys": {
                "uniqueID": audio_1,
                "number": "A1",
                "name": "Warning audio",
                "displayName": "A1 Warning audio",
                "type": "Audio",
                "armed": 0,
                "flagged": False,
                "colorName": "red",
                "isWarning": 1,
                "hasFileTargets": True,
                "skipIfDisarmed": "true",
                "autoLoad": False,
                "hasCueTargets": False,
                "isLoaded": True,
                "isOverridden": False,
            },
            f"/workspace/ws-1/cue_id/{audio_2}/valuesForKeys": {
                "uniqueID": audio_2,
                "number": "A2",
                "name": "Clean audio",
                "displayName": "A2 Clean audio",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
                "isWarning": False,
                "hasFileTargets": False,
                "skipIfDisarmed": False,
                "autoLoad": False,
                "hasCueTargets": False,
                "isLoaded": False,
                "isOverridden": False,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues(
                "ws-1",
                "type",
                "Audio",
                optional_filters=[
                    {"filter": "isWarning", "value": True},
                    {"filter": "disarmed", "value": True},
                    {"filter": "hasFileTargets", "value": True},
                    {"filter": "skipIfDisarmed", "value": True},
                    {"filter": "isLoaded", "value": True},
                    {"filter": "isOverridden", "value": False},
                ],
            )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["cues"][0]["uniqueID"], audio_1)
        self.assertEqual(result["cues"][0]["hasFileTargets"], True)
        self.assertEqual(result["cues"][0]["skipIfDisarmed"], "true")
        self.assertEqual(result["cues"][0]["isLoaded"], True)

    def test_query_cues_supports_timing_presence_and_continue_mode_filters(self) -> None:
        cue_1 = "11111111-1111-4111-8111-111111111111"
        cue_2 = "22222222-2222-4222-8222-222222222222"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_1, cue_2],
            f"/workspace/ws-1/cue_id/{cue_1}/valuesForKeys": {
                "uniqueID": cue_1,
                "number": "1",
                "name": "Auto follow",
                "displayName": "1 Auto follow",
                "type": "Wait",
                "armed": True,
                "flagged": False,
                "colorName": "none",
                "continueMode": "auto_follow",
                "preWait": 1.5,
                "postWait": 0,
                "duration": 3,
            },
            f"/workspace/ws-1/cue_id/{cue_2}/valuesForKeys": {
                "uniqueID": cue_2,
                "number": "2",
                "name": "Manual",
                "displayName": "2 Manual",
                "type": "Wait",
                "armed": True,
                "flagged": False,
                "colorName": "none",
                "continueMode": "do_not_continue",
                "preWait": 0,
                "postWait": 2,
                "duration": 0,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues(
                "ws-1",
                "continueMode",
                "auto_follow",
                optional_filters=[
                    {"filter": "hasPreWait", "value": True},
                    {"filter": "hasPostWait", "value": False},
                    {"filter": "hasDuration", "value": True},
                ],
            )

        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["cues"][0]["uniqueID"], cue_1)
        self.assertEqual(result["cues"][0]["continueMode"], "auto_follow")
        self.assertEqual(result["cues"][0]["continueModeLabel"], "auto_follow")

    def test_query_cues_supports_editorial_health_filters(self) -> None:
        cue_1 = "11111111-1111-4111-8111-111111111111"
        cue_2 = "22222222-2222-4222-8222-222222222222"
        cue_3 = "33333333-3333-4333-8333-333333333333"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_1, cue_2, cue_3],
            f"/workspace/ws-1/cue_id/{cue_1}/valuesForKeys": {
                "uniqueID": cue_1,
                "number": "",
                "name": "",
                "displayName": "",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "isBroken": False,
            },
            f"/workspace/ws-1/cue_id/{cue_2}/valuesForKeys": {
                "uniqueID": cue_2,
                "number": "1",
                "name": "Clean",
                "displayName": "1 Clean",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "isBroken": False,
            },
            f"/workspace/ws-1/cue_id/{cue_3}/valuesForKeys": {
                "uniqueID": cue_3,
                "number": "2",
                "name": "Flagged",
                "displayName": "¿?",
                "type": "Audio",
                "armed": True,
                "flagged": True,
                "isBroken": False,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            empty = reader.query_cues("ws-1", "name_empty", True)
            clean = reader.query_cues(
                "ws-1",
                "type",
                "Audio",
                optional_filters=[{"filter": "name_empty", "value": False}],
            )
            ambiguous = reader.query_cues("ws-1", "ambiguous_label", True)
            flagged_or_broken = reader.query_cues("ws-1", "flagged_or_broken", True)

        self.assertEqual(empty["matched_count"], 1)
        self.assertEqual(empty["cues"][0]["uniqueID"], cue_1)
        self.assertEqual(clean["matched_count"], 2)
        self.assertEqual(ambiguous["matched_count"], 1)
        self.assertEqual(ambiguous["cues"][0]["uniqueID"], cue_3)
        self.assertEqual(flagged_or_broken["matched_count"], 1)
        self.assertEqual(flagged_or_broken["cues"][0]["uniqueID"], cue_3)

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
        self.assertEqual(result_limit["truncation_reasons"], ["max_results"])
        self.assertTrue(result_limit["scanned_all_cues"])
        self.assertTrue(result_limit["result_limited"])
        self.assertEqual(scan_limit["scanned_count"], 2)
        self.assertEqual(scan_limit["total_cue_ids"], 3)
        self.assertTrue(scan_limit["truncated"])
        self.assertEqual(scan_limit["truncation_reasons"], ["max_cues_scanned"])
        self.assertFalse(scan_limit["scanned_all_cues"])
        self.assertFalse(scan_limit["result_limited"])

    def test_query_cues_can_scan_more_than_default_when_explicitly_raised(self) -> None:
        cue_ids = [f"{index:032d}-aaaa-bbbb-cccc-{index:012d}" for index in range(501)]

        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=cue_ids, status="ok")
                return SimpleNamespace(
                    data={
                        "uniqueID": address.split("/cue_id/", 1)[1].split("/", 1)[0],
                        "number": "1",
                        "name": "Audio",
                        "displayName": "Audio",
                        "listName": "Main",
                        "type": "Audio",
                        "armed": True,
                        "flagged": False,
                        "colorName": "none",
                    },
                    status="ok",
                )

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.query_cues("ws-1", "type", "Audio", max_results=501, max_cues_scanned=501)

        self.assertEqual(result["scanned_count"], 501)
        self.assertEqual(result["matched_count"], 501)
        self.assertEqual(result["returned_count"], 501)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["limits"], {"max_results": 501, "max_cues_scanned": 501})

    def test_query_cues_health_redacts_file_target_but_reports_presence(self) -> None:
        cue_id = "11111111-1111-4111-8111-111111111111"
        responses = {
            "/workspace/ws-1/cueLists/uniqueIDs": [cue_id],
            f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys": {
                "uniqueID": cue_id,
                "number": "1",
                "name": "Intro",
                "displayName": "1 Intro",
                "listName": "Intro",
                "type": "Audio",
                "armed": True,
                "flagged": False,
                "colorName": "none",
                "isBroken": True,
                "isWarning": False,
                "hasFileTargets": True,
                "fileTarget": "/Users/example/private/audio.wav",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues("ws-1", "type", "Audio", profile="health")

        self.assertTrue(result["cues"][0]["hasFileTargets"])
        self.assertTrue(result["cues"][0]["fileTargetPresent"])
        self.assertNotIn("fileTarget", result["cues"][0])
        self.assertEqual(result["cues"][0]["health_summary"]["status"], "broken")
        self.assertIn("File target exists", result["cues"][0]["health_summary"]["messages"][0])

    def test_query_cues_targets_profile_redacts_file_target_but_reports_presence(self) -> None:
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
                "isBroken": False,
                "isWarning": False,
                "hasFileTargets": True,
                "hasCueTargets": False,
                "fileTarget": "/Users/example/private/audio.wav",
                "cueTargetID": "",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues("ws-1", "type", "Audio", profile="targets")

        self.assertTrue(result["cues"][0]["hasFileTargets"])
        self.assertTrue(result["cues"][0]["fileTargetPresent"])
        self.assertNotIn("fileTarget", result["cues"][0])

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

    def test_auto_cue_details_sections_representative_types(self) -> None:
        cases = [
            (
                "Audio",
                {"audioOutputPatchName": "Main L/R", "audioMap/size": [2, 2], "hasFileTargets": True},
                ("type_specific", "audioOutputPatchName", "Main L/R"),
            ),
            (
                "Text",
                {
                    "stage": {"regions": [{"id": "large"}]},
                    "stageName": "Projector",
                    "stage/regions": [{"id": "large"}],
                    "opacity": 0.75,
                    "text": "Act I",
                },
                ("type_specific", "stageName", "Projector"),
            ),
            (
                "Light",
                {"lightCommandText": "1 thru 5 @ 80", "alwaysCollate": True},
                ("type_specific", "lightCommandText", "1 thru 5 @ 80"),
            ),
            (
                "Network",
                {"networkPatchName": "EOS", "message": "/eos/cue/1/fire", "messageError": ""},
                ("type_specific", "message", "/eos/cue/1/fire"),
            ),
            (
                "Group",
                {"mode": 3, "playhead": "1.1", "playlistLoop": False},
                ("type_specific", "mode", 3),
            ),
            (
                "Start",
                {"cueTargetNumber": "LX1", "targetMode": "cue"},
                ("type_specific", "cueTargetNumber", "LX1"),
            ),
            (
                "Script",
                {"scriptSource": "display dialog \"secret\""},
                ("type_specific", "scriptSource", None),
            ),
        ]
        for cue_type, extra_values, expected in cases:
            with self.subTest(cue_type=cue_type):
                values = {
                    "uniqueID": "cue-id",
                    "number": "10",
                    "name": f"{cue_type} cue",
                    "displayName": f"10 {cue_type} cue",
                    "listName": "Main",
                    "type": cue_type,
                    "colorName": "none",
                    "armed": True,
                    "flagged": False,
                    "isRunning": False,
                    "isPaused": False,
                    "isLoaded": False,
                    "isBroken": False,
                    "isWarning": False,
                    "preWait": 0,
                    "duration": 1,
                    "postWait": 0,
                    "continueMode": "do_not_continue",
                    "hasFileTargets": False,
                    "fileTarget": "/Users/example/private/target.wav",
                    "notes": "private note",
                    **extra_values,
                }
                with FakeQlabOscServer({"/workspace/ws-1/cue/10/valuesForKeys": values}) as server:
                    reader = QLabReader(client_for(server))

                    result = reader.get_cue_details("ws-1", "10")

                section_name, key, expected_value = expected
                self.assertEqual(result["profile"], "auto")
                self.assertEqual(result["cue_type"], cue_type)
                self.assertEqual(result["sections"]["identity"]["type"], cue_type)
                self.assertEqual(result["sections"]["status"]["armed"], True)
                self.assertEqual(result["sections"]["timing"]["duration"], 1)
                self.assertNotIn("fileTarget", result["properties"])
                self.assertNotIn("notes", result["properties"])
                self.assertNotIn("scriptSource", result["properties"])
                self.assertNotIn("stage", result["properties"])
                self.assertNotIn("stage/regions", result["properties"])
                if expected_value is None:
                    self.assertNotIn(key, result["sections"][section_name])
                else:
                    self.assertEqual(result["sections"][section_name][key], expected_value)

    def test_auto_video_details_keep_compact_stage_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "Projection",
                "displayName": "10 Projection",
                "type": "Video",
                "isBroken": False,
                "isWarning": False,
                "continueMode": 2,
                "stage": {"regions": [{"id": "large"}]},
                "stageName": "Main Stage",
                "stageID": "stage-id",
                "stage/size": [1920, 1080],
                "stage/regions": [{"id": "large"}],
                "opacity": 0.5,
                "translation": [10, 20, 0],
                "scale": [1, 1, 1],
                "videoEffects": [],
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "auto")

        self.assertNotIn("stage", result["properties"])
        self.assertNotIn("stage/regions", result["properties"])
        self.assertEqual(result["sections"]["type_specific"]["stageName"], "Main Stage")
        self.assertEqual(result["sections"]["type_specific"]["stage/size"], [1920, 1080])
        self.assertEqual(result["sections"]["type_specific"]["opacity"], 0.5)
        self.assertEqual(result["sections"]["timing"]["continueModeLabel"], "auto_follow")

    def test_auto_cue_details_falls_back_for_unknown_type(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "Custom",
                "displayName": "10 Custom",
                "type": "Custom Future Cue",
                "armed": True,
                "flagged": False,
                "isBroken": False,
                "isWarning": False,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "auto")

        self.assertEqual(result["cue_type"], "Custom Future Cue")
        self.assertEqual(result["sections"]["identity"]["name"], "Custom")
        self.assertEqual(result["sections"]["type_specific"], {})
        self.assertNotIn("errors", result)

    def test_auto_cue_details_fallback_records_partial_errors(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {"status": "error", "data": "batch unavailable"},
            "/workspace/ws-1/cue/10/uniqueID": "cue-id",
            "/workspace/ws-1/cue/10/number": "10",
            "/workspace/ws-1/cue/10/name": "Intro",
            "/workspace/ws-1/cue/10/displayName": "10 Intro",
            "/workspace/ws-1/cue/10/type": "Audio",
            "/workspace/ws-1/cue/10/armed": True,
            "/workspace/ws-1/cue/10/flagged": False,
            "/workspace/ws-1/cue/10/audioOutputPatchName": "Main L/R",
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "auto")

        self.assertEqual(result["properties"]["name"], "Intro")
        self.assertEqual(result["sections"]["type_specific"]["audioOutputPatchName"], "Main L/R")
        self.assertIn("valuesForKeys", result["errors"])
        self.assertIn("valuesForKeys:type_specific", result["errors"])

    def test_active_cue_details_no_active_cues_is_compact(self) -> None:
        responses = {
            "/workspace/ws-1/cue/active/valuesForKeys": {"status": "error", "data": "No active cues"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "active", "auto")

        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["message"], "No active cues are currently running or paused.")
        self.assertEqual(result["properties"], {})
        self.assertEqual(result["sections"]["identity"], {})
        self.assertNotIn("errors", result)
        self.assertEqual(server.received, ["/workspace/ws-1/cue/active/valuesForKeys"])

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
        self.assertNotIn("notes", properties_for_profile("auto"))
        self.assertNotIn("fileTarget", properties_for_profile("auto"))
        self.assertNotIn("scriptSource", properties_for_profile("auto"))
        self.assertNotIn("notes", properties_for_profile("basic_safe"))
        self.assertNotIn("fileTarget", properties_for_profile("basic_safe"))
        self.assertNotIn("fileTarget", properties_for_profile("targets"))
        self.assertIn("hasFileTargets", properties_for_profile("targets"))
        self.assertIn("fileTarget", properties_for_profile("technical"))
        self.assertIn("isBroken", properties_for_profile("health"))
        self.assertNotIn("fileTarget", properties_for_profile("health"))
        self.assertNotIn("stage", properties_for_profile("type_specific"))
        self.assertNotIn("stage/regions", properties_for_profile("type_specific"))
        self.assertNotIn("scriptSource", properties_for_profile("type_specific"))
        self.assertNotIn("notes", properties_for_profile("full"))
        self.assertNotIn("fileTarget", properties_for_profile("full"))
        self.assertNotIn("scriptSource", properties_for_profile("full"))
        self.assertNotIn("stage", properties_for_profile("full"))
        self.assertNotIn("stage/regions", properties_for_profile("full"))
        self.assertIn("notes", properties_for_profile("full_sensitive"))
        self.assertIn("fileTarget", properties_for_profile("full_sensitive"))
        self.assertIn("scriptSource", properties_for_profile("full_sensitive"))
        self.assertIn("stage", properties_for_profile("full_sensitive"))

    def test_health_profile_redacts_file_target_but_reports_presence(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Audio",
                "isBroken": True,
                "hasFileTargets": True,
                "fileTarget": "/Users/example/private/audio.wav",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "health")

        self.assertTrue(result["properties"]["hasFileTargets"])
        self.assertTrue(result["properties"]["fileTargetPresent"])
        self.assertNotIn("fileTarget", result["properties"])
        self.assertEqual(result["properties"]["health_summary"]["status"], "broken")
        self.assertIn("file_target_present_but_broken", result["properties"]["health_summary"]["probable_causes"])
        self.assertEqual(result["properties"]["health_summary"]["confidence"], "derived")

    def test_targets_profile_redacts_file_target_but_reports_presence(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Audio",
                "hasFileTargets": True,
                "fileTarget": "/Users/example/private/audio.wav",
                "cueTargetID": "",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "targets")

        self.assertTrue(result["properties"]["hasFileTargets"])
        self.assertTrue(result["properties"]["fileTargetPresent"])
        self.assertNotIn("fileTarget", result["properties"])

    def test_health_summary_covers_container_network_and_clean_cues(self) -> None:
        cases = [
            (
                {"type": "Cue List", "isBroken": True, "isWarning": False},
                "broken",
                "Container reports",
                "broken_child_cue_likely",
            ),
            (
                {"type": "Network", "isBroken": False, "isWarning": False, "messageError": "Bad OSC"},
                "attention",
                "Network/message error",
                "network_message_error",
            ),
            (
                {"type": "Light", "isBroken": True, "isWarning": False},
                "broken",
                "Light cue reports",
                "light_cue_reported_broken",
            ),
            (
                {"type": "Audio", "isBroken": False, "isWarning": False},
                "ok",
                None,
                None,
            ),
        ]
        for values, status, message_fragment, probable_cause in cases:
            with self.subTest(status=status):
                responses = {"/workspace/ws-1/cue/10/valuesForKeys": values}
                with FakeQlabOscServer(responses) as server:
                    reader = QLabReader(client_for(server))

                    result = reader.get_cue_details("ws-1", "10", "health")

                summary = result["properties"]["health_summary"]
                self.assertEqual(summary["status"], status)
                self.assertEqual(summary["confidence"], "derived")
                self.assertIn("evidence", summary)
                if message_fragment is None:
                    self.assertEqual(summary["messages"], [])
                else:
                    self.assertIn(message_fragment, summary["messages"][0])
                    self.assertIn(probable_cause, summary["probable_causes"])
                    self.assertTrue(summary["diagnostic_hints"])
                    self.assertTrue(summary["needs_human_check"])

    def test_technical_profile_can_return_file_target(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Audio",
                "hasFileTargets": True,
                "fileTarget": "/Users/example/private/audio.wav",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "technical")

        self.assertEqual(result["properties"]["fileTarget"], "/Users/example/private/audio.wav")

    def test_full_sensitive_profile_can_return_sensitive_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Script",
                "notes": "operator note",
                "fileTarget": "/Users/example/private/audio.wav",
                "scriptSource": "display dialog \"secret\"",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "full_sensitive")

        self.assertEqual(result["properties"]["notes"], "operator note")
        self.assertEqual(result["properties"]["fileTarget"], "/Users/example/private/audio.wav")
        self.assertEqual(result["properties"]["scriptSource"], "display dialog \"secret\"")

    def test_values_for_keys_rejects_action_like_keys(self) -> None:
        self.assertEqual(validate_value_keys(["opacity", "stageName"]), ["opacity", "stageName"])
        for unsafe in (["start"], ["panic"], ["../name"], ["unknownThing"], []):
            with self.assertRaises(UnsafeCuePropertyError):
                validate_value_keys(unsafe)


if __name__ == "__main__":
    unittest.main()

