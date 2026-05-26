"""Workspace overview and compact cue-index orchestration."""

from __future__ import annotations

from typing import Any

from ..allowlist import validate_value_keys
from ..osc.addressing import _clean_workspace_id, _normalize_id_list, _workspace_address
from .editorial import editorial_health_from_index
from .index import (
    _cue_index_row,
    cue_index_columns,
    cue_index_value_keys,
    normalize_cue_index_profile,
)
from .profiles import _derive_profile_fields
from .refs import _flatten_cue_refs
from ..runtime.connection import QLAB_VERSION_KEYS, read_workspace_mode


CONTAINER_CUE_TYPES = {"Cue List", "Cue Cart", "Group"}
OVERVIEW_CUE_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
    "colorName/live",
    "isBroken",
    "isWarning",
    "continueMode",
)

def _workspace_overview_metadata(workspace: Any) -> dict[str, Any]:
    if not isinstance(workspace, dict):
        return {"value": workspace}

    name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
    qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)

    return {
        "uniqueID": workspace.get("uniqueID"),
        "name": name,
        "displayName": workspace.get("displayName"),
        "qlab_version": qlab_version,
        "metadata": dict(workspace),
    }


def _known_child_count(cue: Any) -> int | None:
    if not isinstance(cue, dict):
        return None
    children = cue.get("cues")
    if isinstance(children, list):
        return len(children)
    return None


def _cue_overview_node(cue: Any) -> dict[str, Any]:
    if not isinstance(cue, dict):
        return {"value": cue, "child_count": 0, "children": []}
    node = {key: cue[key] for key in OVERVIEW_CUE_KEYS if key in cue}
    node = _derive_profile_fields("overview", node)
    label = node.get("displayName") or node.get("name") or node.get("listName") or node.get("number") or node.get("uniqueID")
    if label is not None:
        node["label"] = str(label)
    node["child_count"] = _known_child_count(cue)
    node["children"] = []
    return node


def _is_container_cue(cue: dict[str, Any]) -> bool:
    return cue.get("type") in CONTAINER_CUE_TYPES


def _count_stat(stats: dict[str, Any], bucket: str, key: Any) -> None:
    normalized = "unknown" if key in (None, "") else str(key)
    stats[bucket][normalized] = stats[bucket].get(normalized, 0) + 1


def _record_cue_stats(stats: dict[str, Any], cue: dict[str, Any]) -> None:
    _count_stat(stats, "types", cue.get("type"))
    _count_stat(stats, "colors", cue.get("colorName"))
    if cue.get("armed") is True:
        stats["armed"] += 1
    elif cue.get("armed") is False:
        stats["disarmed"] += 1
    if cue.get("flagged") is True:
        stats["flagged"] += 1


