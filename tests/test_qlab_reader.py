from __future__ import annotations

import json
import socket
import sys
import threading
import time
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
from qlab_mcp.runtime.connection import OVERRIDE_ENDPOINTS, normalize_workspace_mode, parse_connect_scopes
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
                if message.address == "/workspaces" and message.address not in self.responses:
                    payload = {
                        "status": "ok",
                        "data": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
                        "workspace_id": "ws-1",
                    }
                    reply_address = f"/reply/{message.address.lstrip('/')}"
                    sock.sendto(encode_message(reply_address, json.dumps(payload)), client_addr)
                    continue
                self.received.append(message.address)
                self.received_args.append(message.args)
                self.received_client_ports.append(client_addr[1])
                response = self.responses.get(message.address)
                if response is None or (
                    response == []
                    and message.address.endswith("/cueLists/shallow")
                    and self.responses.get(message.address.removesuffix("/shallow") + "/uniqueIDs") is not None
                ):
                    response = self._synthetic_shallow_response(message.address)
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

    def _synthetic_shallow_response(self, address: str) -> Any:
        if address.endswith("/cueLists/shallow"):
            unique_ids = self.responses.get(address.removesuffix("/shallow") + "/uniqueIDs")
            if unique_ids is None:
                return None
            return [self._shallow_cue(ref) for ref in self._root_refs(unique_ids)]
        if address.endswith("/children/shallow"):
            if "/cue_id/" in address:
                cue_id = address.split("/cue_id/", 1)[1].split("/children/shallow", 1)[0]
                workspace_prefix = address.split("/cue_id/", 1)[0]
            elif "/cue/" in address:
                cue_id = address.split("/cue/", 1)[1].split("/children/shallow", 1)[0]
                workspace_prefix = address.split("/cue/", 1)[0]
            else:
                return None
            unique_ids = self.responses.get(workspace_prefix + "/cueLists/uniqueIDs")
            children = self._children_for(unique_ids, cue_id)
            if children is None:
                return None
            return [self._shallow_cue(ref) for ref in children]
        return None

    def _root_refs(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return [value]

    def _children_for(self, value: Any, cue_id: str) -> list[Any] | None:
        if isinstance(value, dict):
            if value.get("uniqueID") == cue_id:
                children = value.get("cues", [])
                return children if isinstance(children, list) else []
            children = value.get("cues")
            if isinstance(children, list):
                for child in children:
                    found = self._children_for(child, cue_id)
                    if found is not None:
                        return found
        if isinstance(value, list):
            for item in value:
                found = self._children_for(item, cue_id)
                if found is not None:
                    return found
        return None

    def _shallow_cue(self, ref: Any) -> dict[str, Any]:
        cue_id = ref.get("uniqueID") if isinstance(ref, dict) else ref
        cue_id = str(cue_id)
        values = self.responses.get(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys")
        if isinstance(values, dict) and "status" not in values:
            shallow = dict(values)
        else:
            shallow = {"uniqueID": cue_id}
        shallow.setdefault("uniqueID", cue_id)
        if isinstance(ref, dict) and ref.get("cues") and "type" not in shallow:
            shallow["type"] = "Group"
        return shallow


def client_for(server: FakeQlabOscServer, timeout: float = 0.25) -> QLabOscClient:
    assert server.port is not None
    return QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=server.port, reply_port=0, timeout=timeout))


def override_responses(enabled: bool = True) -> dict[str, Any]:
    return {f"/overrides/{endpoint}": enabled for endpoint in OVERRIDE_ENDPOINTS.values()}


def override_addresses() -> list[str]:
    return [f"/overrides/{endpoint}" for endpoint in OVERRIDE_ENDPOINTS.values()]


def empty_settings_summary_responses() -> dict[str, Any]:
    return {
        "/workspace/ws-1/settings/audio/patchList": [],
        "/workspace/ws-1/settings/mic/patchList": [],
        "/workspace/ws-1/settings/audio/cueOutputChannelCounts": [],
        "/workspace/ws-1/settings/audio/outputChannelNames": [],
        "/workspace/ws-1/settings/audio/maps": [],
        "/workspace/ws-1/settings/video/inputPatchList": [],
        "/workspace/ws-1/settings/video/routes": [],
        "/workspace/ws-1/settings/video/stages": [],
        "/workspace/ws-1/settings/network/patchList": [],
        "/workspace/ws-1/settings/midi/patchList": [],
        "/workspace/ws-1/settings/general/minGoTime": 0,
        "/workspace/ws-1/settings/general/selectionIsPlayhead": False,
    }


class ConnectScopeTests(unittest.TestCase):
    def test_parse_connect_scope_combinations(self) -> None:
        cases = {
            "ok:view": ["view"],
            "ok:view|edit": ["view", "edit"],
            "ok:view|control": ["view", "control"],
            "ok:view|edit|control": ["view", "edit", "control"],
        }

        for raw, scopes in cases.items():
            with self.subTest(raw=raw):
                result = parse_connect_scopes(raw)
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "confirmed")
                self.assertEqual(result["scopes"], scopes)

    def test_parse_connect_scope_unavailable_shapes(self) -> None:
        unknown = parse_connect_scopes("ok:admin")
        missing = parse_connect_scopes("ok")

        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["status"], "scope_unavailable")
        self.assertEqual(unknown["unknown_scopes"], ["admin"])
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["status"], "scope_unavailable")


