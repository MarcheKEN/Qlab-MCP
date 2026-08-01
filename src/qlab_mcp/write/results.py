"""Result construction for gated cue-update batches."""

from __future__ import annotations

from typing import Any


UPDATE_STATUS_ACTIONS = {
    "preflight_failed": "Inspect per-cue errors; no setters were sent, so fix cue refs/profiles before retrying.",
    "partial_failed": "Inspect per-cue errors and verify the affected cues in QLab before retrying only failed items.",
    "verification_failed": "Read the cue fresh and compare requested versus after values before retrying.",
    "verification_inconclusive": "Treat the update as unsafe; inspect executed operations and add deterministic readback before retrying.",
}
UPDATE_STATUS_CODES = {
    "preflight_failed": "QLAB_UPDATE_PREFLIGHT_FAILED",
    "partial_failed": "QLAB_UPDATE_PARTIAL_FAILED",
    "verification_failed": "QLAB_UPDATE_VERIFICATION_FAILED",
    "verification_inconclusive": "QLAB_UPDATE_VERIFICATION_INCONCLUSIVE",
}


def build_batch_update_result(
    workspace_id: str,
    *,
    dry_run: bool,
    results: list[dict[str, Any]],
    status: str,
    requested_count: int,
    timeout_confirmed_count: int = 0,
    errors: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    failed_count = sum(1 for result in results if result.get("errors"))
    updated_count = sum(
        1
        for result in results
        if result.get("status") in {"updated", "updated_with_confirmed_timeouts"}
    )
    planned_count = sum(1 for result in results if result.get("planned_operations"))
    ok = failed_count == 0 and status not in {
        "preflight_failed",
        "partial_failed",
        "verification_failed",
        "verification_inconclusive",
    }
    if status == "dry_run":
        message = "Dry run succeeded; review planned_operations before disabling dry_run."
    elif status == "preflight_failed":
        message = "Batch cue update was blocked during preflight; no mutating OSC commands were sent."
    elif status == "partial_failed":
        message = "Batch cue update partially failed; inspect per-cue results and errors."
    elif status == "verification_failed":
        message = "Batch cue update commands completed, but fresh verification failed."
    elif status == "verification_inconclusive":
        message = "Batch cue update commands completed, but deterministic verification was not available."
    elif status == "updated_with_confirmed_timeouts":
        message = "Batch cue update completed; some setters timed out but fresh after-reads confirmed requested values."
    else:
        message = "Batch cue update completed and fresh after-reads confirmed requested values."
    global_warnings = list(warnings or [])
    if status == "updated_with_confirmed_timeouts":
        global_warnings.append("One or more setters did not reply before timeout, but fresh after-reads confirmed the changes.")
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": requested_count,
        "planned_count": planned_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "timeout_confirmed_count": timeout_confirmed_count,
        "results": results,
        "errors": errors,
        "warnings": global_warnings,
        "error_code": None if ok else UPDATE_STATUS_CODES.get(status, f"QLAB_UPDATE_{status.upper()}"),
        "suggested_action": None if ok else UPDATE_STATUS_ACTIONS.get(status, "Inspect per-cue results before retrying."),
        "message": message,
    }
