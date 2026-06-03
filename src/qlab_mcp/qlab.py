"""QLab workspace inspection facade plus gated write-mode entry points.

This module remains the public compatibility facade. Implementation lives in
focused modules for overview, query, cue details, workspace settings, redaction,
short-lived read caching, and the disabled-by-default write-mode preface.
"""

from __future__ import annotations

import json
from typing import Any

from .errors import OscTimeoutError
from .osc.addressing import (
    _clean_cue_ref,
    _clean_workspace_id,
    _cue_address,
    _normalize_id_list,
    _workspace_address,
)
from .allowlist import validate_property_path, validate_value_keys
from .osc.client import QLabOscClient
from .runtime.connection import WorkspaceConnectionMixin
from .cues.details import CueDetailsMixin
from .cues.overview import CueOverviewMixin
from .cues.query import CueQueryMixin
from .runtime.read_cache import cache_profile_is_safe, client_cache_namespace, shared_read_cache
from .settings.workspace import WorkspaceSettingsMixin
from .write import QLabWriteMixin


class QLabReader(
    WorkspaceConnectionMixin,
    CueOverviewMixin,
    WorkspaceSettingsMixin,
    CueQueryMixin,
    CueDetailsMixin,
    QLabWriteMixin,
):
    def __init__(self, client: QLabOscClient | None = None):
        self.client = client or QLabOscClient()
        self._read_cache = shared_read_cache()

    def _cache_ttl(self) -> float:
        return float(getattr(getattr(self.client, "config", None), "cache_ttl", 10.0))

    def _request_data(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        cacheable: bool = True,
        cache_profile: str | None = None,
    ) -> Any:
        if not cacheable or not cache_profile_is_safe(cache_profile):
            return self.client.request(address, *args, workspace_id=workspace_id).data

        key = (client_cache_namespace(self.client), workspace_id, address, args)
        return self._read_cache.get_or_set(
            key,
            self._cache_ttl(),
            lambda: self.client.request(address, *args, workspace_id=workspace_id).data,
        )

    def _request_data_with_tcp_fallback(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        cacheable: bool = True,
        cache_profile: str | None = None,
    ) -> tuple[Any, str]:
        def read() -> tuple[Any, str]:
            try:
                return self.client.request(address, *args, workspace_id=workspace_id).data, "udp"
            except OscTimeoutError as udp_exc:
                request_tcp = getattr(self.client, "request_tcp", None)
                if request_tcp is None:
                    raise
                try:
                    return request_tcp(address, *args, workspace_id=workspace_id).data, "tcp_fallback"
                except Exception as tcp_exc:
                    raise OscTimeoutError(
                        f"{udp_exc}; TCP fallback also failed for large read-only reply: {tcp_exc}"
                    ) from tcp_exc

        if not cacheable or not cache_profile_is_safe(cache_profile):
            return read()

        key = (client_cache_namespace(self.client), workspace_id, address, args, "udp_tcp_timeout_fallback")
        return self._read_cache.get_or_set(key, self._cache_ttl(), read)

    def get_workspaces(self) -> dict[str, Any]:
        reply = self.client.request("/workspaces")
        return {"workspaces": reply.data, "status": reply.status}

    def _resolve_workspace(self, workspaces: Any, workspace_id: str | None) -> dict[str, Any]:
        if not isinstance(workspaces, list):
            raise ValueError("QLab workspaces response must be a list")
        if workspace_id is None:
            if len(workspaces) != 1:
                raise ValueError("workspace_id is required when QLab has zero or multiple open workspaces")
            workspace = workspaces[0]
            if not isinstance(workspace, dict):
                raise ValueError("QLab workspace entry must be an object")
            return workspace

        requested = _clean_workspace_id(workspace_id)
        for workspace in workspaces:
            if not isinstance(workspace, dict):
                continue
            if workspace.get("uniqueID") == requested or workspace.get("displayName") == requested:
                return workspace
        return {"uniqueID": requested}

    def get_cue_lists(
        self,
        workspace_id: str,
        include_children: bool = False,
        cacheable: bool = True,
        tcp_fallback_on_timeout: bool = False,
    ) -> dict[str, Any]:
        command = "cueLists" if include_children else "cueLists/shallow"
        return self._workspace_data(
            workspace_id,
            command,
            "cue_lists",
            cacheable=cacheable,
            tcp_fallback_on_timeout=tcp_fallback_on_timeout,
        )

    def get_workspace_cue_ids(
        self,
        workspace_id: str,
        include_children: bool = True,
        tcp_fallback_on_timeout: bool = False,
    ) -> dict[str, Any]:
        command = "cueLists/uniqueIDs" if include_children else "cueLists/uniqueIDs/shallow"
        address = _workspace_address(workspace_id, command)
        if tcp_fallback_on_timeout:
            data, read_transport = self._request_data_with_tcp_fallback(address, workspace_id=workspace_id)
        else:
            data = self._request_data(address, workspace_id=workspace_id)
            read_transport = "udp"
        cue_ids = _normalize_id_list(data)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "include_children": include_children,
            "cue_count": len(cue_ids),
            "cue_ids": cue_ids,
            "read_transport": read_transport,
        }

    def get_workspace_cue_inventory(
        self,
        workspace_id: str,
        include_details: bool = False,
        detail_profile: str = "basic_safe",
    ) -> dict[str, Any]:
        id_result = self.get_workspace_cue_ids(workspace_id, include_children=True)
        result: dict[str, Any] = {
            "workspace_id": id_result["workspace_id"],
            "cue_count": id_result["cue_count"],
            "cue_ids": id_result["cue_ids"],
        }
        if not include_details:
            return result

        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for cue_id in id_result["cue_ids"]:
            try:
                cues.append(self.get_cue_details(workspace_id, cue_id, detail_profile))
            except Exception as exc:
                errors[cue_id] = str(exc)
        result["detail_profile"] = detail_profile
        result["cues"] = cues
        if errors:
            result["errors"] = errors
        return result

    def get_selected_cues(self, workspace_id: str, include_children: bool = False) -> dict[str, Any]:
        command = "selectedCues" if include_children else "selectedCues/shallow"
        return self._workspace_data(workspace_id, command, "selected_cues", cacheable=False)

    def get_running_cues(
        self,
        workspace_id: str,
        include_paused: bool = True,
        include_children: bool = False,
    ) -> dict[str, Any]:
        base = "runningOrPausedCues" if include_paused else "runningCues"
        command = base if include_children else f"{base}/shallow"
        return self._workspace_data(workspace_id, command, "running_cues", cacheable=False)

    def get_cue_children(
        self,
        workspace_id: str,
        cue_ref: str,
        shallow: bool = False,
        ids_only: bool = False,
        tcp_fallback_on_timeout: bool = False,
    ) -> dict[str, Any]:
        suffix = "children"
        if ids_only:
            suffix += "/uniqueIDs"
        if shallow:
            suffix += "/shallow"
        address = _cue_address(workspace_id, cue_ref, suffix)
        if tcp_fallback_on_timeout:
            data, read_transport = self._request_data_with_tcp_fallback(address, workspace_id=workspace_id)
        else:
            data = self._request_data(address, workspace_id=workspace_id)
            read_transport = "udp"
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "children": data,
            "ids_only": ids_only,
            "shallow": shallow,
            "read_transport": read_transport,
        }

    def read_cue_property(self, workspace_id: str, cue_ref: str, property_path: str) -> dict[str, Any]:
        prop = validate_property_path(property_path)
        data = self._request_data(
            _cue_address(workspace_id, cue_ref, prop),
            workspace_id=workspace_id,
            cacheable=False,
        )
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "property": prop,
            "value": data,
        }

    def read_cue_values(
        self,
        workspace_id: str,
        cue_ref: str,
        keys: list[str],
        cache_profile: str | None = None,
        cacheable: bool = True,
    ) -> dict[str, Any]:
        normalized_keys = validate_value_keys(keys)
        data = self._request_data(
            _cue_address(workspace_id, cue_ref, "valuesForKeys"),
            json.dumps(normalized_keys),
            workspace_id=workspace_id,
            cacheable=cacheable,
            cache_profile=cache_profile,
        )
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "keys": normalized_keys,
            "values": data,
        }

    def _workspace_data(
        self,
        workspace_id: str,
        command: str,
        key: str,
        cacheable: bool = True,
        cache_profile: str | None = None,
        tcp_fallback_on_timeout: bool = False,
    ) -> dict[str, Any]:
        address = _workspace_address(workspace_id, command)
        if tcp_fallback_on_timeout:
            data, read_transport = self._request_data_with_tcp_fallback(
                address,
                workspace_id=workspace_id,
                cacheable=cacheable,
                cache_profile=cache_profile,
            )
        else:
            data = self._request_data(
                address,
                workspace_id=workspace_id,
                cacheable=cacheable,
                cache_profile=cache_profile,
            )
            read_transport = "udp"
        return {"workspace_id": _clean_workspace_id(workspace_id), key: data, "read_transport": read_transport}