class WorkspaceModeTests(unittest.TestCase):
    def test_normalize_workspace_mode(self) -> None:
        show = normalize_workspace_mode(True, "/workspace/ws-1/showMode")
        edit = normalize_workspace_mode(False, "/workspace/ws-1/showMode")
        unknown = normalize_workspace_mode("false", "/workspace/ws-1/showMode")

        self.assertTrue(show["ok"])
        self.assertEqual(show["mode"], "show")
        self.assertTrue(show["show_mode"])
        self.assertTrue(edit["ok"])
        self.assertEqual(edit["mode"], "edit")
        self.assertFalse(edit["show_mode"])
        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["status"], "unexpected_data")
        self.assertEqual(unknown["mode"], "unknown")


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
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-1", "name": "Main"}],
            **override_responses(),
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
        self.assertTrue(result["capabilities"]["workspace_status"])
        self.assertTrue(result["capabilities"]["query_cues"])
        self.assertTrue(result["capabilities"]["cue_details"])
        self.assertIsNone(result["capabilities"]["edit"])
        self.assertIsNone(result["capabilities"]["control"])
        self.assertEqual(result["connect_scopes"]["status"], "not_checked")
        self.assertEqual(result["workspace_mode"]["mode"], "edit")
        self.assertFalse(result["workspace_mode"]["show_mode"])
        self.assertEqual(result["checks"]["show_mode"]["status"], "confirmed")
        self.assertEqual(result["overrides_scope"], "global_to_qlab_app")
        self.assertEqual(result["overrides"]["dmx_output_enabled"]["enabled"], True)
        self.assertEqual(result["override_warnings"], [])
        self.assertTrue(result["permissions"]["view"]["ok"])
        self.assertEqual(result["permissions"]["view"]["status"], "confirmed")
        self.assertTrue(result["permissions"]["view"]["safe_to_probe"])
        self.assertIsNone(result["permissions"]["edit"]["ok"])
        self.assertIsNone(result["permissions"]["control"]["ok"])
        self.assertTrue(result["permissions"]["edit"]["safe_to_probe"])
        self.assertTrue(result["permissions"]["control"]["safe_to_probe"])
        self.assertIn("QLAB_PASSCODE is not configured", result["warnings"][0])
        self.assertEqual(
            server.received,
            ["/workspaces", "/workspace/ws-1/showMode", *override_addresses(), "/workspace/ws-1/cueLists/shallow"],
        )

    def test_check_connection_parses_connect_scopes(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "version": "5.5.10"}]
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/connect": "ok:view|edit",
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-1", "name": "Main"}],
            **override_responses(),
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

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["connect_scopes"]["status"], "confirmed")
        self.assertEqual(result["connect_scopes"]["scopes"], ["view", "edit"])
        self.assertEqual(result["workspace_mode"]["mode"], "edit")
        self.assertTrue(result["permissions"]["edit"]["ok"])
        self.assertEqual(result["permissions"]["edit"]["status"], "confirmed")
        self.assertFalse(result["permissions"]["control"]["ok"])
        self.assertEqual(result["permissions"]["control"]["status"], "not_granted")
        self.assertTrue(result["capabilities"]["edit"])
        self.assertFalse(result["capabilities"]["control"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(
            server.received,
            [
                "/workspaces",
                "/workspace/ws-1/connect",
                "/workspace/ws-1/showMode",
                *override_addresses(),
                "/workspace/ws-1/cueLists/shallow",
            ],
        )

    def test_check_connection_reports_disabled_override_as_warning_not_failure(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        overrides = override_responses()
        overrides["/overrides/dmxOutputEnabled"] = 0
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [],
            **overrides,
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["overrides"]["dmx_output_enabled"]["enabled"])
        self.assertEqual(result["override_warnings"], ["Override disabled: dmx_output_enabled"])
        self.assertIn("Override disabled: dmx_output_enabled", result["warnings"])
        self.assertIn("/overrides/dmxOutputEnabled", server.received)

    def test_check_connection_normalizes_integer_override_values(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        overrides = override_responses()
        overrides["/overrides/dmxOutputEnabled"] = 1
        overrides["/overrides/timecodeOutputEnabled"] = 0
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [],
            **overrides,
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertTrue(result["overrides"]["dmx_output_enabled"]["enabled"])
        self.assertEqual(result["overrides"]["dmx_output_enabled"]["status"], "ok")
        self.assertNotIn("raw_value", result["overrides"]["dmx_output_enabled"])
        self.assertFalse(result["overrides"]["timecode_output_enabled"]["enabled"])
        self.assertEqual(result["overrides"]["timecode_output_enabled"]["status"], "ok")
        self.assertEqual(result["override_warnings"], ["Override disabled: timecode_output_enabled"])

    def test_check_connection_reports_weird_override_value_as_unexpected_data(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        overrides = override_responses()
        overrides["/overrides/dmxOutputEnabled"] = "enabled"
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [],
            **overrides,
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertIsNone(result["overrides"]["dmx_output_enabled"]["enabled"])
        self.assertEqual(result["overrides"]["dmx_output_enabled"]["status"], "unexpected_data")
        self.assertEqual(result["overrides"]["dmx_output_enabled"]["raw_value"], "enabled")
        self.assertEqual(result["override_warnings"], [])

    def test_check_connection_override_read_failure_does_not_break_connection(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [],
            **override_responses(),
            "/overrides/midiOutputEnabled": {"status": "error", "data": "unsupported"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["overrides"]["midi_output_enabled"]["ok"])
        self.assertEqual(result["overrides"]["midi_output_enabled"]["status"], "error")

    def test_check_connection_preserves_connect_view_when_read_probe_times_out(self) -> None:
        workspaces = [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]
        responses = {
            "/workspaces": workspaces,
            "/workspace/ws-1/connect": "ok:view|edit",
            "/workspace/ws-1/showMode": False,
            **override_responses(),
            "/workspace/ws-1/cueLists/shallow": lambda _message: time.sleep(0.2),
        }
        with FakeQlabOscServer(responses) as server:
            assert server.port is not None
            config = QLabConfig(
                host="127.0.0.1",
                osc_port=server.port,
                reply_port=0,
                timeout=0.05,
                passcode="5983",
            )
            reader = QLabReader(QLabOscClient(config))

            result = reader.check_connection()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_read_timeout")
        self.assertFalse(result["workspace_readable"])
        self.assertEqual(result["connect_scopes"]["scopes"], ["view", "edit"])
        self.assertEqual(result["workspace_mode"]["mode"], "edit")
        self.assertTrue(result["permissions"]["view"]["ok"])
        self.assertEqual(result["permissions"]["view"]["status"], "confirmed")
        self.assertEqual(result["permissions"]["view"]["source"], "/connect")
        self.assertEqual(result["checks"]["read_access"]["status"], "timeout")
        self.assertEqual(result["checks"]["read_access"]["address"], "/workspace/ws-1/cueLists/shallow")
        self.assertEqual(
            server.received,
            [
                "/workspaces",
                "/workspace/ws-1/connect",
                "/workspace/ws-1/showMode",
                *override_addresses(),
                "/workspace/ws-1/cueLists/shallow",
            ],
        )

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
        with FakeQlabOscServer(
            {"/workspaces": workspaces, "/workspace/ws-1/showMode": True, **override_responses()}
        ) as server:
            reader = QLabReader(client_for(server))

            result = reader.check_connection(require_read_access=False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["workspace_readable"])
        self.assertTrue(result["checks"]["read_access"]["skipped"])
        self.assertEqual(result["permissions"]["view"]["status"], "skipped")
        self.assertEqual(result["workspace_mode"]["mode"], "show")
        self.assertTrue(result["workspace_mode"]["show_mode"])
        self.assertTrue(result["capabilities"]["resolve_workspace"])
        self.assertFalse(result["capabilities"]["read_workspace"])
        self.assertEqual(server.received, ["/workspaces", "/workspace/ws-1/showMode", *override_addresses()])

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

    def test_workspace_status_invalid_workspace_id_returns_clean_not_found(self) -> None:
        responses = {"/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("missing-ws")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_not_found")
        self.assertEqual(result["error_code"], "workspace_not_found")
        self.assertEqual(result["workspace_id"], "missing-ws")
        self.assertEqual(result["sections"], {})
        self.assertEqual(result["summary"]["available_sections"], [])
        self.assertEqual(result["summary"]["cue_scan_completeness"], "failed")
        self.assertIn("workspace_resolution", result["errors"])
        self.assertNotIn("settings_summary", result["sections"])
        self.assertNotIn("info", result["sections"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_workspace_overview_invalid_workspace_id_returns_clean_not_found(self) -> None:
        responses = {"/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("missing-ws")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_not_found")
        self.assertEqual(result["workspace_id"], "missing-ws")
        self.assertIsNone(result["workspace"])
        self.assertEqual(result["cue_lists"], [])
        self.assertEqual(result["cue_index"]["rows"], [])
        self.assertIn("workspace_resolution", result["errors"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_query_cues_invalid_workspace_id_returns_failed_not_complete(self) -> None:
        responses = {"/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.query_cues("missing-ws", "type", "Audio")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_not_found")
        self.assertEqual(result["query_completeness"], "failed")
        self.assertEqual(result["cues"], [])
        self.assertIn("workspace_resolution", result["errors"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_workspace_settings_invalid_workspace_id_returns_clean_not_found(self) -> None:
        responses = {"/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings("missing-ws")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_not_found")
        self.assertEqual(result["sections"], {})
        self.assertEqual(result["available_detail_requests"], [])
        self.assertIn("workspace_resolution", result["errors"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_cue_details_invalid_workspace_id_returns_workspace_error_without_cue_read(self) -> None:
        responses = {"/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}]}
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("missing-ws", "cue-1")

        self.assertEqual(result["errors"]["error_code"], "workspace_not_found")
        self.assertEqual(result["properties"], {})
        self.assertIn("Requested workspace could not be resolved", result["warnings"][0])
        self.assertEqual(server.received, ["/workspaces"])

    def test_workspace_overview_ambiguous_display_name_returns_clean_error(self) -> None:
        responses = {
            "/workspaces": [
                {"uniqueID": "ws-1", "displayName": "same.qlab5"},
                {"uniqueID": "ws-2", "displayName": "same.qlab5"},
            ]
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("same.qlab5")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_ambiguous")
        self.assertEqual(result["cue_lists"], [])
        self.assertIn("workspace_resolution", result["errors"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_workspace_status_resolves_valid_display_name_in_multiworkspace(self) -> None:
        responses = {
            "/workspaces": [
                {"uniqueID": "ws-1", "displayName": "demo.qlab5"},
                {"uniqueID": "ws-2", "displayName": "other.qlab5"},
            ],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-id", "type": "Cue List", "name": "Main"}],
            "/workspace/ws-1/cue/list-id/children/shallow": [],
            "/workspace/ws-1/cue/list-id/valuesForKeys": {
                "uniqueID": "list-id",
                "type": "Cue List",
                "isWarning": False,
                "isBroken": False,
                "flagged": False,
            },
            **empty_settings_summary_responses(),
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("demo.qlab5", max_cues_scanned=10)

        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["summary"]["cue_scan_completeness"], "complete")
        self.assertIn("/workspace/ws-1/cueLists/shallow", server.received)
        self.assertNotIn("/workspace/demo.qlab5/cueLists/shallow", server.received)

    def test_workspace_status_ambiguous_display_name_returns_clean_error(self) -> None:
        responses = {
            "/workspaces": [
                {"uniqueID": "ws-1", "displayName": "same.qlab5"},
                {"uniqueID": "ws-2", "displayName": "same.qlab5"},
            ]
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("same.qlab5")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "workspace_ambiguous")
        self.assertEqual(result["error_code"], "workspace_ambiguous")
        self.assertEqual(result["workspace_id"], "same.qlab5")
        self.assertEqual(result["sections"], {})
        self.assertEqual(result["summary"]["cue_scan_completeness"], "failed")
        self.assertIn("workspace_resolution", result["errors"])
        self.assertIn("available_workspaces[].uniqueID", result["suggested_action"])
        self.assertEqual(server.received, ["/workspaces"])

    def test_workspace_status_returns_derived_sections_and_not_exposed_markers(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-id", "type": "Cue List", "name": "Main"}],
            "/workspace/ws-1/cue/list-id/children/shallow": [
                {"uniqueID": "cue-1", "type": "Audio", "number": "1"},
                {"uniqueID": "tc-1", "type": "Timecode", "number": "TC"},
            ],
            "/workspace/ws-1/cue/list-id/valuesForKeys": {
                "uniqueID": "list-id",
                "type": "Cue List",
                "name": "Main",
                "timecodeSyncMode": 1,
                "timecodeSMPTEFormat": 30,
                "isWarning": False,
                "isBroken": False,
                "flagged": False,
            },
            "/workspace/ws-1/cue/cue-1/valuesForKeys": {
                "uniqueID": "cue-1",
                "type": "Audio",
                "number": "1",
                "isWarning": True,
                "isBroken": False,
                "flagged": True,
                "continueMode": 2,
            },
            "/workspace/ws-1/cue/tc-1/valuesForKeys": {
                "uniqueID": "tc-1",
                "type": "Timecode",
                "number": "TC",
                "timecodeString": "01:00:00:00",
                "isWarning": False,
                "isBroken": False,
                "flagged": False,
            },
            "/workspace/ws-1/cue/list-id/currentTimecode/text": "01:00:12:10",
            "/workspace/ws-1/cue/tc-1/currentTimecode/text": {"status": "error", "data": "not a receiver"},
            **empty_settings_summary_responses(),
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("ws-1", max_cues_scanned=10)

        self.assertEqual(result["summary"]["cue_scan_completeness"], "complete")
        self.assertEqual(result["sections"]["warnings_summary"]["warning_count"], 1)
        self.assertEqual(result["sections"]["warnings_summary"]["flagged_count"], 1)
        self.assertEqual(result["sections"]["trigger_summary"]["auto_follow_count"], 1)
        self.assertEqual(result["sections"]["trigger_summary"]["timecode_trigger_count"], 0)
        self.assertEqual(result["sections"]["timecode_config"]["configured_count"], 2)
        self.assertFalse(result["sections"]["timecode_config"]["default_timecode_values_seen"])
        self.assertFalse(result["sections"]["timecode_config"]["default_timecode_values_not_counted"])
        self.assertTrue(result["sections"]["timecode_live_status"]["available"])
        self.assertEqual(
            result["sections"]["timecode_live_status"]["sample"][0]["currentTimecode/text"],
            "01:00:12:10",
        )
        self.assertEqual(result["sections"]["logs"]["source"], "not_exposed")
        self.assertEqual(result["sections"]["artnet"]["source"], "not_exposed")
        self.assertEqual(result["sections"]["video_metrics"]["source"], "not_exposed")
        self.assertIn("/workspace/ws-1/cue/list-id/currentTimecode/text", server.received)

    def test_workspace_status_does_not_count_default_timecode_values_as_configured(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-id", "type": "Cue List", "name": "Main"}],
            "/workspace/ws-1/cue/list-id/children/shallow": [{"uniqueID": "cue-1", "type": "Audio"}],
            "/workspace/ws-1/cue/list-id/valuesForKeys": {
                "uniqueID": "list-id",
                "type": "Cue List",
                "timecodeTrigger": {"hours": 1, "minutes": 0, "seconds": 0, "frames": 0, "bits": 0},
                "timecodeTrigger/text": "1:00:00:00",
                "timecodeSyncMode": 0,
                "timecodeSMPTEFormat": 3,
                "timecodeStartBehavior": 4,
                "timecodeStopBehavior": 1,
                "timecodeFreewheelTime": 0.25,
                "timecodeLookbackTime": 0,
            },
            "/workspace/ws-1/cue/cue-1/valuesForKeys": {
                "uniqueID": "cue-1",
                "type": "Audio",
                "timecodeTrigger": {"hours": 1, "minutes": 0, "seconds": 0, "frames": 0, "bits": 0},
                "timecodeTrigger/text": "1:00:00:00",
            },
            **empty_settings_summary_responses(),
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("ws-1", max_cues_scanned=10)

        timecode = result["sections"]["timecode_config"]
        self.assertFalse(timecode["available"])
        self.assertEqual(timecode["configured_count"], 0)
        self.assertTrue(timecode["default_timecode_values_seen"])
        self.assertTrue(timecode["default_timecode_values_not_counted"])
        self.assertEqual(result["sections"]["trigger_summary"]["timecode_trigger_count"], 0)
        self.assertFalse(result["sections"]["timecode_live_status"]["available"])
        self.assertIsNone(result["errors"])
        self.assertNotIn("/workspace/ws-1/cue/list-id/currentTimecode/text", server.received)

    def test_workspace_status_live_timecode_unavailable_is_not_hard_error(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-id", "type": "Cue List", "name": "Main"}],
            "/workspace/ws-1/cue/list-id/children/shallow": [],
            "/workspace/ws-1/cue/list-id/valuesForKeys": {
                "uniqueID": "list-id",
                "type": "Cue List",
                "timecodeSyncMode": 1,
                "isWarning": False,
                "isBroken": False,
                "flagged": False,
            },
            "/workspace/ws-1/cue/list-id/currentTimecode/text": {"status": "error", "data": "not running"},
            **empty_settings_summary_responses(),
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("ws-1", max_cues_scanned=10)

        live = result["sections"]["timecode_live_status"]
        self.assertFalse(live["available"])
        self.assertEqual(live["source"], "not_running_or_not_exposed")
        self.assertEqual(live["status"], "unavailable")
        self.assertIn("unavailable for 1 candidate", " ".join(live["notes"]))
        self.assertIsNone(result["errors"])

    def test_workspace_status_failed_cue_scan_keeps_sections_explicit(self) -> None:
        with FakeQlabOscServer(
            {
                "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
                "/workspace/ws-1/cueLists/shallow": {"status": "error", "data": "denied"},
            }
        ) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_status("ws-1")

        self.assertEqual(result["summary"]["cue_scan_completeness"], "failed")
        self.assertFalse(result["sections"]["warnings_summary"]["available"])
        self.assertFalse(result["sections"]["timecode_live_status"]["available"])
        self.assertEqual(result["sections"]["video_metrics"]["source"], "not_exposed")
        self.assertTrue(any(key.startswith("cue_scan.") for key in result["errors"]))

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
                    "/workspace/ws-1/cueLists/shallow": [
                        {
                            "uniqueID": cue_id,
                            "number": "1",
                            "name": "Intro",
                            "displayName": "1 Intro",
                            "listName": "Main",
                            "type": "Audio",
                            "armed": True,
                            "flagged": False,
                            "colorName": "none",
                        }
                    ],
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

        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/shallow"), 1)
        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/uniqueIDs"), 0)

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
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": cue_id, "type": "Audio"}], status="ok")
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

        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/shallow"), 2)
        self.assertEqual(client.requests.count("/workspace/ws-1/cueLists/uniqueIDs"), 0)
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
            "/workspace/ws-1/showMode": False,
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
        self.assertEqual(result["workspace"]["mode"], "edit")
        self.assertFalse(result["workspace"]["show_mode"])
        self.assertEqual(result["workspace"]["mode_check"]["source"], "/showMode")
        self.assertEqual(result["cue_count"], 3)
        self.assertEqual(result["summary"]["cue_lists"], 1)
        self.assertEqual(result["summary"]["inspected_cues"], 3)
        self.assertEqual(result["summary"]["types"], {"Cue List": 1, "Group": 1, "Light": 1})
        self.assertEqual(result["summary"]["armed"], 2)
        self.assertEqual(result["summary"]["disarmed"], 1)
        self.assertEqual(result["summary"]["flagged"], 1)
        self.assertIsNone(result["summary"]["broken"])
        self.assertIsNone(result["summary"]["warning"])
        self.assertEqual(result["summary"]["health_counts_status"], "partial")
        self.assertIn("Overview health counts are partial", result["warnings"][-1])
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
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", server.received)

    def test_workspace_overview_supports_5000_cues_without_global_unique_ids(self) -> None:
        cues = [
            {
                "uniqueID": f"cue-{index}",
                "number": str(index),
                "name": f"Cue {index}",
                "displayName": f"Cue {index}",
                "type": "Memo",
                "armed": True,
                "flagged": False,
            }
            for index in range(5001)
        ]

        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=cues, status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", max_cues=5000, max_index_cues=5000)

        self.assertEqual(result["cue_count"], 5000)
        self.assertEqual(result["summary"]["inspected_cues"], 5000)
        self.assertEqual(result["summary"]["returned_cues"], 5000)
        self.assertEqual(result["summary"]["total_cue_ids_status"], "partial")
        self.assertFalse(result["summary"]["global_unique_ids_used"])
        self.assertEqual(result["cue_index"]["indexed_count"], 5000)
        self.assertTrue(result["limits"]["truncated"])
        self.assertEqual(result["limits"]["count_status"]["total_cue_ids"], "partial")
        self.assertTrue(result["cue_index"]["truncated"])
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", client.requests)

        with self.assertRaises(ValueError):
            reader.get_workspace_overview("ws-1", max_cues=5001)

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
        self.assertEqual([row[0] for row in result["cue_index"]["rows"]], [list_id, group_id, cue_id])
        self.assertEqual(result["cue_index"]["rows"][0][4], "Cue List")
        self.assertEqual(result["cue_index"]["rows"][1][4], "Group")
        self.assertEqual(result["cue_index"]["rows"][2][4], "Light")
        self.assertEqual(result["cue_index"]["rows"][2][12], True)
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
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", server.received)
        self.assertNotIn(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys", server.received)

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
        self.assertEqual(result["cue_index"]["total_cue_ids"], 1)
        self.assertEqual(result["cue_index"]["indexed_count"], 1)

    def test_workspace_overview_marks_depth_truncation(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5", "port": 53000}],
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": "list-id", "name": "Main", "type": "Cue List", "armed": True, "flagged": False}
            ],
            "/workspace/ws-1/cueLists/uniqueIDs": ["list-id", "child-id"],
            "/workspace/ws-1/cue/list-id/children/shallow": [],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", max_depth=0, max_cues=10)

        self.assertTrue(result["limits"]["truncated"])
        self.assertIn("max_depth", result["limits"]["truncation_reasons"])
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
        self.assertIn("max_cues", result["limits"]["truncation_reasons"])
        self.assertEqual(result["summary"]["inspected_cues"], 2)
        self.assertEqual(result["summary"]["returned_cues"], 1)
        self.assertEqual(result["summary"]["total_cue_ids_status"], "partial")
        self.assertEqual(result["limits"]["count_status"]["returned_cues"], 1)
        self.assertEqual(len(result["cue_lists"]), 1)

    def test_workspace_overview_marks_child_read_errors_as_partial_counts(self) -> None:
        list_id = "11111111-1111-4111-8111-111111111111"

        class FailingChildrenClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(
                        data=[
                            {
                                "uniqueID": list_id,
                                "number": "TEKNO",
                                "name": "Main",
                                "displayName": "TEKNO Main",
                                "type": "Cue List",
                                "armed": True,
                                "flagged": False,
                                "colorName": "red",
                                "duration": 12.5,
                                "isBroken": False,
                                "isWarning": False,
                            }
                        ],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue/{list_id}/children/shallow":
                    raise RuntimeError("children read failed")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(FailingChildrenClient())  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", max_depth=2, include_cue_index=False)

        self.assertTrue(result["limits"]["truncated"])
        self.assertIn("child_read_error", result["limits"]["truncation_reasons"])
        self.assertEqual(result["limits"]["child_read_errors"][0]["cue_ref"], list_id)
        self.assertEqual(result["limits"]["child_read_errors"][0]["number"], "TEKNO")
        self.assertEqual(result["limits"]["child_read_errors"][0]["name"], "Main")
        self.assertEqual(result["limits"]["child_read_errors"][0]["displayName"], "TEKNO Main")
        self.assertEqual(result["limits"]["child_read_errors"][0]["type"], "Cue List")
        self.assertEqual(result["limits"]["child_read_errors"][0]["parent_id"], None)
        self.assertEqual(result["limits"]["child_read_errors"][0]["depth"], 0)
        self.assertEqual(result["limits"]["child_read_errors"][0]["colorName"], "red")
        self.assertEqual(result["limits"]["child_read_errors"][0]["duration"], 12.5)
        self.assertFalse(result["limits"]["child_read_errors"][0]["isBroken"])
        self.assertFalse(result["limits"]["child_read_errors"][0]["isWarning"])
        self.assertEqual(result["summary"]["total_cue_ids_status"], "partial")
        self.assertEqual(result["summary"]["health_counts_status"], "partial")
        self.assertIsNone(result["summary"]["broken"])
        self.assertIn("Some container children could not be read", " ".join(result["warnings"]))
        self.assertIn(list_id, result["errors"])

    def test_workspace_overview_falls_back_to_child_unique_ids_when_shallow_times_out(self) -> None:
        list_id = "list-1"
        group_id = "TEKNO"

        class FallbackChildrenClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": list_id, "name": "Main", "type": "Cue List"}],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue/{list_id}/children/shallow":
                    return SimpleNamespace(
                        data=[
                            {
                                "uniqueID": group_id,
                                "number": "TEKNO",
                                "name": "TENEMOS UN PROBLEMA",
                                "displayName": "TEKNO display",
                                "type": "Group",
                                "colorName": "red",
                                "duration": 12.5,
                                "isBroken": False,
                                "isWarning": True,
                            }
                        ],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply to children/shallow")
                if address == f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow":
                    return SimpleNamespace(data=["child-1", "child-2"], status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        client = FallbackChildrenClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", max_depth=2, include_cue_index=False)

        self.assertIn(f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow", client.requests)
        self.assertEqual(result["summary"]["inspected_cues"], 2)
        self.assertEqual(result["summary"]["returned_cues"], 2)
        self.assertEqual(result["known_total_cues"], 4)
        self.assertEqual(result["known_total_cues_status"], "partial")
        self.assertEqual(result["known_total_cues_meaning"], "cue_items_including_cue_lists")
        self.assertEqual(result["summary"]["known_total_cues"], 4)
        self.assertEqual(result["summary"]["known_total_cues_meaning"], "cue_items_including_cue_lists")
        self.assertEqual(
            result["limits"]["count_status"]["known_total_cues_meaning"],
            "cue_items_including_cue_lists",
        )
        group = result["cue_lists"][0]["children"][0]
        self.assertEqual(group["child_count"], 2)
        self.assertEqual(group["child_count_source"], "children/uniqueIDs/shallow")
        self.assertEqual(group["child_metadata_status"], "timeout")
        self.assertTrue(group["fallback_used"])
        error = result["limits"]["child_read_errors"][0]
        self.assertEqual(error["cue_ref"], group_id)
        self.assertEqual(error["number"], "TEKNO")
        self.assertEqual(error["displayName"], "TEKNO display")
        self.assertEqual(error["parent_id"], list_id)
        self.assertEqual(error["cue_list_id"], list_id)
        self.assertEqual(error["colorName"], "red")
        self.assertEqual(error["duration"], 12.5)
        self.assertFalse(error["isBroken"])
        self.assertTrue(error["isWarning"])
        self.assertTrue(error["fallback_used"])
        self.assertEqual(error["child_count"], 2)
        self.assertEqual(error["child_count_source"], "children/uniqueIDs/shallow")
        self.assertEqual(error["child_metadata_status"], "timeout")
        self.assertIn(group_id, result["errors"])
        warning_text = " ".join(result["warnings"])
        self.assertIn("fallback counted ID-only children", warning_text)
        self.assertIn("Metadata, tree, and health counts are partial", warning_text)
        self.assertEqual(result["agent_summary"]["known_total_cue_items"], 4)
        self.assertEqual(result["agent_summary"]["cue_lists"], 1)

    def test_workspace_overview_uses_tcp_for_large_child_metadata_before_id_only_fallback(self) -> None:
        list_id = "list-1"
        group_id = "group-1"
        child_id = "child-1"

        class TcpChildClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.udp_requests: list[str] = []
                self.tcp_requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.udp_requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": list_id, "name": "Main", "type": "Cue List"}], status="ok")
                if address == f"/workspace/ws-1/cue/{list_id}/children/shallow":
                    return SimpleNamespace(data=[{"uniqueID": group_id, "name": "Big Group", "type": "Group"}], status="ok")
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply to children/shallow")
                if address == f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow":
                    raise AssertionError("ID-only fallback should not run after TCP metadata success")
                raise AssertionError(f"Unexpected UDP request: {address}")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.tcp_requests.append(address)
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": child_id, "name": "Audio Child", "type": "Audio"}],
                        status="ok",
                    )
                raise AssertionError(f"Unexpected TCP request: {address}")

        client = TcpChildClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", max_depth=3, include_cue_index=False)

        self.assertEqual(client.tcp_requests, [f"/workspace/ws-1/cue/{group_id}/children/shallow"])
        self.assertEqual(result["known_total_cues"], 3)
        self.assertEqual(result["known_total_cues_status"], "known")
        self.assertFalse(result["limits"]["truncated"])
        self.assertEqual(result["limits"]["child_read_errors"], [])
        group = result["cue_lists"][0]["children"][0]
        self.assertEqual(group["child_count"], 1)
        self.assertEqual(group["child_read_transport"], "tcp_fallback")
        self.assertNotIn(f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow", client.udp_requests)

    def test_workspace_overview_expands_cart_children(self) -> None:
        cart_id = "cart-1"
        midi_id = "midi-1"
        timecode_id = "timecode-1"

        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/showMode": False,
            "/workspace/ws-1/cueLists/shallow": [
                {"uniqueID": "list-1", "name": "Main", "type": "Cue List"},
                {"uniqueID": cart_id, "name": "Cue Cart", "type": "Cart"},
            ],
            "/workspace/ws-1/cue/list-1/children/shallow": [],
            f"/workspace/ws-1/cue/{cart_id}/children/shallow": [
                {
                    "uniqueID": midi_id,
                    "name": "midi note",
                    "type": "MIDI",
                    "cartPosition": [0, 0],
                    "cartPosition/row": 0,
                    "cartPosition/column": 0,
                },
                {
                    "uniqueID": timecode_id,
                    "name": "timecode out",
                    "type": "MTC",
                    "cartPosition": [0, 1],
                    "cartPosition/row": 0,
                    "cartPosition/column": 1,
                },
            ],
        }

        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))
            result = reader.get_workspace_overview("ws-1", max_depth=1, include_cue_index=False)

        cart = result["cue_lists"][1]
        self.assertEqual(cart["type"], "Cart")
        self.assertEqual(cart["child_count"], 2)
        self.assertEqual([child["type"] for child in cart["children"]], ["MIDI", "MTC"])
        self.assertEqual(cart["children"][0]["cartPosition"], [0, 0])
        self.assertEqual(result["summary"]["types"]["Cart"], 1)
        self.assertEqual(result["summary"]["types"]["MIDI"], 1)
        self.assertEqual(result["summary"]["types"]["MTC"], 1)
        self.assertIn(f"/workspace/ws-1/cue/{cart_id}/children/shallow", server.received)

    def test_workspace_overview_cart_fallback_counts_id_only_children(self) -> None:
        cart_id = "cart-1"

        class CartFallbackClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": cart_id, "name": "Cue Cart", "type": "Cart"}], status="ok")
                if address == f"/workspace/ws-1/cue/{cart_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply to children/shallow")
                if address == f"/workspace/ws-1/cue/{cart_id}/children/uniqueIDs/shallow":
                    return SimpleNamespace(data=["midi-1", "timecode-1", "midi-file-1"], status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(CartFallbackClient())  # type: ignore[arg-type]
        result = reader.get_workspace_overview("ws-1", max_depth=1, include_cue_index=False)

        cart = result["cue_lists"][0]
        self.assertEqual(cart["type"], "Cart")
        self.assertEqual(cart["child_count"], 3)
        self.assertEqual(cart["child_count_source"], "children/uniqueIDs/shallow")
        self.assertTrue(cart["fallback_used"])
        self.assertEqual(result["known_total_cues"], 4)
        self.assertEqual(result["agent_summary"]["id_only_counted_cues"], 3)
        self.assertEqual(result["limits"]["child_read_errors"][0]["type"], "Cart")
        self.assertEqual(result["agent_summary"]["metadata_inspected_cues"], 1)
        self.assertEqual(result["agent_summary"]["workspace_total_for_humans"], "3 cues in 1 lists")
        self.assertEqual(result["agent_summary"]["workspace_total_status"], "partial")
        self.assertTrue(result["agent_summary"]["metadata_partial"])
        self.assertEqual(len(result["agent_summary"]["main_partial_branches"]), 1)
        self.assertEqual(result["agent_summary"]["main_partial_branches"][0]["type"], "Cart")

    def test_workspace_overview_root_read_timeout_is_not_empty_healthy_workspace(self) -> None:
        class RootTimeoutClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply to cueLists/shallow")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(RootTimeoutClient())  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", max_depth=0, include_cue_index=False)

        self.assertEqual(result["cue_count"], 0)
        self.assertEqual(result["cue_count_meaning"], "inspected_cues")
        self.assertIsNone(result["known_total_cues"])
        self.assertEqual(result["known_total_cues_status"], "unknown")
        self.assertEqual(result["summary"]["total_cue_ids_status"], "unknown")
        self.assertEqual(result["summary"]["known_total_cues_status"], "unknown")
        self.assertTrue(result["limits"]["truncated"])
        self.assertIn("root_read_error", result["limits"]["truncation_reasons"])
        self.assertIn("cueLists/shallow", result["errors"])
        self.assertIn("Root cue list read failed", " ".join(result["warnings"]))

    def test_workspace_overview_global_count_is_opt_in(self) -> None:
        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": "list-1", "type": "Cue List"}], status="ok")
                if address == "/workspace/ws-1/cue/list-1/children/shallow":
                    return SimpleNamespace(data=[], status="ok")
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=["list-1", "child-1"], status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", include_cue_index=False, include_global_count=False)

        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", client.requests)
        self.assertEqual(result["known_total_cues"], 1)
        self.assertEqual(result["known_total_cues_source"], "bounded_shallow_traversal")

    def test_workspace_overview_depth_zero_without_global_count_keeps_human_total_unknown(self) -> None:
        class DepthZeroClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": f"list-{index}", "type": "Cue List"} for index in range(7)],
                        status="ok",
                    )
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(DepthZeroClient())  # type: ignore[arg-type]

        result = reader.get_workspace_overview(
            "ws-1",
            max_depth=0,
            include_cue_index=False,
            include_global_count=False,
        )

        self.assertEqual(result["known_total_cues"], 7)
        self.assertEqual(result["agent_summary"]["cue_lists"], 7)
        self.assertIsNone(result["agent_summary"]["workspace_total_for_humans"])
        self.assertEqual(result["agent_summary"]["workspace_total_status"], "inspected_only")

    def test_workspace_overview_global_count_opt_in_uses_unique_ids(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-1", "type": "Cue List"}],
            "/workspace/ws-1/cue/list-1/children/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": ["list-1", "child-1", "child-2"],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview("ws-1", include_cue_index=False, include_global_count=True)

        self.assertIn("/workspace/ws-1/cueLists/uniqueIDs", server.received)
        self.assertEqual(result["known_total_cues"], 3)
        self.assertEqual(result["known_total_cues_status"], "known")
        self.assertEqual(result["known_total_cues_source"], "cueLists/uniqueIDs")
        self.assertEqual(result["known_total_cues_meaning"], "cue_items_including_cue_lists")
        self.assertTrue(result["summary"]["global_unique_ids_used"])

    def test_workspace_overview_global_count_is_bounded_by_requested_limits(self) -> None:
        responses = {
            "/workspaces": [{"uniqueID": "ws-1", "displayName": "demo.qlab5"}],
            "/workspace/ws-1/cueLists/shallow": [{"uniqueID": "list-1", "type": "Cue List"}],
            "/workspace/ws-1/cue/list-1/children/shallow": [],
            "/workspace/ws-1/cueLists/uniqueIDs": ["list-1", "child-1", "child-2", "child-3"],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_overview(
                "ws-1",
                max_cues=2,
                max_index_cues=2,
                include_cue_index=False,
                include_global_count=True,
            )

        self.assertEqual(result["known_total_cues"], 2)
        self.assertEqual(result["known_total_cues_status"], "partial")
        self.assertIn("partial", " ".join(result["warnings"]))

    def test_workspace_overview_global_count_uses_tcp_after_udp_timeout(self) -> None:
        class GlobalTcpClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.udp_requests: list[str] = []
                self.tcp_requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.udp_requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": "list-1", "type": "Cue List"}], status="ok")
                if address == "/workspace/ws-1/cue/list-1/children/shallow":
                    return SimpleNamespace(data=[], status="ok")
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    raise OscTimeoutError("Timed out waiting for QLab reply to cueLists/uniqueIDs")
                if address == "/workspace/ws-1/cueLists/uniqueIDs/shallow":
                    raise AssertionError("Root ID fallback should not run after TCP global count success")
                raise AssertionError(f"Unexpected UDP request: {address}")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.tcp_requests.append(address)
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    return SimpleNamespace(data=["list-1", "child-1", "child-2"], status="ok")
                raise AssertionError(f"Unexpected TCP request: {address}")

        client = GlobalTcpClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", include_cue_index=False, include_global_count=True)

        self.assertEqual(client.tcp_requests, ["/workspace/ws-1/cueLists/uniqueIDs"])
        self.assertEqual(result["known_total_cues"], 3)
        self.assertEqual(result["known_total_cues_status"], "known")
        self.assertEqual(result["known_total_cues_source"], "cueLists/uniqueIDs")
        self.assertEqual(result["limits"]["count_status"]["global_count_read_transport"], "tcp_fallback")
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", result["errors"] or {})
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs/shallow", client.udp_requests)

    def test_workspace_overview_global_count_timeout_does_not_break_overview(self) -> None:
        class GlobalTimeoutClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": "list-1", "type": "Cue List"}], status="ok")
                if address == "/workspace/ws-1/cue/list-1/children/shallow":
                    return SimpleNamespace(data=[], status="ok")
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    raise OscTimeoutError("Timed out waiting for QLab reply to cueLists/uniqueIDs")
                if address == "/workspace/ws-1/cueLists/uniqueIDs/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply to cueLists/uniqueIDs/shallow")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(GlobalTimeoutClient())  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", include_cue_index=False, include_global_count=True)

        self.assertEqual(result["summary"]["inspected_cues"], 1)
        self.assertIsNone(result["known_total_cues"])
        self.assertEqual(result["known_total_cues_status"], "timeout")
        self.assertIn("cueLists/uniqueIDs", result["errors"])
        self.assertIn("Global cue count was requested", " ".join(result["warnings"]))

    def test_workspace_overview_global_count_falls_back_by_roots_after_global_timeout(self) -> None:
        class GlobalFallbackClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/showMode":
                    return SimpleNamespace(data=False, status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": "list-1", "type": "Cue List"}], status="ok")
                if address == "/workspace/ws-1/cue/list-1/children/shallow":
                    return SimpleNamespace(data=[], status="ok")
                if address == "/workspace/ws-1/cueLists/uniqueIDs":
                    raise OscTimeoutError("Timed out waiting for QLab reply to cueLists/uniqueIDs")
                if address == "/workspace/ws-1/cueLists/uniqueIDs/shallow":
                    return SimpleNamespace(data=["list-1"], status="ok")
                if address == "/workspace/ws-1/cue/list-1/children/uniqueIDs":
                    return SimpleNamespace(
                        data=[
                            {"uniqueID": "group-1", "cues": [{"uniqueID": "child-1", "cues": []}]},
                            {"uniqueID": "child-2", "cues": []},
                        ],
                        status="ok",
                    )
                raise AssertionError(f"Unexpected request: {address}")

        client = GlobalFallbackClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.get_workspace_overview("ws-1", include_cue_index=False, include_global_count=True)

        self.assertIn("/workspace/ws-1/cueLists/uniqueIDs/shallow", client.requests)
        self.assertIn("/workspace/ws-1/cue/list-1/children/uniqueIDs", client.requests)
        self.assertEqual(result["known_total_cues"], 4)
        self.assertEqual(result["known_total_cues_status"], "known")
        self.assertEqual(
            result["known_total_cues_source"],
            "cueLists/uniqueIDs_fallback:cueLists/uniqueIDs/shallow+children/uniqueIDs",
        )
        self.assertIn("cueLists/uniqueIDs", result["errors"])
        self.assertIn("per-root uniqueID fallback", " ".join(result["warnings"]))

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
        self.assertIn(
            {"section": "network", "kind": "network_patch", "ref": "EOS", "name": "EOS", "uniqueID": "network-1"},
            result["available_detail_requests"],
        )
        self.assertIn(
            {
                "section": "video",
                "kind": "stage",
                "ref": "Main Stage",
                "name": "Main Stage",
                "uniqueID": "stage-1",
            },
            result["available_detail_requests"],
        )
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
                    {
                        "ipAddress": "127.0.0.1",
                        "port": 53000,
                        "passcode": "9999",
                        "oscPasscode": "compound-secret",
                        "apiToken": "token-secret",
                        "authSecret": "auth-secret",
                    }
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
        self.assertNotIn("compound-secret", serialized)
        self.assertNotIn("token-secret", serialized)
        self.assertNotIn("auth-secret", serialized)
        self.assertEqual(result["details"]["destinations"][0]["passcode"], "[redacted]")
        self.assertEqual(result["details"]["destinations"][0]["oscPasscode"], "[redacted]")
        self.assertEqual(result["details"]["destinations"][0]["apiToken"], "[redacted]")
        self.assertEqual(result["details"]["destinations"][0]["authSecret"], "[redacted]")
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
        self.assertIn({"section": "light", "kind": "light_patch", "ref": None}, result["available_detail_requests"])
        self.assertIn({"section": "general", "kind": "all", "ref": None}, result["available_detail_requests"])
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

    def test_workspace_settings_summary_lists_all_detail_request_kinds(self) -> None:
        responses = {
            "/workspace/ws-1/settings/audio/patchList": [{"name": "Main", "uniqueID": "audio-out-1"}],
            "/workspace/ws-1/settings/mic/patchList": [{"name": "Mic", "uniqueID": "audio-in-1"}],
            "/workspace/ws-1/settings/audio/cueOutputChannelCounts": {},
            "/workspace/ws-1/settings/audio/outputChannelNames": {},
            "/workspace/ws-1/settings/audio/maps": [{"name": "Map", "uniqueID": "map-1"}],
            "/workspace/ws-1/settings/video/inputPatchList": [{"name": "Camera", "uniqueID": "video-in-1"}],
            "/workspace/ws-1/settings/video/routes": [{"name": "Projector", "uniqueID": "route-1"}],
            "/workspace/ws-1/settings/video/stages": [{"name": "TELON", "uniqueID": "stage-1"}],
            "/workspace/ws-1/settings/video/stageID/stage-1/regions": [],
            "/workspace/ws-1/settings/network/patchList": [{"name": "OSC", "uniqueID": "network-1"}],
            "/workspace/ws-1/settings/midi/patchList": [{"name": "MIDI", "uniqueID": "midi-1"}],
            "/workspace/ws-1/settings/general/minGoTime": 0.4,
            "/workspace/ws-1/settings/general/selectionIsPlayhead": True,
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings("ws-1")

        request_keys = {
            (request["section"], request["kind"], request["ref"])
            for request in result["available_detail_requests"]
        }
        self.assertEqual(result["mode"], "summary")
        self.assertIn(("audio", "output_patch", "Main"), request_keys)
        self.assertIn(("audio", "input_patch", "Mic"), request_keys)
        self.assertIn(("audio", "audio_map", "Map"), request_keys)
        self.assertIn(("video", "video_input_patch", "Camera"), request_keys)
        self.assertIn(("video", "route", "Projector"), request_keys)
        self.assertIn(("video", "stage", "TELON"), request_keys)
        self.assertIn(("network", "network_patch", "OSC"), request_keys)
        self.assertIn(("midi", "midi_patch", "MIDI"), request_keys)
        self.assertIn(("light", "light_patch", None), request_keys)
        self.assertIn(("general", "all", None), request_keys)

    def test_workspace_settings_details_mode_single_request(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {"name": "QLab Loopback", "uniqueID": "network-1", "destinations": [{"ipAddress": "127.0.0.1"}]}
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings(
                "ws-1",
                mode="details",
                requests=[{"section": "network", "kind": "network_patch", "ref": "QLab Loopback"}],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_count"], 1)
        self.assertEqual(result["succeeded_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["results"][0]["section"], "network")
        self.assertEqual(result["results"][0]["kind"], "network_patch")
        self.assertTrue(result["results"][0]["details"]["destination_present"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_settings_details_mode_batch_mixed_requests(self) -> None:
        responses = {
            "/workspace/ws-1/settings/audio/patchList": [{"name": "Main", "uniqueID": "audio-1"}],
            "/workspace/ws-1/settings/video/stages": [{"name": "TELON", "uniqueID": "stage-1"}],
            "/workspace/ws-1/settings/video/stageID/stage-1/regions": [{"name": "A", "uniqueID": "region-1"}],
            "/workspace/ws-1/settings/light/patch": {"instruments": [{"name": "1"}], "groups": []},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings(
                "ws-1",
                mode="details",
                requests=[
                    {"section": "audio", "kind": "output_patch", "ref": "Main"},
                    {"section": "video", "kind": "stage", "ref": "TELON"},
                    {"section": "light", "kind": "light_patch"},
                ],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_count"], 3)
        self.assertEqual(result["succeeded_count"], 3)
        self.assertEqual([item["kind"] for item in result["results"]], ["output_patch", "stage", "light_patch"])
        self.assertEqual(result["results"][1]["details"]["regions"][0]["uniqueID"], "region-1")
        self.assertEqual(result["results"][2]["details"]["summary"]["instrument_count"], 1)
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/audio/patchList",
                "/workspace/ws-1/settings/video/stages",
                "/workspace/ws-1/settings/video/stageID/stage-1/regions",
                "/workspace/ws-1/settings/light/patch",
            ],
        )

    def test_workspace_settings_details_mode_preserves_choices_for_omitted_ref(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {"name": "OSC A", "uniqueID": "network-1"},
                {"name": "OSC B", "uniqueID": "network-2"},
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings(
                "ws-1",
                mode="details",
                requests=[{"section": "network", "kind": "network_patch"}],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["requested_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertIsNone(result["results"][0]["details"])
        self.assertEqual(len(result["results"][0]["choices"]), 2)
        self.assertIn("Multiple settings items", result["results"][0]["message"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_settings_details_mode_valid_and_invalid_requests_partial_success(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {"name": "OSC", "uniqueID": "network-1", "destinations": [{"ipAddress": "127.0.0.1"}]}
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings(
                "ws-1",
                mode="details",
                requests=[
                    {"section": "network", "kind": "network_patch", "ref": "OSC"},
                    {"section": "audio", "kind": "network_patch", "ref": "bad"},
                ],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["requested_count"], 2)
        self.assertEqual(result["succeeded_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertTrue(result["results"][0]["ok"])
        self.assertFalse(result["results"][1]["ok"])
        self.assertIn("Audio details support", result["errors"]["request_1"])
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_settings_details_mode_exhaustive_warns_and_redacts_credentials(self) -> None:
        responses = {
            "/workspace/ws-1/settings/network/patchList": [
                {
                    "name": "OSC",
                    "uniqueID": "network-1",
                    "destinations": [{"ipAddress": "127.0.0.1", "port": 53000, "passcode": "secret"}],
                }
            ],
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_settings(
                "ws-1",
                mode="details",
                profile="exhaustive",
                requests=[{"section": "network", "kind": "network_patch", "ref": "OSC"}],
            )

        serialized = json.dumps(result)
        self.assertTrue(result["ok"])
        self.assertIn("deepest allowlisted", result["warnings"][0])
        self.assertIn("127.0.0.1", serialized)
        self.assertIn("53000", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(result["results"][0]["details"]["destinations"][0]["passcode"], "[redacted]")
        self.assertEqual(result["results"][0]["redactions"][0]["reason"], "credential")
        self.assertEqual(server.received, ["/workspace/ws-1/settings/network/patchList"])

    def test_workspace_setting_details_technical_audio_map_uses_focused_map_id_read(self) -> None:
        responses = {
            "/workspace/ws-1/settings/audio/maps": [
                {"name": "Stereo", "uniqueID": "map-1", "width": 1000, "height": 1000}
            ],
            "/workspace/ws-1/settings/audio/mapID/map-1": {
                "name": "Stereo",
                "uniqueID": "map-1",
                "width": 1000,
                "height": 1000,
                "marks": [{"name": "Left", "levels": [0, -60]}],
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_workspace_setting_details(
                "ws-1",
                section="audio",
                kind="audio_map",
                ref="Stereo",
                profile="technical",
            )

        self.assertEqual(result["details"]["marks"][0]["levels"], [0, -60])
        self.assertEqual(
            server.received,
            [
                "/workspace/ws-1/settings/audio/maps",
                "/workspace/ws-1/settings/audio/mapID/map-1",
            ],
        )

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

        self.assertEqual(client.udp_requests, ["/workspaces", "/workspace/ws-1/settings/light/patch"])
        self.assertEqual(client.tcp_requests, ["/workspace/ws-1/settings/light/patch"])
        self.assertIsNone(result["errors"])
        self.assertEqual(result["details"]["summary"]["instrument_count"], 1)
        self.assertEqual(result["details"]["summary"]["read_transport"], "tcp_fallback")
        self.assertIn("does not imply output failure", result["details"]["summary"]["read_transport_meaning"])

    def test_workspace_setting_details_light_patch_tcp_denied_returns_clear_error_without_secret(self) -> None:
        secret = "server-passcode"

        class DeniedFallbackClient:
            config = QLabConfig(passcode=secret)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                raise OscTimeoutError("udp too small")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                raise QLabReplyError("denied", "not connected", address.lstrip("/"))

        reader = QLabReader(DeniedFallbackClient())  # type: ignore[arg-type]

        result = reader.get_workspace_setting_details("ws-1", section="light", kind="light_patch")

        serialized = json.dumps(result)
        self.assertIn("light.patch", result["errors"])
        self.assertIn("TCP fallback also failed", result["errors"]["light.patch"])
        self.assertEqual(result["details"]["summary"]["patch_present"], False)
        self.assertNotIn(secret, serialized)

    def test_workspace_settings_details_batch_keeps_successes_when_light_tcp_fallback_denied(self) -> None:
        class MixedFallbackClient:
            config = QLabConfig(passcode="server-passcode")

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspace/ws-1/settings/network/patchList":
                    return SimpleNamespace(data=[{"name": "OSC", "uniqueID": "network-1"}])
                if address == "/workspace/ws-1/settings/light/patch":
                    raise OscTimeoutError("udp too small")
                raise AssertionError(address)

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                raise QLabReplyError("denied", "not connected", address.lstrip("/"))

        reader = QLabReader(MixedFallbackClient())  # type: ignore[arg-type]

        result = reader.get_workspace_settings(
            "ws-1",
            mode="details",
            requests=[
                {"section": "network", "kind": "network_patch", "ref": "OSC"},
                {"section": "light", "kind": "light_patch"},
            ],
        )

        serialized = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["succeeded_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertTrue(result["results"][0]["ok"])
        self.assertFalse(result["results"][1]["ok"])
        self.assertIn("Workspace setting detail request failed", result["errors"]["request_1"])
        self.assertNotIn("server-passcode", serialized)

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
                if address == "/workspace/ws-1/cue/list-1/children/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": cue_id, "number": "1", "name": "Intro", "type": "Audio"}],
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
        self.assertEqual(overview["cue_count"], 2)
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
        self.assertEqual(server.received[0], "/workspace/ws-1/cueLists/shallow")
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", server.received)

    def test_query_cues_supports_5000_scan_limit_before_expensive_reads(self) -> None:
        cue_ids = [f"{index:032d}-aaaa-bbbb-cccc-{index:012d}" for index in range(5001)]
        cues = [{"uniqueID": cue_id, "type": "Audio"} for cue_id in cue_ids]

        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=cues, status="ok")
                cue_id = address.split("/cue_id/", 1)[1].split("/", 1)[0]
                return SimpleNamespace(data={"uniqueID": cue_id, "type": "Audio"}, status="ok")

        client = CountingClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.query_cues("ws-1", "type", "Audio", max_results=5000, max_cues_scanned=5000)

        self.assertEqual(result["scanned_count"], 5000)
        self.assertEqual(result["returned_count"], 5000)
        self.assertTrue(result["truncated"])
        self.assertIn("max_cues_scanned", result["truncation_reasons"])
        self.assertNotIn("/workspace/ws-1/cueLists/uniqueIDs", client.requests)
        self.assertFalse(any(f"/cue_id/{cue_ids[5000]}/valuesForKeys" in request for request in client.requests))

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
        self.assertEqual(scan_limit["total_cue_ids"], 2)
        self.assertTrue(scan_limit["truncated"])
        self.assertEqual(scan_limit["truncation_reasons"], ["max_cues_scanned"])
        self.assertEqual(scan_limit["query_completeness"], "partial")
        self.assertEqual(scan_limit["query_completeness_reasons"], ["max_cues_scanned"])

    def test_query_cues_reports_id_only_unscanned_branches_as_partial(self) -> None:
        list_id = "list-1"
        group_id = "group-tekno"
        class QueryFallbackClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": list_id, "name": "Main", "type": "Cue List"}], status="ok")
                if address == f"/workspace/ws-1/cue/{list_id}/children/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": group_id, "number": "TEKNO", "name": "TEKNO", "type": "Group"}],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply")
                if address == f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow":
                    return SimpleNamespace(data=["child-1", "child-2"], status="ok")
                if address.endswith("/valuesForKeys"):
                    cue_id = args[0] if args else None
                    keys = args[1] if len(args) > 1 else []
                    payload = {key: None for key in keys}
                    payload["uniqueID"] = cue_id
                    payload["type"] = "Group"
                    return SimpleNamespace(data=payload, status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(QueryFallbackClient())  # type: ignore[arg-type]
        result = reader.query_cues("ws-1", "type", "Group", max_cues_scanned=5000)

        self.assertEqual(result["query_completeness"], "partial")
        self.assertEqual(result["query_completeness_reasons"], ["id_only_unscanned"])
        self.assertEqual(result["id_only_unscanned_count"], 2)
        self.assertEqual(result["scanned_count"], 2)
        self.assertEqual(result["total_cue_ids"], 2)
        self.assertEqual(len(result["omitted_branches"]), 1)
        self.assertEqual(result["omitted_branches"][0]["number"], "TEKNO")
        self.assertEqual(result["omitted_branches"][0]["child_count"], 2)
        self.assertEqual(result["omitted_branches"][0]["child_count_source"], "children/uniqueIDs/shallow")
        self.assertTrue(result["omitted_branches"][0]["fallback_used"])
        self.assertIn("scanned only cues with metadata", " ".join(result["warnings"]))
        self.assertFalse(result["scanned_all_cues"])
        self.assertFalse(result["result_limited"])

    def test_query_cues_uses_tcp_child_metadata_before_id_only_partial_branch(self) -> None:
        list_id = "list-1"
        group_id = "group-tekno"
        child_id = "audio-1"

        class QueryTcpClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.udp_requests: list[str] = []
                self.tcp_requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.udp_requests.append(address)
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": list_id, "name": "Main", "type": "Cue List"}], status="ok")
                if address == f"/workspace/ws-1/cue/{list_id}/children/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": group_id, "number": "TEKNO", "name": "TEKNO", "type": "Group"}],
                        status="ok",
                    )
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply")
                if address == f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow":
                    raise AssertionError("ID-only fallback should not run after TCP metadata success")
                if address.endswith("/valuesForKeys"):
                    cue_id = address.split("/cue/", 1)[1].split("/valuesForKeys", 1)[0]
                    keys = json.loads(args[0]) if args else []
                    payload = {key: None for key in keys}
                    payload["uniqueID"] = cue_id
                    payload["type"] = "Audio" if cue_id == child_id else "Group"
                    payload["name"] = "Audio Child" if cue_id == child_id else "TEKNO"
                    return SimpleNamespace(data=payload, status="ok")
                raise AssertionError(f"Unexpected UDP request: {address}")

            def request_tcp(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.tcp_requests.append(address)
                if address == f"/workspace/ws-1/cue/{group_id}/children/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": child_id, "name": "Audio Child", "type": "Audio"}],
                        status="ok",
                    )
                raise AssertionError(f"Unexpected TCP request: {address}")

        client = QueryTcpClient()
        reader = QLabReader(client)  # type: ignore[arg-type]

        result = reader.query_cues("ws-1", "type", "Audio", max_cues_scanned=5000)

        self.assertEqual(client.tcp_requests, [f"/workspace/ws-1/cue/{group_id}/children/shallow"])
        self.assertEqual(result["query_completeness"], "complete")
        self.assertEqual(result["id_only_unscanned_count"], 0)
        self.assertEqual(result["omitted_branches"], [])
        self.assertEqual(result["scanned_count"], 3)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["cues"][0]["uniqueID"], child_id)
        self.assertTrue(result["scanned_all_cues"])
        self.assertNotIn(f"/workspace/ws-1/cue/{group_id}/children/uniqueIDs/shallow", client.udp_requests)

    def test_query_cues_finds_cart_children_by_real_type(self) -> None:
        cart_id = "cart-1"
        midi_id = "midi-1"
        timecode_id = "timecode-1"

        class CartChildrenClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": cart_id, "name": "Cue Cart", "type": "Cart"}], status="ok")
                if address == f"/workspace/ws-1/cue/{cart_id}/children/shallow":
                    return SimpleNamespace(
                        data=[
                            {
                                "uniqueID": midi_id,
                                "name": "MIDI note",
                                "type": "MIDI",
                                "cartPosition": [0, 0],
                                "cartPosition/row": 0,
                                "cartPosition/column": 0,
                            },
                            {
                                "uniqueID": timecode_id,
                                "name": "Timecode out",
                                "type": "MTC",
                                "cartPosition": [0, 1],
                                "cartPosition/row": 0,
                                "cartPosition/column": 1,
                            },
                        ],
                        status="ok",
                    )
                if address.endswith("/valuesForKeys"):
                    if "/cue_id/" in address:
                        cue_id = address.split("/cue_id/", 1)[1].split("/valuesForKeys", 1)[0]
                    else:
                        cue_id = address.split("/cue/", 1)[1].split("/valuesForKeys", 1)[0]
                    keys = json.loads(args[0]) if args else []
                    values = {key: None for key in keys}
                    if cue_id == cart_id:
                        values.update({"uniqueID": cue_id, "name": "Cue Cart", "type": "Cart"})
                    else:
                        values.update(
                            {
                                "uniqueID": cue_id,
                                "number": "",
                                "name": "MIDI note" if cue_id == midi_id else "Timecode out",
                                "displayName": "MIDI note" if cue_id == midi_id else "Timecode out",
                                "listName": "MIDI note" if cue_id == midi_id else "Timecode out",
                                "type": "MIDI" if cue_id == midi_id else "MTC",
                                "armed": True,
                                "flagged": False,
                                "cartPosition": [0, 0] if cue_id == midi_id else [0, 1],
                                "cartPosition/row": 0,
                                "cartPosition/column": 0 if cue_id == midi_id else 1,
                            }
                        )
                    return SimpleNamespace(data=values, status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(CartChildrenClient())  # type: ignore[arg-type]
        midi = reader.query_cues("ws-1", "type", "MIDI", max_cues_scanned=5000)
        timecode = reader.query_cues("ws-1", "name_contains", "timecode", max_cues_scanned=5000)

        self.assertEqual(midi["matched_count"], 1)
        self.assertEqual(midi["cues"][0]["uniqueID"], midi_id)
        self.assertEqual(midi["cues"][0]["parent_id"], cart_id)
        self.assertEqual(midi["cues"][0]["cue_list_id"], cart_id)
        self.assertEqual(midi["cues"][0]["cartPosition"], [0, 0])
        self.assertEqual(timecode["matched_count"], 1)
        self.assertEqual(timecode["cues"][0]["uniqueID"], timecode_id)
        self.assertEqual(timecode["query_completeness"], "complete")

    def test_query_cues_reports_cart_id_only_children_as_partial(self) -> None:
        cart_id = "cart-1"

        class CartFallbackClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if address == "/workspaces":
                    return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(data=[{"uniqueID": cart_id, "name": "Cue Cart", "type": "Cart"}], status="ok")
                if address == f"/workspace/ws-1/cue/{cart_id}/children/shallow":
                    raise OscTimeoutError("Timed out waiting for QLab reply")
                if address == f"/workspace/ws-1/cue/{cart_id}/children/uniqueIDs/shallow":
                    return SimpleNamespace(data=["midi-1", "timecode-1", "midi-file-1"], status="ok")
                if address.endswith("/valuesForKeys"):
                    if "/cue_id/" in address:
                        cue_id = address.split("/cue_id/", 1)[1].split("/valuesForKeys", 1)[0]
                    else:
                        cue_id = address.split("/cue/", 1)[1].split("/valuesForKeys", 1)[0]
                    keys = json.loads(args[0]) if args else []
                    values = {key: None for key in keys}
                    values.update({"uniqueID": cue_id, "type": "Cart", "name": "Cue Cart"})
                    return SimpleNamespace(data=values, status="ok")
                raise AssertionError(f"Unexpected request: {address}")

        reader = QLabReader(CartFallbackClient())  # type: ignore[arg-type]
        result = reader.query_cues("ws-1", "type", "MIDI", max_cues_scanned=5000)

        self.assertEqual(result["query_completeness"], "partial")
        self.assertEqual(result["query_completeness_reasons"], ["id_only_unscanned"])
        self.assertEqual(result["id_only_unscanned_count"], 3)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["omitted_branches"][0]["type"], "Cart")
        self.assertEqual(result["omitted_branches"][0]["child_count"], 3)

    def test_query_cues_can_scan_more_than_default_when_explicitly_raised(self) -> None:
        cue_ids = [f"{index:032d}-aaaa-bbbb-cccc-{index:012d}" for index in range(501)]

        class CountingClient:
            config = QLabConfig(cache_ttl=0)

            def __init__(self) -> None:
                self.requests: list[str] = []

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                self.requests.append(address)
                if address == "/workspace/ws-1/cueLists/shallow":
                    return SimpleNamespace(
                        data=[{"uniqueID": cue_id, "type": "Audio"} for cue_id in cue_ids],
                        status="ok",
                    )
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

    def test_batch_cue_details_accepts_multiple_cues(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {"uniqueID": "cue-10", "number": "10", "name": "Ten"},
            "/workspace/ws-1/cue/11/valuesForKeys": {"uniqueID": "cue-11", "number": "11", "name": "Eleven"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", ["10", "11"])

        self.assertTrue(result["ok"])
        self.assertEqual(result["requested_count"], 2)
        self.assertEqual(result["succeeded_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual([item["properties"]["name"] for item in result["results"]], ["Ten", "Eleven"])

    def test_batch_cue_details_returns_individual_errors(self) -> None:
        class PartialClient:
            config = QLabConfig(cache_ttl=0)

            def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
                if "/cue/10/" in address:
                    return SimpleNamespace(data={"uniqueID": "cue-10", "number": "10", "name": "Ten"}, status="ok")
                raise RuntimeError("cue read failed")

        reader = QLabReader(PartialClient())  # type: ignore[arg-type]

        result = reader.get_cue_details("ws-1", ["10", ""])

        self.assertFalse(result["ok"])
        self.assertEqual(result["succeeded_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertIn("", result["errors"])
        self.assertEqual(result["results"][0]["properties"]["name"], "Ten")

    def test_batch_cue_details_counts_items_with_internal_errors_as_failures(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {"uniqueID": "cue-10", "number": "10", "name": "Ten"},
            "/workspace/ws-1/cue/missing/valuesForKeys": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/uniqueID": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/number": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/name": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/displayName": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/type": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/armed": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/flagged": {"status": "error", "data": "not found"},
            "/workspace/ws-1/cue/missing/colorName": {"status": "error", "data": "not found"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", ["10", "missing"], "basic_safe")

        self.assertFalse(result["ok"])
        self.assertEqual(result["requested_count"], 2)
        self.assertEqual(result["succeeded_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertIn("missing", result["errors"])
        self.assertIsNotNone(result["results"][1]["errors"])
        self.assertEqual(result["errors"]["missing"], "cue_ref_unresolved")
        self.assertEqual(result["results"][1]["errors"]["error_code"], "cue_ref_unresolved")
        self.assertLessEqual(len(result["results"][1]["errors"]), 2)
        self.assertIn("One or more cue detail reads failed", result["warnings"][0])

    def test_batch_cue_details_rejects_more_than_50_cues(self) -> None:
        reader = QLabReader(SimpleNamespace(config=QLabConfig()))  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "at most 50"):
            reader.get_cue_details("ws-1", [str(index) for index in range(51)])

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

    def test_inspector_safe_profile_reads_broader_non_sensitive_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "Projection",
                "type": "Video",
                "notes": "private note",
                "fileTarget": "/Users/stage/private.mov",
                "scriptSource": "display dialog \"private\"",
                "stage": {"regions": [{"id": "large"}]},
                "stage/regions": [{"id": "large"}],
                "stageName": "Main",
                "stage/size": [1920, 1080],
                "anchor/x": 0.5,
                "anchor/y": 0.5,
                "translation/x": 10,
                "translation/y": 20,
                "scale/x": 1.1,
                "scale/y": 0.9,
                "cropTop": 10,
                "cropBottom": 20,
                "opacity": 0.75,
                "rate": 1.0,
                "playCount": 2,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "inspector_safe")

        self.assertEqual(result["profile"], "inspector_safe")
        self.assertEqual(result["cue_type"], "Video")
        self.assertEqual(result["properties"]["anchor/x"], 0.5)
        self.assertEqual(result["properties"]["cropTop"], 10)
        self.assertEqual(result["properties"]["translation/x"], 10)
        self.assertEqual(result["properties"]["scale/y"], 0.9)
        self.assertEqual(result["sections"]["identity"]["type"], "Video")
        self.assertNotIn("notes", result["properties"])
        self.assertNotIn("fileTarget", result["properties"])
        self.assertNotIn("scriptSource", result["properties"])
        self.assertNotIn("stage", result["properties"])
        self.assertNotIn("stage/regions", result["properties"])
        self.assertTrue(all("/children" not in address for address in server.received))

    def test_inspector_safe_profile_covers_audio_light_and_group_without_children(self) -> None:
        cases = [
            (
                "Audio",
                {
                    "audioOutputPatchName": "Main",
                    "audioMap/size": [2, 2],
                    "rate": 0.95,
                    "startTime": 1.5,
                    "endTime": 12.0,
                    "playCount": 3,
                    "infiniteLoop": False,
                    "preservePitch": True,
                },
                ("rate", 0.95),
            ),
            (
                "Light",
                {
                    "lightCommandText": "1 thru 5 @ 80",
                    "alwaysCollate": True,
                    "subcontroller": False,
                },
                ("lightCommandText", "1 thru 5 @ 80"),
            ),
            (
                "Group",
                {"mode": 3, "playlist/doLoop": True, "playbackPositionID": "child-id"},
                ("mode", 3),
            ),
        ]
        for cue_type, extra_values, expected in cases:
            with self.subTest(cue_type=cue_type):
                values = {
                    "uniqueID": "cue-id",
                    "number": "10",
                    "name": f"{cue_type} cue",
                    "type": cue_type,
                    **extra_values,
                }
                with FakeQlabOscServer({"/workspace/ws-1/cue/10/valuesForKeys": values}) as server:
                    reader = QLabReader(client_for(server))

                    result = reader.get_cue_details("ws-1", "10", "inspector_safe")

                key, expected_value = expected
                self.assertEqual(result["properties"][key], expected_value)
                self.assertTrue(all("/children" not in address for address in server.received))

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
                {
                    "lightCommandText": "1 thru 5 @ 80",
                    "alwaysCollate": True,
                    "subcontroller": False,
                    "parameterValues": {"intensity": 80},
                    "parameterFadesEnabled": {"intensity": True},
                },
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

    def test_auto_light_details_keep_dashboard_and_fixture_values_out_of_type_specific(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "LX",
                "displayName": "LX",
                "type": "Light",
                "lightCommandText": "1 = 50",
                "alwaysCollate": True,
                "subcontroller": False,
                "parameterValues": {"intensity": 80},
                "parameterFadesEnabled": {"intensity": True},
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "auto")

        type_specific = result["sections"]["type_specific"]
        self.assertEqual(type_specific["lightCommandText"], "1 = 50")
        self.assertTrue(type_specific["alwaysCollate"])
        self.assertFalse(type_specific["subcontroller"])
        self.assertNotIn("parameterValues", type_specific)
        self.assertNotIn("parameterFadesEnabled", type_specific)

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

    def test_passcode_connect_is_reused_for_following_workspace_requests(self) -> None:
        responses = {
            "/workspace/ws-1/connect": "ok:view|edit",
            "/workspace/ws-1/showMode": False,
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
            client = QLabOscClient(config)

            client.request("/workspace/ws-1/connect", "5983")
            reply = client.request("/workspace/ws-1/showMode", workspace_id="ws-1")

        self.assertFalse(reply.data)
        self.assertEqual(server.received, ["/workspace/ws-1/connect", "/workspace/ws-1/showMode"])

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

    def test_exhaustive_profile_includes_sensitive_heavy_and_deep_allowlisted_keys(self) -> None:
        exhaustive = properties_for_profile("exhaustive")

        for key in (
            "notes",
            "fileTarget",
            "scriptSource",
            "stage",
            "stage/regions",
            "audioMap/objects",
            "audioOutputPatch/routing",
            "levels",
            "anchor",
            "cueSize",
            "text/format/shadowOffset/width",
            "fadeEntries",
            "devampType",
        ):
            self.assertIn(key, exhaustive)
        self.assertNotIn("stage", properties_for_profile("auto"))
        self.assertNotIn("fileTarget", properties_for_profile("auto"))
        self.assertNotIn("stage", properties_for_profile("inspector_safe"))
        self.assertNotIn("fileTarget", properties_for_profile("inspector_safe"))
        self.assertNotIn("audioOutputPatch/routing", properties_for_profile("inspector_safe"))
        self.assertNotIn("text/format/shadowOffset/width", properties_for_profile("inspector_safe"))

    def test_exhaustive_video_details_include_heavy_geometry_stage_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Video",
                "fileTarget": "/Users/example/private/video.mov",
                "notes": "private note",
                "stage": {"name": "Main", "regions": [{"id": "r1"}]},
                "stage/regions": [{"id": "r1"}],
                "stage/name": "Main",
                "stage/size": [1920, 1080],
                "anchor": [0.5, 0.5],
                "anchor/x": 0.5,
                "anchor/y": 0.5,
                "cueSize": [640, 360],
                "cueSize/width": 640,
                "cueSize/height": 360,
                "fillStage": True,
                "fillStyle": "scale_to_fit",
                "holdLastFrame": True,
                "layer": 5,
                "preserveAspectRatio": True,
                "quaternion": [0, 0, 0, 1],
                "smooth": True,
                "videoEffects": [{"name": "blur"}],
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["profile"], "exhaustive")
        self.assertEqual(result["properties"]["fileTarget"], "/Users/example/private/video.mov")
        self.assertEqual(result["properties"]["stage/regions"], [{"id": "r1"}])
        self.assertEqual(result["properties"]["anchor"], [0.5, 0.5])
        self.assertEqual(result["properties"]["cueSize/width"], 640)
        self.assertEqual(result["properties"]["layer"], 5)
        self.assertIn("large, sensitive", result["warnings"][0])
        self.assertEqual(result["read_coverage"]["status"], "available")
        self.assertGreater(result["read_coverage"]["status_counts"]["live_omitted"], 0)
        self.assertGreater(result["read_coverage"]["status_counts"]["indexed_read_gap"], 0)
        self.assertTrue(all("/children" not in address for address in server.received))

    def test_exhaustive_text_details_include_format_and_geometry_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Text",
                "text": "Act I",
                "text/format": {"fontFamily": "Helvetica"},
                "text/format/fontFamily": "Helvetica",
                "text/format/fontStyle": "Bold",
                "text/format/fontFamilyAndStyle": "Helvetica Bold",
                "text/format/lineSpacing": 1.2,
                "text/format/shadowBlurRadius": 3,
                "text/format/shadowOffset": [2, 4],
                "text/format/shadowOffset/width": 2,
                "text/format/shadowOffset/height": 4,
                "text/format/color": "#ffffff",
                "text/format/backgroundColor": "#000000",
                "text/format/shadowColor": "#111111",
                "text/format/strikethroughColor": "#222222",
                "text/format/underlineColor": "#333333",
                "text/outputSize": [320, 120],
                "text/outputSize/width": 320,
                "text/outputSize/height": 120,
                "cueSize": [320, 120],
                "anchor": [0.5, 0.5],
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["properties"]["text/format/fontFamily"], "Helvetica")
        self.assertEqual(result["properties"]["text/format/shadowOffset/width"], 2)
        self.assertEqual(result["properties"]["text/outputSize/height"], 120)
        self.assertEqual(result["properties"]["cueSize"], [320, 120])

    def test_exhaustive_audio_details_include_playback_maps_and_patch_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Audio",
                "audioMap": {"name": "Main Map"},
                "audioMap/filters": [{"name": "EQ"}],
                "audioMap/marks": [{"time": 1.2}],
                "audioMap/objects": [{"name": "Object 1"}],
                "audioMap/uniqueID": "map-id",
                "audioMap/size/width": 2,
                "audioMap/size/height": 2,
                "audioOutputPatch": {"name": "Main"},
                "audioOutputPatch/cueOutputChannels": [1, 2],
                "audioOutputPatch/muteChannels": [],
                "audioOutputPatch/routing": [{"in": 1, "out": 1}],
                "levels": [[0, 0]],
                "muteChannels": [2],
                "muteObjects": ["Object 1"],
                "numChannelsIn": 2,
                "objectLevels": {"Object 1": 0},
                "objects": [{"name": "Object 1"}],
                "sliderLevels": [0, 0],
                "sliceMarkers": [{"time": 0}],
                "soloChannels": [1],
                "soloObjects": ["Object 1"],
                "rate": 1.25,
                "startTime": 0.5,
                "endTime": 12,
                "playCount": 3,
                "infiniteLoop": False,
                "preservePitch": True,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["properties"]["audioMap/objects"], [{"name": "Object 1"}])
        self.assertEqual(result["properties"]["audioOutputPatch/routing"], [{"in": 1, "out": 1}])
        self.assertEqual(result["properties"]["levels"], [[0, 0]])
        self.assertEqual(result["properties"]["sliceMarkers"], [{"time": 0}])
        self.assertEqual(result["properties"]["rate"], 1.25)

    def test_exhaustive_light_details_include_documented_command_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Light",
                "lightCommandText": "1 thru 5 @ 80",
                "alwaysCollate": True,
                "subcontroller": False,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["properties"]["lightCommandText"], "1 thru 5 @ 80")
        self.assertTrue(result["properties"]["alwaysCollate"])
        self.assertFalse(result["properties"]["subcontroller"])

    def test_exhaustive_script_details_can_return_script_fields(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Script",
                "scriptSource": "display dialog \"secret\"",
                "scriptText": "display dialog \"secret\"",
                "notes": "operator note",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["properties"]["scriptSource"], "display dialog \"secret\"")
        self.assertEqual(result["properties"]["scriptText"], "display dialog \"secret\"")
        self.assertEqual(result["properties"]["notes"], "operator note")
        self.assertIn("scripts", result["warnings"][0])

    def test_exhaustive_group_details_do_not_expand_children(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "type": "Group",
                "mode": 3,
                "playbackPositionID": "child-id",
                "playlist/doLoop": True,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "exhaustive")

        self.assertEqual(result["properties"]["mode"], 3)
        self.assertEqual(result["properties"]["playbackPositionID"], "child-id")
        self.assertTrue(all("/children" not in address for address in server.received))

    def test_cart_details_do_not_expand_children(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cart-id",
                "type": "Cart",
                "name": "Cue Cart",
                "mode": 5,
                "cartRows": 4,
                "cartColumns": 4,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "inspector_safe")

        self.assertEqual(result["cue_type"], "Cart")
        self.assertEqual(result["properties"]["mode"], 5)
        self.assertEqual(result["properties"]["cartRows"], 4)
        self.assertTrue(all("/children" not in address for address in server.received))

    def test_batch_exhaustive_emits_size_and_sensitivity_warning(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {"uniqueID": "cue-10", "type": "Audio"},
            "/workspace/ws-1/cue/11/valuesForKeys": {"uniqueID": "cue-11", "type": "Video"},
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", ["10", "11"], "exhaustive")

        self.assertTrue(result["ok"])
        self.assertEqual(result["succeeded_count"], 2)
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(any("large, sensitive" in warning for warning in result["warnings"]))
        self.assertTrue(any("Batch exhaustive" in warning for warning in result["warnings"]))
        self.assertTrue(all(item["warnings"] for item in result["results"]))
        self.assertEqual(result["read_coverage"]["status"], "available")
        self.assertTrue(all("read_coverage" not in item for item in result["results"]))

    def test_editable_profile_returns_update_capabilities_for_audio(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "Intro",
                "displayName": "10 Intro",
                "type": "Audio",
                "flagged": False,
                "colorName": "none",
                "hasFileTargets": True,
                "fileTarget": "/Users/example/private/audio.wav",
                "rate": 1.0,
                "startTime": 0,
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "editable")

        self.assertEqual(result["profile"], "editable")
        self.assertEqual(result["cue_type"], "Audio")
        self.assertNotIn("fileTarget", result["properties"])
        capabilities = result["update_capabilities"]
        self.assertEqual(capabilities["compatible_profiles"], ["common", "audio_basic"])
        self.assertEqual(capabilities["recommended_profile"], "audio_basic")
        for prop in ("name", "flagged", "colorName", "rate", "startTime"):
            self.assertIn(prop, capabilities["real_write_properties"])
        for prop in (
            "fileTarget",
            "level",
            "sliderLevel",
            "deleteSliceMarker",
            "deleteSliceMarkers",
            "objectIDLevel",
            "audioOutputPatch/level",
            "audioOutputPatch/routing/reset",
            "audioMap/objectID/position",
            "audioOutputPatchID",
        ):
            self.assertIn(prop, capabilities["dry_run_only_properties"])
            self.assertNotIn(prop, capabilities["real_write_properties"])
        self.assertEqual(
            capabilities["property_details"]["dry_run_only"]["level"]["planned_only_reason"],
            "audio_levels_can_affect_live_output",
        )
        self.assertEqual(
            capabilities["operations"]["level"]["args"],
            [
                {"name": "inChannel", "validator": "audio_level_row"},
                {"name": "outChannel", "validator": "audio_output_ref"},
                {"name": "decibel", "validator": "decibel"},
            ],
        )
        self.assertFalse(capabilities["operations"]["level"]["real_write_enabled"])
        self.assertEqual(capabilities["validators"]["level"]["decibel"], "decibel")
        self.assertEqual(capabilities["validators"]["sliderLevel"]["channel"], "audio_output_ref")
        self.assertEqual(capabilities["validators"]["objectIDLevel"]["row"], "audio_level_row")
        self.assertEqual(capabilities["validators"]["audioOutputPatch/level"]["outChannel"], "device_output_ref")
        self.assertIn("operations", capabilities["arg_schema"])
        self.assertEqual(
            capabilities["requires_write_gates"],
            ["QLAB_ENABLE_WRITE", "QLAB_PASSCODE", "edit_scope_via_connect", "edit_mode_via_showMode"],
        )

    def test_editable_profile_matches_specific_profiles_by_cue_type(self) -> None:
        cases = (
            ("Memo", "memo_basic", ()),
            ("Text", "text_basic", ("text/format/color",)),
            ("Network", "network_basic", ("customString", "parameterValue", "parameterValues")),
            ("Light", "light_basic", ("lightCommandText", "setLight", "alwaysCollate")),
            ("Timecode", "timecode_basic", ("timecodeString", "timecodeFormat")),
            ("Script", "script_basic", ("scriptSource", "scriptText")),
        )
        for cue_type, expected_profile, dry_run_props in cases:
            with self.subTest(cue_type=cue_type):
                responses = {
                    "/workspace/ws-1/cue/10/valuesForKeys": {
                        "uniqueID": "cue-id",
                        "number": "10",
                        "name": cue_type,
                        "displayName": cue_type,
                        "type": cue_type,
                    },
                }
                with FakeQlabOscServer(responses) as server:
                    reader = QLabReader(client_for(server))

                    result = reader.get_cue_details("ws-1", "10", "editable")

                capabilities = result["update_capabilities"]
                self.assertIn("common", capabilities["compatible_profiles"])
                self.assertIn(expected_profile, capabilities["compatible_profiles"])
                self.assertEqual(capabilities["recommended_profile"], expected_profile)
                for profile in capabilities["compatible_profiles"]:
                    self.assertTrue(profile == "common" or profile == expected_profile)
                for prop in dry_run_props:
                    self.assertIn(prop, capabilities["dry_run_only_properties"])
                    self.assertNotIn(prop, capabilities["real_write_properties"])

    def test_editable_profile_exposes_documented_light_update_capabilities(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "LX",
                "displayName": "LX",
                "type": "Light",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "editable")

        capabilities = result["update_capabilities"]
        self.assertEqual(capabilities["recommended_profile"], "light_basic")
        for prop in (
            "alwaysCollate",
            "collateAndStart",
            "lightCommandText",
            "prune",
            "pruneCommands",
            "removeLightCommandsMatching",
            "replaceLightCommand",
            "safeSort",
            "safeSortCommands",
            "setLight",
            "subcontroller",
        ):
            self.assertIn(prop, capabilities["dry_run_only_properties"])
            self.assertNotIn(prop, capabilities["real_write_properties"])
            self.assertIn(prop, capabilities["planned_only_reason"])
        self.assertEqual(capabilities["validators"]["alwaysCollate"]["value"], "boolean")
        self.assertEqual(capabilities["validators"]["subcontroller"]["value"], "boolean")
        self.assertEqual(capabilities["validators"]["setLight"]["instrument_or_group"], "non_empty_string")
        self.assertEqual(capabilities["validators"]["setLight"]["setting"], "json_value")
        self.assertEqual(capabilities["validators"]["replaceLightCommand"]["oldCommand"], "non_empty_string")
        self.assertEqual(capabilities["validators"]["replaceLightCommand"]["newCommand"], "non_empty_string")
        self.assertNotIn("parameterValues", capabilities["operations"])
        self.assertNotIn("removeLightCommand", capabilities["operations"])
        self.assertNotIn("dashboard/setLight", capabilities["operations"])

    def test_editable_profile_exposes_group_list_cart_update_capabilities(self) -> None:
        cases = ("Group", "Cue List", "Cue Cart")
        for cue_type in cases:
            with self.subTest(cue_type=cue_type):
                responses = {
                    "/workspace/ws-1/cue/10/valuesForKeys": {
                        "uniqueID": "cue-id",
                        "number": "10",
                        "name": cue_type,
                        "displayName": cue_type,
                        "type": cue_type,
                    },
                }
                with FakeQlabOscServer(responses) as server:
                    reader = QLabReader(client_for(server))

                    result = reader.get_cue_details("ws-1", "10", "editable")

                capabilities = result["update_capabilities"]
                self.assertEqual(capabilities["recommended_profile"], "group_basic")
                self.assertIn("group_basic", capabilities["compatible_profiles"])
                self.assertIn("mode", capabilities["real_write_properties"])
                self.assertEqual(capabilities["validators"]["mode"]["value"], "group_mode")
                for prop in (
                    "playhead",
                    "playbackPositionID",
                    "playhead/next",
                    "playbackPosition/previousSequence",
                    "moveCartCue",
                    "playlist/currentCueID",
                    "playlistLoop",
                    "playlistCrossfadeDuration",
                ):
                    self.assertIn(prop, capabilities["dry_run_only_properties"])
                    self.assertNotIn(prop, capabilities["real_write_properties"])
                    self.assertIn(prop, capabilities["operations"])
                    self.assertIn(prop, capabilities["planned_only_reason"])
                self.assertEqual(capabilities["validators"]["moveCartCue"]["row"], "non_negative_int")
                self.assertEqual(capabilities["validators"]["playlist/currentCueID"]["value"], "non_empty_string")
                self.assertNotIn("cartRows", capabilities["operations"])
                self.assertNotIn("go", capabilities["operations"])

    def test_editable_profile_exposes_documented_timecode_update_capabilities(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "TC",
                "displayName": "TC",
                "type": "Timecode",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "editable")

        capabilities = result["update_capabilities"]
        self.assertEqual(capabilities["recommended_profile"], "timecode_basic")
        for prop in ("outputType", "timecodeFrameRate", "startTime", "endTime"):
            self.assertIn(prop, capabilities["real_write_properties"])
        self.assertEqual(capabilities["operations"]["timecodeFrameRate"]["path"], "framerate")
        self.assertEqual(capabilities["validators"]["timecodeFrameRate"]["value"], "timecode_framerate")
        self.assertIn("timecodeString", capabilities["dry_run_only_properties"])
        self.assertIn("timecodeFormat", capabilities["dry_run_only_properties"])

    def test_auto_timecode_profile_excludes_midi_msc_timecode_aliases(self) -> None:
        responses = {
            "/workspace/ws-1/cue/10/valuesForKeys": {
                "uniqueID": "cue-id",
                "number": "10",
                "name": "TC",
                "displayName": "TC",
                "type": "Timecode",
                "timecodeString": "01:00:00:00",
                "timecodeFormat": 3,
                "outputType": 1,
                "framerate": 7,
                "startTime": "01:00:00:00",
                "endTime": "01:00:10:00",
                "ltcChannel": 1,
                "midiPatchName": "Patch 1",
                "audioOutputPatchName": "Main",
            },
        }
        with FakeQlabOscServer(responses) as server:
            reader = QLabReader(client_for(server))

            result = reader.get_cue_details("ws-1", "10", "auto")

        type_specific = result["sections"]["type_specific"]
        self.assertNotIn("timecodeString", type_specific)
        self.assertNotIn("timecodeFormat", type_specific)
        self.assertEqual(type_specific["outputType"], 1)
        self.assertEqual(type_specific["framerate"], 7)
        self.assertEqual(type_specific["startTime"], "01:00:00:00")
        self.assertEqual(type_specific["endTime"], "01:00:10:00")
        self.assertEqual(type_specific["ltcChannel"], 1)
        self.assertEqual(type_specific["midiPatchName"], "Patch 1")
        self.assertEqual(type_specific["audioOutputPatchName"], "Main")

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
        self.assertEqual(
            validate_value_keys(
                [
                    "opacity",
                    "stageName",
                    "layer",
                    "fillStage",
                    "text/format/shadowOffset",
                    "text/format/shadowBlurRadius",
                ]
            ),
            ["opacity", "stageName", "layer", "fillStage", "text/format/shadowOffset", "text/format/shadowBlurRadius"],
        )
        for unsafe in (["start"], ["panic"], ["../name"], ["unknownThing"], []):
            with self.assertRaises(UnsafeCuePropertyError):
                validate_value_keys(unsafe)


if __name__ == "__main__":
    unittest.main()

