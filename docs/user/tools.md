# Public MCP Tools

QLab MCP 0.2.0 exposes exactly 13 tools. This page is a human index; the
decorated functions, generated schemas, and `tests/test_server_tools.py` are
the source of truth for exact annotations and constraints.

| Tool | Arguments and defaults | Return | Mode |
| --- | --- | --- | --- |
| `qlab_check_connection` | `workspace_id=None`, `require_read_access=True` | `QlabConnectionCheckResult` | Read-only |
| `qlab_get_workspace_overview` | `workspace_id=None`, `max_depth=2`, `max_cues=1000`, `include_live_state=False`, `include_cue_index=True`, `max_index_cues=5000`, `cue_index_profile="minimal"`, `include_global_count=False` | `WorkspaceOverviewResult` | Read-only |
| `qlab_get_workspace_status` | `workspace_id`, `profile="summary"`, `include_timecode=True`, `max_cues_scanned=1000`, `sample_limit=10` | `WorkspaceStatusResult` | Read-only |
| `qlab_get_workspace_settings` | `workspace_id`, `mode="summary"`, `sections=None`, `requests=None`, `profile="safe"` | `WorkspaceSettingsResult` | Read-only |
| `qlab_get_workspace_setting_details` | `workspace_id`, `section`, `kind=None`, `ref=None`, `profile="safe"` | `WorkspaceSettingDetailsResult` | Read-only compatibility wrapper |
| `qlab_query_cues` | `workspace_id`, `primary_filter`, `primary_value`, `optional_filters=None`, `profile="basic_safe"`, `max_results=500`, `max_cues_scanned=500` | `CueQueryResult` | Read-only |
| `qlab_get_cue_details` | `workspace_id`, `cue_ref`, `profile="auto"` | `CueDetailsResult` or `CueDetailsBatchResult` | Read-only |
| `qlab_check_write_readiness` | `workspace_id` | `WriteReadinessResult` | Read-only preflight |
| `qlab_create_cue` | `workspace_id`, `cue_type`, exactly one of `after_cue_id` or `parent_container_id`, `dry_run=None`, `confirm_token=None` | `CreateCueResult` | Gated structural write |
| `qlab_edit_cues` | `workspace_id`, `updates`, `dry_run=None` | `UpdateCuesResult` | Gated write |
| `qlab_update_cues` | Same arguments and defaults as `qlab_edit_cues` | `UpdateCuesResult` | Compatible alias |
| `qlab_move_cues` | `workspace_id`, `moves`, `dry_run=None`, `confirm_token=None` | `MoveCuesResult` | Gated structural write |
| `qlab_delete_cues` | `workspace_id`, `cue_ids`, `dry_run=None`, `confirm_token=None` | `DeleteCuesResult` | Gated destructive write |

`dry_run=None` follows `QLAB_WRITE_DRY_RUN_DEFAULT`, which defaults to dry-run.
Create accepts only `memo`, `group`, `wait`, or `audio`. It has no initial
properties argument and sends no property setters: QLab's Cue Template supplies
the cue's default state. Real Create requires a fresh `confirm:createCue:v2`
token bound to the workspace structure and returns a structured
`CreateCueResult` with the created UUID, placement, fresh verification,
executed operations, warnings/errors, and `cleanup_required`/manual cleanup
guidance. `after_cue_id` uses the anchored route. `parent_container_id` uses
`currentCueListID` plus unanchored `/new` for an empty Cue List, `/new` plus
one `/move` for an empty Group, and direct `/new` with Cart request coordinates
`0,0` for an empty Cue Cart. In QLab 5.5.10 the first Cart cell is reported as
readback coordinates `1,1`; the verifier handles that runtime normalization.
An ambiguous `/new` timeout is never retried and receives no setters.
Edit accepts
1–50 updates; Move and Delete accept 1–10 exact UUID targets. Delete is
leaf-only, sequential, non-atomic, and does not cascade; real deletion requires
its exact fresh `confirm:deleteCues:v1` token.

`qlab_update_cues` calls `qlab_edit_cues` directly and remains available for
older clients. Move and Delete are intentional public additions, not aliases.

Generate the current machine-readable schemas with:

```bash
uv run fastmcp inspect fastmcp.json
```
