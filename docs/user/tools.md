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
| `qlab_create_cue` | `workspace_id`, `cue_type`, `after_cue_id`, `properties=None`, `dry_run=None`, `confirm_token=None` | `CreateCueResult` | Gated structural write |
| `qlab_edit_cues` | `workspace_id`, `updates`, `dry_run=None` | `UpdateCuesResult` | Gated write |
| `qlab_update_cues` | Same arguments and defaults as `qlab_edit_cues` | `UpdateCuesResult` | Compatible alias |
| `qlab_move_cues` | `workspace_id`, `moves`, `dry_run=None`, `confirm_token=None` | `MoveCuesResult` | Gated structural write |
| `qlab_delete_cues` | `workspace_id`, `cue_ids`, `dry_run=None`, `confirm_token=None` | `DeleteCuesResult` | Gated destructive write |

`dry_run=None` follows `QLAB_WRITE_DRY_RUN_DEFAULT`, which defaults to dry-run.
Create accepts only blank `memo`, `group`, `wait`, or `audio` cues and requires
an exact anchor plus a fresh dry-run token bound to the workspace structure.
Edit accepts
1–50 updates; Move and Delete accept 1–10 exact UUID targets. Delete is
leaf-only and does not cascade.

`qlab_update_cues` calls `qlab_edit_cues` directly and remains available for
older clients. Move and Delete are intentional public additions, not aliases.

Generate the current machine-readable schemas with:

```bash
uv run fastmcp inspect fastmcp.json
```