class CueOverviewMixin:
    def get_workspace_overview(
        self,
        workspace_id: str | None = None,
        max_depth: int = 2,
        max_cues: int = 1000,
        include_live_state: bool = False,
        include_cue_index: bool = True,
        max_index_cues: int = 1000,
        cue_index_profile: str = "minimal",
        include_selected_and_running: bool | None = None,
    ) -> dict[str, Any]:
        if include_selected_and_running is not None:
            include_live_state = include_selected_and_running
        if max_depth < 0:
            raise ValueError("max_depth must be 0 or greater")
        if max_cues < 1:
            raise ValueError("max_cues must be 1 or greater")
        if max_index_cues < 1:
            raise ValueError("max_index_cues must be 1 or greater")
        if max_index_cues > 5000:
            raise ValueError("max_index_cues must be 5000 or lower")
        normalized_cue_index_profile = normalize_cue_index_profile(cue_index_profile)

        workspaces_result = self.get_workspaces()
        workspaces = workspaces_result.get("workspaces") or []
        workspace = self._resolve_workspace(workspaces, workspace_id)
        resolved_workspace_id = _clean_workspace_id(workspace.get("uniqueID") or workspace_id or "")
        workspace_mode = read_workspace_mode(self.client, resolved_workspace_id, authenticated=True)

        cue_lists = self.get_cue_lists(resolved_workspace_id, include_children=False)["cue_lists"] or []
        cue_id_data = self._request_data(
            _workspace_address(resolved_workspace_id, "cueLists/uniqueIDs"),
            workspace_id=resolved_workspace_id,
        )
        cue_ids = _normalize_id_list(cue_id_data)
        cue_refs = _flatten_cue_refs(cue_id_data)

        summary: dict[str, Any] = {
            "total_cue_ids": len(cue_ids),
            "inspected_cues": 0,
            "cue_lists": len(cue_lists),
            "types": {},
            "colors": {},
            "armed": 0,
            "disarmed": 0,
            "flagged": 0,
            "max_depth_returned": 0,
        }
        limits: dict[str, Any] = {
            "max_depth": max_depth,
            "max_cues": max_cues,
            "truncated": False,
            "truncation_reasons": [],
        }
        errors: dict[str, str] = {}

        def mark_truncated(reason: str) -> None:
            limits["truncated"] = True
            if reason not in limits["truncation_reasons"]:
                limits["truncation_reasons"].append(reason)

        def build_node(cue: Any, depth: int) -> dict[str, Any] | None:
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                return None

            node = _cue_overview_node(cue)
            node["depth"] = depth
            summary["inspected_cues"] += 1
            summary["max_depth_returned"] = max(summary["max_depth_returned"], depth)
            _record_cue_stats(summary, node)

            cue_id = node.get("uniqueID")
            if not cue_id:
                node["child_count"] = node["child_count"] or 0
                return node
            if not _is_container_cue(node):
                node["child_count"] = node["child_count"] or 0
                return node
            if depth >= max_depth:
                node["children_truncated"] = True
                mark_truncated("max_depth")
                return node

            try:
                children = self.get_cue_children(
                    resolved_workspace_id,
                    str(cue_id),
                    shallow=True,
                    ids_only=False,
                )["children"]
            except Exception as exc:
                errors[str(cue_id)] = str(exc)
                return node

            if not isinstance(children, list):
                node["child_count"] = 0
                return node

            node["child_count"] = len(children)
            child_nodes: list[dict[str, Any]] = []
            for child in children:
                child_node = build_node(child, depth + 1)
                if child_node is not None:
                    child_nodes.append(child_node)
                if summary["inspected_cues"] >= max_cues:
                    mark_truncated("max_cues")
                    break
            node["children"] = child_nodes
            if len(child_nodes) < len(children):
                node["children_truncated"] = True
            return node

        overview_cue_lists: list[dict[str, Any]] = []
        for cue_list in cue_lists:
            node = build_node(cue_list, 0)
            if node is not None:
                overview_cue_lists.append(node)
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                break

        live_state = None
        if include_live_state:
            live_state = {
                "selected_cues": self.get_selected_cues(
                    resolved_workspace_id,
                    include_children=False,
                )["selected_cues"],
                "running_cues": self.get_running_cues(
                    resolved_workspace_id,
                    include_paused=True,
                    include_children=False,
                )["running_cues"],
                "running_includes_paused": True,
            }

        warnings: list[str] = []
        if limits["truncated"]:
            reasons = ", ".join(limits["truncation_reasons"])
            if include_cue_index:
                warnings.append(
                    "Tree preview is partial"
                    + (f" ({reasons})" if reasons else "")
                    + "; cue_index may still contain the compact workspace map up to max_index_cues."
                )
            else:
                warnings.append(
                    "Tree preview is partial"
                    + (f" ({reasons})" if reasons else "")
                    + "; increase max_depth or max_cues for a deeper tree scan."
                )

        workspace_metadata = _workspace_overview_metadata(workspace)
        workspace_metadata.update(
            {
                "mode": workspace_mode.get("mode"),
                "show_mode": workspace_mode.get("show_mode"),
                "mode_check": workspace_mode,
            }
        )
        result = {
            "workspace_id": resolved_workspace_id,
            "workspace": workspace_metadata,
            "cue_count": len(cue_ids),
            "summary": summary,
            "cue_lists": overview_cue_lists,
            "limits": limits,
            "warnings": warnings,
            "errors": errors or None,
        }
        if live_state is not None:
            result["live_state"] = live_state
        if include_cue_index:
            index_errors: dict[str, str] = {}
            index_rows: list[list[Any]] = []
            index_keys = validate_value_keys(cue_index_value_keys(normalized_cue_index_profile))
            for cue_ref in cue_refs[:max_index_cues]:
                cue_id = cue_ref.get("uniqueID")
                if not cue_id:
                    continue
                try:
                    values = self.read_cue_values(
                        resolved_workspace_id,
                        str(cue_id),
                        index_keys,
                        cache_profile=normalized_cue_index_profile,
                    )["values"]
                    if not isinstance(values, dict):
                        raise ValueError("QLab valuesForKeys response must be an object")
                except Exception as exc:
                    index_errors[str(cue_id)] = str(exc)
                    continue
                index_rows.append(_cue_index_row(cue_ref, values, normalized_cue_index_profile))

            result["cue_index"] = {
                "profile": normalized_cue_index_profile,
                "columns": list(cue_index_columns(normalized_cue_index_profile)),
                "rows": index_rows,
                "total_cue_ids": len(cue_refs),
                "indexed_count": len(index_rows),
                "truncated": len(cue_refs) > max_index_cues,
                "max_index_cues": max_index_cues,
                "errors": index_errors or None,
            }
            result["editorial_health"] = editorial_health_from_index(
                result["cue_index"]["columns"],
                index_rows,
            )
        return result
