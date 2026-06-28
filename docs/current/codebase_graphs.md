# Codebase Graphs

Proyecto Codebase MCP: `Users-filarmonica-Documents-qlab-mcp-osc`.

Snapshot:

- 1787 nodos, 10305 relaciones.
- Nodos principales: 756 funciones, 271 metodos, 73 modulos, 52 clases.
- Relaciones principales: 2645 `CALLS`, 1407 `USAGE`, 1004 `TESTS`, 541 `WRITES`, 222 `IMPORTS`.
- Entry point: `qlab-mcp = qlab_mcp.server:main`.
- Runtime FastMCP: `src/qlab_mcp/server.py:mcp`.

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

    Connection --> OSC["osc.client<br/>UDP + TCP fallback"]
    Overview --> OSC
    Query --> OSC
    Details --> OSC
    Settings --> OSC
    Status --> OSC
    Write --> Safety["write.safety<br/>write gates"]
    Write --> Registry["write.registry<br/>allowlisted profiles"]
    Write --> OSC

    OSC --> QLab["QLab 5 OSC"]
```

## Herramientas MCP Expuestas

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
    Tools --> Update["qlab_update_cues"]
```

## Flujo Read-Only Recomendado

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

    User->>S: qlab_get_workspace_overview()
    S->>R: get_workspace_overview()
    R->>C: bounded cue-list/cue reads
    C->>Q: OSC UDP/TCP fallback
    Q-->>C: JSON reply
    S-->>User: WorkspaceOverviewResult
```

## Flujo Write Gated

```mermaid
flowchart TD
    Update["qlab_update_cues"] --> Ready["ensure_write_ready"]
    Ready --> Env["QLAB_ENABLE_WRITE=true<br/>QLAB_PASSCODE set"]
    Ready --> Connect["/connect confirms edit scope"]
    Ready --> Mode["/showMode confirms Edit Mode"]
    Update --> DryRun{"dry_run?"}
    DryRun -->|true| Plan["build planned_operations<br/>no setters sent"]
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
    Update["write.operations.QLabWriteMixin.update_cues<br/>in:182 out:97"] --> Many["many phase/profile helpers"]
    Overview["cues.overview.CueOverviewMixin.get_workspace_overview<br/>in:30 out:13"] --> ReadMap["tree + index + counts"]
    Client["osc.client.QLabOscClient.request<br/>in:12 out:4"] --> Boundary["QLab OSC boundary"]
    Reader["qlab.QLabReader<br/>in:340"] --> Mixins["connection/settings/status/cues/write mixins"]
```

## Cambio Seguro: Donde Tocar

- Nueva tool MCP: empezar en `src/qlab_mcp/server.py`, delegar a `QLabReader`.
- Nueva lectura de cues: mirar `src/qlab_mcp/cues/*`; usar `_request_data` para cache seguro.
- Nueva lectura de settings: mirar `src/qlab_mcp/settings/workspace.py`.
- Nuevo write profile: mirar primero `src/qlab_mcp/write/registry.py`; luego el minimo helper en `src/qlab_mcp/write/operations.py`.
- Cambios OSC bajo nivel: tocar `src/qlab_mcp/osc/client.py` solo si el problema es transporte, timeout, parseo o passcode.

## Checks Minimos

```bash
uv run pytest tests/test_server_tools.py
uv run pytest tests/test_write_mode.py
uv run pytest tests/test_qlab_reader.py
```
