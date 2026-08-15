# Codebase Graphs

Codebase MCP project: `<CODEBASE_PROJECT_ID>`.

Snapshot regenerated with `codebase-memory-mcp` on 2026-07-09.

- 2363 nodes, 14148 relationships.
- Main nodes: 1037 functions, 403 sections, 338 variables, 285 methods, 106 modules, 105 files, 52 classes.
- Main relationships: 3582 `SEMANTICALLY_RELATED`, 3568 `CALLS`, 2221 `DEFINES`, 1762 `USAGE`, 1248 `TESTS`, 691 `WRITES`.
- Indexed languages: Python 44 files, TOML 1 file.
- Entry point: `qlab-mcp = qlab_mcp.server:main`.
- Runtime FastMCP: `src/qlab_mcp/server.py:mcp`.
- Local index persistence: the MCP returned `artifact_present:false`; `.codebase-memory/graph.db.zst` was not found in the repository.

## Arquitectura

```mermaid
flowchart TD
    Client["MCP client"] --> Server["server.py / FastMCP tools"]
    Server --> Reader["QLabReader facade"]

    Reader --> Connection["runtime.connection<br/>connect/readiness/status probes"]
    Reader --> Overview["cues.overview<br/>show map + cue index"]
    Reader --> Query["cues.query<br/>cue search"]
    Reader --> Details["cues.details<br/>cue detail profiles"]
    Reader --> Settings["settings.workspace<br/>workspace settings"]
    Reader --> Status["status.py<br/>derived workspace status"]
    Reader --> Write["write.operations<br/>create/update gated writes"]

    Details --> Profiles["cues.profiles<br/>video/text/camera summaries"]
    Connection --> OSC["osc.client<br/>UDP + TCP fallback"]
    Overview --> OSC
    Query --> OSC
    Details --> OSC
    Settings --> OSC
    Status --> OSC
    Write --> Safety["write.safety<br/>write gates"]
    Write --> Registry["write.registry<br/>allowlisted profiles"]
    Write --> Timeouts["write.timeouts<br/>operation budgets"]
    Write --> OSC

    OSC --> QLab["QLab 5 OSC"]
```

## Exposed MCP Tools

```mermaid
flowchart LR
    Tools["server.py FastMCP"] --> Check["qlab_check_connection"]
    Tools --> Overview["qlab_get_workspace_overview"]
    Tools --> Status["qlab_get_workspace_status"]
    Tools --> Settings["qlab_get_workspace_settings"]
    Tools --> SettingDetails["qlab_get_workspace_setting_details"]
    Tools --> Query["qlab_query_cues"]
    Tools --> CueDetails["qlab_get_cue_details"]
    Tools --> Ready["qlab_check_write_readiness"]
    Tools --> Create["qlab_create_cue"]
    Tools --> Edit["qlab_edit_cues"]
    Tools --> UpdateAlias["qlab_update_cues<br/>compatibility alias"]
```

## Recommended Read-Only Flow

```mermaid
sequenceDiagram
    participant User as MCP caller
    participant S as server.py
    participant R as QLabReader
    participant C as QLabOscClient
    participant Q as QLab

    User->>S: qlab_check_connection()
    S->>R: check_connection()
    R->>C: request(/workspaces, /connect, /showMode)
    C->>Q: OSC UDP
    Q-->>C: JSON reply
    C-->>R: QLabReply
    R-->>S: normalized dict
    S-->>User: QlabConnectionCheckResult

    User->>S: qlab_get_cue_details(profile="inspector_safe")
    S->>R: get_cue_details()
    R->>C: bounded cue reads
    C->>Q: OSC UDP/TCP fallback
    Q-->>C: JSON reply
    S-->>User: CueDetailsResult
```

## Gated Write Flow

