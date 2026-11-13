"""Read-only, source-separated views of live and saved QLab audio patches."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Literal
from uuid import UUID

from .audio_archive import read_saved_audio_patches
from .sanitizer import sanitize_exception_message

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PATCH_PAGE = 128
MAX_MATRIX_PAGE = 256
MAX_DEVICE_OBSERVATIONS = 64


def _canonical_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value))).upper()
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"{field} must be an exact UUID.") from None


def _channel(value: int, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 128:
        raise ValueError(f"{field} must be an integer from 0 to 128.")
    return value


def _source_status(source: dict[str, Any]) -> str:
    if source.get("status") not in {"available", "partial"}:
        return "unavailable"
    return str(source.get("status"))


def _device_observations(value: Any) -> dict[str, Any]:
    """Keep passive CoreAudio inventory separate and bounded in audio reads."""
    if not isinstance(value, dict):
        value = {"source": "macos_coreaudio", "status": "unavailable"}
    result = {
        "source": value.get("source") if isinstance(value.get("source"), str) else "macos_coreaudio",
        "status": value.get("status") if isinstance(value.get("status"), str) else "unavailable",
        "scope": "Passive CoreAudio inventory only; signal and playback are not verified.",
    }
    for key in ("output_status", "observed_at", "identity_scope"):
        item = value.get(key)
        if isinstance(item, str):
            result[key] = item[:256]
    if type(value.get("capture_started")) is bool:
        result["capture_started"] = value["capture_started"]
    for key in ("default_input_id", "default_output_id"):
        item = value.get(key)
        if type(item) is int or isinstance(item, str):
            result[key] = item if type(item) is int else item[:256]

    raw_devices = value.get("devices")
    if not isinstance(raw_devices, list):
        result.update(devices=[], device_count=None, returned_devices=0, devices_truncated=False)
        return result

    devices = []
    for row in raw_devices[:MAX_DEVICE_OBSERVATIONS]:
        if not isinstance(row, dict):
            continue
        device = {}
        for key in ("id", "uid", "name", "manufacturer", "model_uid"):
            item = row.get(key)
            if type(item) is int:
                device[key] = item
            elif isinstance(item, str):
                if key == "uid":
                    if len(item) <= 512:
                        device[key] = item
                    else:
                        device["uid_over_limit"] = True
                else:
                    device[key] = item[:256]
        for key in ("input_channels", "output_channels"):
            item = row.get(key)
            if type(item) is int:
                device[key] = item
        errors = row.get("metadata_errors")
        if isinstance(errors, list):
            device["metadata_errors"] = [item[:256] for item in errors[:8] if isinstance(item, str)]
        devices.append(device)
    result.update(
        devices=devices,
        device_count=len(raw_devices),
        returned_devices=len(devices),
        devices_truncated=len(raw_devices) > MAX_DEVICE_OBSERVATIONS,
    )
    return result


def _overall(sources: dict[str, dict[str, Any]]) -> tuple[bool, str, bool]:
    statuses = [_source_status(source) for source in sources.values()]
    ok = any(status in {"available", "partial"} for status in statuses)
    partial = not all(status == "available" for status in statuses)
    return ok, "ready" if ok and not partial else "partial" if ok else "error", partial


def _saved_source(reader, workspace_id: str, patch_type: str, patch_id: str) -> dict[str, Any]:
    try:
        read = read_saved_audio_patches(reader, workspace_id, patch_type=patch_type, ref=patch_id)
    except Exception as exc:
        return {
            "source": "saved_archive", "status": "unavailable", "freshness": "unavailable",
            "document_modified": None, "data": None,
            "device_observations": _device_observations(None),
            "issues": [sanitize_exception_message(exc)],
        }

    saved = read.get("saved") if isinstance(read.get("saved"), dict) else {}
    key = "output_patches" if patch_type == "output" else "input_patches"
    patches = saved.get(key) if isinstance(saved.get(key), list) else []
    matches = [patch for patch in patches if isinstance(patch, dict)
               and str(patch.get("id", "")).casefold() == patch_id.casefold()]
    data = matches[0] if len(matches) == 1 else None
    status = read.get("status")
    source_status = "available" if status == "ready" and data is not None else (
        "partial" if status in {"ready", "partial"} or data is not None else "unavailable"
    )
    issues = list(read.get("issues") or [])
    if status in {"ready", "partial"} and data is None:
        issues.append("The exact saved audio patch was not returned.")
    return {
        "source": "saved_archive", "status": source_status,
        "freshness": read.get("freshness", "unavailable"),
        "document_modified": read.get("document_modified"), "sha256": read.get("sha256"),
        "device_observations": _device_observations(read.get("device_observations")),
        "data": deepcopy(data), "issues": issues,
    }


def _live_patch(reader, workspace_id: str, patch_type: str, patch_id: str, profile: str,
                input_channel: int | None, output_channel: int | None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "workspace_id": workspace_id, "section": "audio",
        "kind": f"{patch_type}_patch", "ref": patch_id, "profile": profile,
    }
    if input_channel is not None:
        options.update(input_channel=input_channel, output_channel=output_channel)
    try:
        result = reader.get_workspace_setting_details(**options)
    except Exception as exc:
        return {
            "source": "live_osc", "status": "unavailable", "data": None,
            "errors": [sanitize_exception_message(exc)], "warnings": [],
        }

    if not isinstance(result, dict):
        return {"source": "live_osc", "status": "unavailable", "data": None,
                "errors": ["QLab returned an invalid Audio Patch response."], "warnings": []}
    details = result.get("details")
    returned_id = None
    if isinstance(details, dict):
        returned_id = details.get("uniqueID", details.get("id", details.get("patchID")))
    errors = result.get("errors")
    if not result.get("ok", True) or not isinstance(details, dict):
        details = None
        status = "unavailable"
    elif returned_id is None or str(returned_id).casefold() != patch_id.casefold():
        details = None
        errors = {**(errors if isinstance(errors, dict) else {}), "audio.patch": "Exact patch identity was not confirmed."}
        status = "unavailable"
    elif result.get("partial") or errors:
        status = "partial"
    else:
        status = "available"
    return {
        "source": "live_osc", "status": status, "data": deepcopy(details),
        "errors": deepcopy(errors) if errors else [],
        "warnings": deepcopy(result.get("warnings") or []),
        "redactions": deepcopy(result.get("redactions") or []),
    }


def _archive_cell(matrix: Any, row: int, column: int) -> dict[str, Any]:
    if not isinstance(matrix, dict) or matrix.get("status") not in {"available", "partial"}:
        return {"status": "unavailable", "data": None}
    cells = matrix.get("cells")
    if not isinstance(cells, list):
        return {"status": "unavailable", "data": None}
    for cell in cells:
        if isinstance(cell, dict) and cell.get("row") == row and cell.get("column") == column:
            return {"status": "available", "data": deepcopy(cell)}
    # Missing cells are not converted into an assumed zero level.
    incomplete = matrix.get("truncated") is True or matrix.get("status") == "partial"
    return {"status": "not_observed_in_incomplete_matrix" if incomplete else "not_observed", "data": None}


def _compare_patch_names(live: Any, saved: Any) -> dict[str, Any]:
    differences = []
    compared = []
    if isinstance(live, dict) and isinstance(saved, dict):
        saved_name = saved.get("name")
        # Exact patch detail exposes the persisted name separately. Inventory
        # `name` may be QLab's decorated display string, so only compare it
        # when it exactly equals the archived name.
        live_name = live.get("name_property")
        if live_name is None and live.get("name") == saved_name:
            live_name = live.get("name")
        if isinstance(live_name, str) and isinstance(saved_name, str):
            compared.append("name")
            if live_name != saved_name:
                differences.append({"field": "name", "live_osc": live_name, "saved_archive": saved_name})
    return {
        "status": "differs" if differences else "matches_observed_fields" if compared else "not_comparable",
        "compared_fields": compared,
        "differences": differences,
        "scope": ["persisted patch name when independently observable"],
        "atomic_snapshot": False,
    }


def _compare_inventories(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    live_data = sources.get("live_osc", {}).get("data")
    saved_data = sources.get("saved_archive", {}).get("data")
    differences = []
    compared = 0
    if isinstance(live_data, dict) and isinstance(saved_data, dict):
        for key in ("output_patches", "input_patches"):
            live_items = live_data.get(key)
            saved_items = saved_data.get(key)
            if not isinstance(live_items, list) or not isinstance(saved_items, list):
                continue
            saved_by_id = {str(item.get("id", "")).casefold(): item for item in saved_items
                           if isinstance(item, dict) and item.get("id")}
            for live in live_items:
                if not isinstance(live, dict):
                    continue
                live_id = live.get("uniqueID", live.get("id", live.get("patchID")))
                saved = saved_by_id.get(str(live_id).casefold()) if live_id else None
                if saved is None:
                    continue
                comparison = _compare_patch_names(live, saved)
                compared += len(comparison["compared_fields"])
                for difference in comparison["differences"]:
                    differences.append({"patch_id": str(live_id), **difference})
    return {
        "status": "differs" if differences else "matches_observed_fields" if compared else "not_comparable",
        "compared_fields": ["patch name"] if compared else [],
        "differences": differences,
        "scope": ["patch name for exact IDs present in both paged sources"],
        "atomic_snapshot": False,
    }


def _paged_matrix(patch: dict[str, Any] | None, offset: int, limit: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    empty_page = {
        "offset": offset, "limit": limit, "total_cells": None, "returned_cells": 0,
        "observed_total_cells": None, "truncated": False, "source_truncated": False,
        "next_offset": None,
    }
    if not isinstance(patch, dict):
        return None, empty_page
    result = deepcopy(patch)
    matrix = result.get("routing_matrix")
    if not isinstance(matrix, dict) or not isinstance(matrix.get("cells"), list):
        return result, empty_page
    all_cells = matrix["cells"]
    total = matrix.get("total_cells")
    page = all_cells[offset:offset + limit]
    has_observed_more = offset + len(page) < len(all_cells)
    source_truncated = matrix.get("truncated") is True
    source_incomplete = source_truncated or matrix.get("status") == "partial"
    truncated = has_observed_more or source_incomplete
    result["routing_matrix"]["cells"] = page
    return result, {
        "offset": offset, "limit": limit, "total_cells": total,
        "observed_total_cells": len(all_cells), "returned_cells": len(page),
        "truncated": truncated, "source_truncated": source_truncated,
        "source_incomplete": source_incomplete,
        "next_offset": offset + len(page) if has_observed_more else None,
    }


def read_audio_patch(
    reader,
    workspace_id: str,
    patch_type: Literal["input", "output"],
    patch_id: str,
    *,
    profile: Literal["safe", "technical", "exhaustive"] = "safe",
    input_channel: int | None = None,
    output_channel: int | None = None,
    cell_offset: int = 0,
    cell_limit: int = 128,
) -> dict[str, Any]:
    """Read one exact input/output patch from OSC and the last-saved archive."""
    workspace_id = _canonical_uuid(workspace_id, "workspace_id")
    patch_id = _canonical_uuid(patch_id, "patch_id")
    if patch_type not in {"input", "output"}:
        raise ValueError("patch_type must be 'input' or 'output'.")
    if profile not in {"safe", "technical", "exhaustive"}:
        raise ValueError("profile must be safe, technical or exhaustive.")
    if (input_channel is None) != (output_channel is None):
        raise ValueError("input_channel and output_channel must be provided together.")
    if input_channel is not None:
        if patch_type != "output":
            raise ValueError("Channel selectors require an output patch.")
        input_channel = _channel(input_channel, "input_channel")
        output_channel = _channel(output_channel, "output_channel")
    if type(cell_offset) is not int or cell_offset < 0:
        raise ValueError("cell_offset must be a non-negative integer.")
    if type(cell_limit) is not int or not 1 <= cell_limit <= MAX_MATRIX_PAGE:
        raise ValueError(f"cell_limit must be from 1 to {MAX_MATRIX_PAGE}.")

    live = _live_patch(reader, workspace_id, patch_type, patch_id, profile, input_channel, output_channel)
    saved = _saved_source(reader, workspace_id, patch_type, patch_id)
    comparison = _compare_patch_names(live.get("data"), saved.get("data"))
    archive_cell = None
    if input_channel is not None:
        raw_saved = saved.get("data")
        raw_matrix = raw_saved.get("routing_matrix") if isinstance(raw_saved, dict) else None
        archive_cell = _archive_cell(raw_matrix, input_channel, output_channel)
    saved_data, cell_page = _paged_matrix(saved.get("data"), cell_offset, cell_limit)
    saved["data"] = saved_data
    device_observations = saved.pop("device_observations")
    sources = {"live_osc": live, "saved_archive": saved}
    ok, status, partial = _overall(sources)
    cell = None
    if input_channel is not None:
        live_level = live.get("data", {}).get("level") if isinstance(live.get("data"), dict) else None
        if (isinstance(live_level, dict) and live_level.get("input_channel") == input_channel
                and live_level.get("output_channel") == output_channel):
            live_cell = {"status": "available", "data": deepcopy(live_level)}
        else:
            live_cell = {"status": "not_observed" if live["status"] == "available" else "unavailable", "data": None}
        cell = {
            "input_channel": input_channel, "output_channel": output_channel,
            "live_osc": live_cell,
            "saved_archive": archive_cell,
        }
    result = {
        "ok": ok, "status": status, "partial": partial, "workspace_id": workspace_id,
        "patch_type": patch_type, "patch_id": patch_id,
        "sources": sources,
        "device_observations": device_observations,
        "cell": cell,
        "comparison": comparison,
        "source_status": {
            "atomic_snapshot": False,
            "field_provenance": {
                "sources.live_osc.data": "live_osc",
                "sources.saved_archive.data": "saved_archive",
                "device_observations": "macos_coreaudio",
                **({"cell.live_osc": "live_osc", "cell.saved_archive": "saved_archive"} if cell else {}),
            },
        },
        "pagination": {"matrix_cells": cell_page, "byte_limit": MAX_RESPONSE_BYTES},
        "errors": {
            source_name: source.get("errors") or source.get("issues")
            for source_name, source in sources.items()
            if source.get("errors") or source.get("issues")
        },
    }
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
        # The cell result remains exact; reduce only the returned matrix page.
        live_data = result["sources"]["live_osc"].get("data")
        if isinstance(live_data, dict) and "technical_payload" in live_data:
            live_data.pop("technical_payload", None)
            result["sources"]["live_osc"]["status"] = "partial"
            result["sources"]["live_osc"].setdefault("warnings", []).append(
                "Live technical payload omitted to fit the response byte limit."
            )
        saved_data = result["sources"]["saved_archive"].get("data")
        saved_matrix = saved_data.get("routing_matrix") if isinstance(saved_data, dict) else None
        if isinstance(saved_matrix, dict):
            saved_matrix["cells"] = []
        page = result["pagination"]["matrix_cells"]
        page.update(returned_cells=0, truncated=True, byte_truncated=True, next_offset=None)
        result["partial"] = True
        result["status"] = "partial" if result["ok"] else "error"
        if len(json.dumps(result, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
            result["sources"]["live_osc"]["data"] = None
            result["sources"]["saved_archive"]["data"] = None
            result["cell"] = None
            result["pagination"]["omitted_fields"] = [
                "Patch details and cell omitted because the complete response exceeded the byte limit."
            ]
    return result


def _patch_page(values: Any, offset: int, limit: int, *, strip_matrix: bool) -> tuple[list[Any], dict[str, Any]]:
    items = values if isinstance(values, list) else []
    page = deepcopy(items[offset:offset + limit])
    if strip_matrix:
        for item in page:
            if isinstance(item, dict) and isinstance(item.get("routing_matrix"), dict):
                item["routing_matrix"]["cells"] = []
    truncated = offset + len(page) < len(items)
    if strip_matrix:
        for item in page:
            if not isinstance(item, dict):
                continue
            for key in ("cue_output_buses", "device_output_buses"):
                buses = item.pop(key, None)
                if isinstance(buses, list):
                    item[key.removesuffix("_buses") + "_bus_count"] = len(buses)
                    item["bus_details_omitted"] = True
            matrix = item.get("routing_matrix")
            if isinstance(matrix, dict):
                matrix["cells_omitted"] = bool(matrix.get("cells")) or (
                    type(matrix.get("total_cells")) is int and matrix["total_cells"] > 0
                ) or matrix.get("truncated") is True
                matrix["cells"] = []
    return page, {
        "total": len(items), "returned": len(page), "offset": offset, "limit": limit,
        "truncated": truncated, "next_offset": offset + len(page) if truncated else None,
    }


def read_audio_overview(
    reader,
    workspace_id: str,
    *,
    profile: Literal["safe", "technical", "exhaustive"] = "safe",
    offset: int = 0,
    limit: int = 25,
) -> dict[str, Any]:
    """Read bounded live and last-saved patch inventories without combining fields."""
    workspace_id = _canonical_uuid(workspace_id, "workspace_id")
    if profile not in {"safe", "technical", "exhaustive"}:
        raise ValueError("profile must be safe, technical or exhaustive.")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer.")
    if type(limit) is not int or not 1 <= limit <= MAX_PATCH_PAGE:
        raise ValueError(f"limit must be from 1 to {MAX_PATCH_PAGE}.")

    try:
        live_result = reader.get_workspace_settings(
            workspace_id=workspace_id, mode="summary", sections=["audio"], profile=profile,
        )
        live_audio = ((live_result.get("sections") or {}).get("audio")
                      if isinstance(live_result, dict) else None)
        live_status = "unavailable" if not isinstance(live_audio, dict) or live_result.get("ok") is False else (
            "partial" if live_result.get("partial") or live_result.get("errors") else "available"
        )
        live_source = {
            "source": "live_osc", "status": live_status,
            "data": deepcopy(live_audio) if live_status != "unavailable" else None,
            "errors": deepcopy(live_result.get("errors") or []) if isinstance(live_result, dict) else [],
            "warnings": deepcopy(live_result.get("warnings") or []) if isinstance(live_result, dict) else [],
        }
    except Exception as exc:
        live_result = {}
        live_source = {"source": "live_osc", "status": "unavailable", "data": None,
                       "errors": [sanitize_exception_message(exc)], "warnings": []}

    try:
        saved_result = read_saved_audio_patches(reader, workspace_id, patch_type="all")
    except Exception as exc:
        saved_result = {"status": "unavailable", "source": "saved_archive",
                        "freshness": "unavailable", "saved": {},
                        "device_observations": {"status": "not_requested", "source": "macos_coreaudio"},
                        "issues": [sanitize_exception_message(exc)]}
    device_observations = _device_observations(saved_result.get("device_observations"))
    saved_raw = saved_result.get("saved") if isinstance(saved_result.get("saved"), dict) else {}
    archive_status = "available" if saved_result.get("status") == "ready" else (
        "partial" if saved_result.get("status") == "partial" else "unavailable"
    )
    saved_source = {
        "source": "saved_archive", "status": archive_status,
        "freshness": saved_result.get("freshness", "unavailable"),
        "document_modified": saved_result.get("document_modified"),
        "sha256": saved_result.get("sha256"),
        "data": deepcopy(saved_raw) if archive_status != "unavailable" else None,
        "issues": deepcopy(saved_result.get("issues") or []),
    }
    def build_page(page_limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
        sources = deepcopy({"live_osc": live_source, "saved_archive": saved_source})
        page_counts = {}
        for source_name, source in sources.items():
            source_pages = {}
            raw = source.get("data")
            if not isinstance(raw, dict):
                page_counts[source_name] = {
                    key: {"known": False, "total": None, "returned": 0, "offset": offset,
                          "limit": page_limit, "truncated": False, "next_offset": None}
                    for key in ("output_patches", "input_patches")
                }
                continue
            for kind in ("output_patches", "input_patches"):
                values = raw.get(kind)
                if isinstance(values, list):
                    page, counts = _patch_page(values, offset, page_limit, strip_matrix=source_name == "saved_archive")
                    raw[kind] = page
                    source_pages[kind] = {"known": True, **counts}
                else:
                    if source.get("status") == "available":
                        source["status"] = "partial"
                    source_pages[kind] = {
                        "known": False, "total": None, "returned": 0, "offset": offset,
                        "limit": page_limit, "truncated": False, "next_offset": None,
                    }
            page_counts[source_name] = source_pages
        return sources, page_counts

    effective_limit = limit
    sources, page_counts = build_page(effective_limit)
    pagination: dict[str, Any] = {"offset": offset, "limit": limit, "effective_limit": effective_limit,
                                  "byte_limit": MAX_RESPONSE_BYTES, "sources": page_counts}

    ok, status, partial = _overall(sources)
    if any(page["truncated"] for source_pages in pagination["sources"].values() for page in source_pages.values()):
        partial, status = True, "partial" if ok else "error"
    result = {
        "ok": ok, "status": status, "partial": partial, "workspace_id": workspace_id,
        "sources": sources,
        "device_observations": device_observations,
        "source_status": {
            "atomic_snapshot": False,
            "field_provenance": {
                "sources.live_osc.data.output_patches": "live_osc",
                "sources.live_osc.data.input_patches": "live_osc",
                "sources.saved_archive.data.output_patches": "saved_archive",
                "sources.saved_archive.data.input_patches": "saved_archive",
                "device_observations": "macos_coreaudio",
            },
        },
        "comparison": _compare_inventories(sources),
        "pagination": pagination,
        "errors": {
            source_name: source.get("errors") or source.get("issues")
            for source_name, source in sources.items()
            if source.get("errors") or source.get("issues")
        },
    }
    while len(json.dumps(result, allow_nan=False).encode()) > MAX_RESPONSE_BYTES and effective_limit > 1:
        effective_limit = max(1, effective_limit // 2)
        sources, page_counts = build_page(effective_limit)
        pagination.update(effective_limit=effective_limit, sources=page_counts, byte_truncated=True)
        result["sources"] = sources
        result["pagination"] = pagination
        result["comparison"] = _compare_inventories(sources)
        result["ok"], result["status"], result["partial"] = _overall(sources)
        result["partial"] = True
        result["status"] = "partial" if result["ok"] else "error"
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_RESPONSE_BYTES:
        return {
            "ok": ok, "status": "partial" if ok else "error", "partial": True,
            "workspace_id": workspace_id,
            "sources": {
                name: {"source": source["source"], "status": source["status"],
                       "freshness": source.get("freshness"), "document_modified": source.get("document_modified"),
                       "data": None, "errors": source.get("errors", []), "issues": source.get("issues", [])}
                for name, source in sources.items()
            },
            "device_observations": device_observations,
            "source_status": {"atomic_snapshot": False,
                              "field_provenance": {"device_observations": "macos_coreaudio"}},
            "comparison": {"status": "not_comparable", "differences": [], "atomic_snapshot": False},
            "pagination": {**pagination, "byte_truncated": True,
                           "omitted_fields": ["audio patch page omitted; response byte limit exceeded"]},
            "errors": {},
        }
    return result
