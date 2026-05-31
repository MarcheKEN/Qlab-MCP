"""Workspace overview and compact cue-index orchestration."""

from __future__ import annotations

from typing import Any

from ..allowlist import validate_value_keys
from ..osc.addressing import _clean_workspace_id
from .editorial import editorial_health_from_index
from .index import (
    _cue_index_row,
    cue_index_columns,
    cue_index_value_keys,
    normalize_cue_index_profile,
)
from .profiles import _derive_profile_fields
from .refs import _bounded_cue_refs_from_shallow
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
    if "isBroken" in cue:
        stats["health_counts"]["broken_known"] += 1
        if cue.get("isBroken") is True:
            stats["health_counts"]["broken"] += 1
    if "isWarning" in cue:
        stats["health_counts"]["warning_known"] += 1
        if cue.get("isWarning") is True:
            stats["health_counts"]["warning"] += 1


def _tree_from_bounded_refs(refs: list[dict[str, Any]], max_depth: int, truncated_reasons: list[str]) -> list[dict[str, Any]]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for ref in refs:
        cue = ref.get("cue")
        if not isinstance(cue, dict):
            continue
        node = _cue_overview_node(cue)
        node["depth"] = ref.get("depth", 0)
        cue_id = node.get("uniqueID")
        if cue_id:
            nodes_by_id[str(cue_id)] = node
        parent_id = ref.get("parent_id")
        children_by_parent.setdefault(parent_id, []).append(node)

    for ref in refs:
        cue_id = ref.get("uniqueID")
        if not cue_id:
            continue
        node = nodes_by_id.get(str(cue_id))
        if node is None:
            continue
        children = children_by_parent.get(str(cue_id), [])
        node["children"] = children
        node["child_count"] = len(children)
        if _is_container_cue(node) and ref.get("depth", 0) >= max_depth and "max_depth" in truncated_reasons:
            node["children_truncated"] = True
        if children and "max_cues" in truncated_reasons:
            node["children_truncated"] = True

    return children_by_parent.get(None, [])


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
        if max_cues > 5000:
            raise ValueError("max_cues must be 5000 or lower")
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

        tree_bounded = _bounded_cue_refs_from_shallow(
            self,
            resolved_workspace_id,
            limit=max_cues,
            max_depth=max_depth,
        )
        index_bounded = (
            _bounded_cue_refs_from_shallow(
                self,
                resolved_workspace_id,
                limit=max_index_cues,
                max_depth=None,
            )
            if include_cue_index
            else tree_bounded
        )
        cue_refs = index_bounded["refs"]
        overview_refs = tree_bounded["refs"]
        summary_refs = cue_refs if include_cue_index else overview_refs
        cue_lists = [ref.get("cue") for ref in overview_refs if ref.get("parent_id") is None]

        count_source = "bounded_shallow_traversal"
        count_truncated = bool(index_bounded["truncated"] if include_cue_index else tree_bounded["truncated"])
        count_errors = bool(index_bounded["errors"] if include_cue_index else tree_bounded["errors"])
        total_cue_ids_status = "partial" if count_truncated or count_errors else "known"
        child_read_errors = [
            *tree_bounded.get("child_read_errors", []),
            *([] if index_bounded is tree_bounded else index_bounded.get("child_read_errors", [])),
        ]

        summary: dict[str, Any] = {
            "total_cue_ids": len(summary_refs),
            "total_cue_ids_status": total_cue_ids_status,
            "total_cue_ids_source": count_source,
            "global_unique_ids_used": False,
            "inspected_cues": len(summary_refs),
            "returned_cues": len(overview_refs),
            "cue_lists": len(cue_lists),
            "types": {},
            "colors": {},
            "armed": 0,
            "disarmed": 0,
            "flagged": 0,
            "broken": None,
            "warning": None,
            "health_counts_status": "not_calculated",
            "health_counts_source": count_source,
            "health_counts": {
                "broken": 0,
                "warning": 0,
                "broken_known": 0,
                "warning_known": 0,
                "unknown_cues": len(summary_refs),
            },
            "max_depth_returned": 0,
        }
        limits: dict[str, Any] = {
            "max_depth": max_depth,
            "max_cues": max_cues,
            "truncated": bool(tree_bounded["truncated"]),
            "truncation_reasons": list(tree_bounded["truncation_reasons"]),
            "count_status": {
                "total_cue_ids": total_cue_ids_status,
                "source": count_source,
                "global_unique_ids_used": False,
                "inspected_cues": len(summary_refs),
                "returned_cues": len(overview_refs),
            },
            "child_read_errors": child_read_errors,
        }
        errors: dict[str, str] = {**tree_bounded["errors"], **index_bounded["errors"]}

        def mark_truncated(reason: str) -> None:
            limits["truncated"] = True
            if reason not in limits["truncation_reasons"]:
                limits["truncation_reasons"].append(reason)

        for ref in summary_refs:
            cue = ref.get("cue")
            if isinstance(cue, dict):
                node = _cue_overview_node(cue)
                node["depth"] = ref.get("depth", 0)
                summary["max_depth_returned"] = max(summary["max_depth_returned"], int(ref.get("depth", 0) or 0))
                _record_cue_stats(summary, node)

        health_counts = summary["health_counts"]
        health_known = (
            health_counts["broken_known"] == len(summary_refs)
            and health_counts["warning_known"] == len(summary_refs)
            and not child_read_errors
        )
        health_counts["unknown_cues"] = max(
            len(summary_refs) - min(health_counts["broken_known"], health_counts["warning_known"]),
            0,
        )
        if health_known:
            summary["broken"] = health_counts["broken"]
            summary["warning"] = health_counts["warning"]
            summary["health_counts_status"] = "known"
        else:
            summary["health_counts_status"] = "partial"

        overview_cue_lists = _tree_from_bounded_refs(overview_refs, max_depth, limits["truncation_reasons"])

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
        if child_read_errors:
            failed_refs = ", ".join(str(item.get("cue_ref")) for item in child_read_errors[:5])
            warnings.append(
                "Some container children could not be read; cue counts are partial and do not represent the full workspace. "
                f"Failed container refs: {failed_refs}."
            )
            limits["truncated"] = True
            if "child_read_error" not in limits["truncation_reasons"]:
                limits["truncation_reasons"].append("child_read_error")
        if summary["health_counts_status"] != "known":
            warnings.append(
                "Overview health counts are partial because shallow cue data did not include reliable isBroken/isWarning "
                "for every inspected cue; use qlab_query_cues with flagged_or_broken or isWarning for authoritative health counts."
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
            "cue_count": len(summary_refs),
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
                    raw_values = cue_ref.get("cue")
                    if not isinstance(raw_values, dict):
                        raise ValueError("QLab shallow cue entry must be an object")
                    values = {key: raw_values.get(key) for key in index_keys if key in raw_values}
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
                "truncated": bool(index_bounded["truncated"]),
                "max_index_cues": max_index_cues,
                "errors": index_errors or None,
            }
            result["editorial_health"] = editorial_health_from_index(
                result["cue_index"]["columns"],
                index_rows,
            )
        return result