```mermaid
flowchart TD
    Edit["qlab_edit_cues"] --> Alias["qlab_update_cues alias"]
    Alias --> Update["QLabWriteMixin.update_cues"]
    Edit --> Update
    Update --> Ready["ensure_write_ready"]
    Ready --> Env["QLAB_ENABLE_WRITE=true<br/>QLAB_PASSCODE set"]
    Ready --> Connect["/connect confirms edit scope"]
    Ready --> Mode["/showMode confirms Edit Mode"]
    Update --> DryRun{"dry_run?"}
    DryRun -->|true| Plan["plan + diff<br/>no setters sent"]
    DryRun -->|false| Validate["validate profile + confirm gates"]
    Validate --> Registry["write.registry specs"]
    Validate --> BatchGate{"any preflight error?"}
    BatchGate -->|yes| Block["send zero setters"]
    BatchGate -->|no| Setters["send allowlisted OSC setters"]
    Setters --> ClearCache["clear read cache"]
    Setters --> Verify["readback/verification"]
```

## OSC Core

```mermaid
flowchart TD
    Request["QLabOscClient.request"] --> Lock["per host/port lock"]
    Lock --> UDP["UDP socket bound to reply_port"]
    UDP --> Connect{"workspace_id + passcode<br/>not connected?"}
    Connect -->|yes| ConnectMsg["/workspace/{id}/connect"]
    Connect -->|no| Send["send OSC packet"]
    ConnectMsg --> Send
    Send --> Parse["decode JSON reply"]
    Parse --> Status{"status ok?"}
    Status -->|ok| Reply["QLabReply"]
    Status -->|not ok| Error["QLabReplyError"]

    LargeRead["large read helper"] --> UDPFirst["try UDP"]
    UDPFirst -->|timeout| TCP["request_tcp with SLIP framing"]
```

## Codebase MCP Hotspots

```mermaid
flowchart LR
    Update["write.operations.QLabWriteMixin.update_cues<br/>fan-in:222"] --> WriteMix["planning + validation + tokens + execution + verification"]
    Edit["write.operations.QLabWriteMixin.edit_cues<br/>fan-in:71"] --> Update
    Details["cues.details.CueDetailsMixin.get_cue_details<br/>fan-in:64"] --> Profiles["cues.profiles"]
    UpdateOne["write.operations.QLabWriteMixin.update_cue<br/>fan-in:44"] --> Update
    Cache["runtime.read_cache.ReadCache.clear<br/>fan-in:41"] --> OSCBoundary["OSC/readback boundary"]
    Resolve["write.operations._resolved_cue_id<br/>fan-in:36"] --> Update
```

## Video/Text/Camera Write Surface

- `video_basic`: common cue fields plus video visual, geometry, IO, embedded audio, slice marker and video FX paths. Most real writes are specialized and confirm-token gated.
- `camera_basic`: common fields plus mic/video/catalog camera paths. Shares much of video visual geometry machinery.
- `text_basic`: common fields, text content basics, selected visual properties, and rich text/style paths. Phase 3F real writes remain blocked where fresh readback is unreliable.
- Public preferred tool name is `qlab_edit_cues`; `qlab_update_cues` remains a compatibility alias.

## Safe Changes: Where to Work

- New MCP tool: start in `src/qlab_mcp/server.py`, delegate to `QLabReader`, and do not change public signatures without an explicit decision.
- New cue read: inspect `src/qlab_mcp/cues/*`; use `_request_data` and the `cues.profiles` profiles.
- New settings read: inspect `src/qlab_mcp/settings/workspace.py`.
- New write profile: inspect `src/qlab_mcp/write/registry.py` first, then add the smallest helper in `src/qlab_mcp/write/operations.py`.
- Write refactor: extract one responsibility at a time from `src/qlab_mcp/write/operations.py`; do not split every family in one PR.
- Low-level OSC changes: touch `src/qlab_mcp/osc/client.py` only when the problem is transport, timeout, parsing, or passcode handling.

## Minimum Checks

```bash
uv run pytest tests/test_server_tools.py
uv run pytest tests/test_write_mode.py tests/test_update_registry_coverage.py
uv run pytest tests/test_qlab_reader.py
```
