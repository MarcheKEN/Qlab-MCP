# LIGHT PLAN — MVP read model and LCL analyzer

Snapshot: 2026-06-19

Verified QLab: 5.5.10

Scope: read-only analysis and planning. This document does not authorize changes in QLab or the MCP.

## 1. Executive summary

The current MCP can already retrieve the two main sources needed to understand lighting:

- `/settings/light/patch`, through `qlab_get_workspace_setting_details`, contains instruments, groups, definitions, and parameters.
- The `auto` and `inspector_safe` profiles of `qlab_get_cue_details` return `lightCommandText`, `alwaysCollate`, `subcontroller`, duration, and status for each Light Cue.

The main gap is not OSC access; it is normalization. The safe Light Patch is exposed as the tabular `instrument_index`, deep parameters are omitted, and no semantic Lighting Command Language (LCL) analysis exists. The minimal proposal keeps the existing tools, expands the safe Light Patch output, and then adds one read-only tool for analyzing LCL text.

Reading or controlling the Light Dashboard Live state is out of scope. Writing cues, the patch, levels, groups, instruments, definitions, or DMX addresses is also out of scope.

## 2. Official QLab 5 sources and behavior

Official sources consulted:

- [The Light Patch Editor](https://qlab.app/docs/v5/lighting/light-patch-editor/)
- [Light Cues](https://qlab.app/docs/v5/lighting/light-cues/)
- [The Light Dashboard](https://qlab.app/docs/v5/lighting/light-dashboard/)
- [The Lighting Command Language](https://qlab.app/docs/v5/lighting/lighting-command-language/)
- [QLab's OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)

### 2.1 Light Patch

The Light Patch belongs to `Workspace Settings → Light`. The editor shows instruments and groups, per-instrument parameters, the assigned definition, and patch state. Names must be unique within the workspace. An instrument may be unpatched or broken because of an address conflict; an unpatched instrument does not appear in the Light Dashboard.

The OSC Dictionary defines `/workspace/{id}/settings/light/patch` as read-only for view, edit, and control permissions. It returns JSON containing:

- `settingKeywords`: al menos `home`, `pass` y `cue`.
- `instruments[]`: `name`, `patched`, `conflicted`, `definition` y `parameters[]`.
- `groups[]`: name, members, expanded instruments, and group parameters.
- Definition: `name`, `manufacturer`, `definitionVersion`, `defaultParameter`, `isBroken`, and a parameter map.
- Parameter: `name`, `type`, `homeValue`, `homeValueInDMX`, `valueIsPercentage`, `twoBytes`, `uniqueName`, and `definitionParameter` where applicable.

`twoBytes` distinguishes 8-bit and 16-bit parameters. `valueIsPercentage` distinguishes percentage values from raw DMX values. The documented payload does not publish a normalized list of DMX addresses or each parameter's physical destination; it publishes `patched` and `conflicted`.

With multiple workspaces open, an explicit UUID must be used. A message without `/workspace/{id}` may reach every workspace listening on the same port. The observed workspace names contain spaces or diacritics, so the UUID also avoids OSC character restrictions that apply to the display name.

### 2.2 Light Cues

A Light Cue contains LCL text, duration, and a curve. It has no cue target: it may affect one or more Light Patch parameters. Its commands are interpreted sequentially, from top to bottom.

Confirmed cue-specific OSC reads:

| Campo | Mensaje | Lectura oficial |
| --- | --- | --- |
| `lightCommandText` | `/cue/{cue_number}/lightCommandText` | Complete command text |
| `alwaysCollate` | `/cue/{cue_number}/alwaysCollate` | State of “Collate effects of previous light cues” |
| `subcontroller` | `/cue/{cue_number}/subcontroller` | State of “Use as subcontroller in dashboard” |

Duration, identity, armed/broken/warning, and waits belong to the common cue messages and are already part of the current detail profiles.

QLab documents four main causes of a broken Light Cue:

1. Invalid LCL command.
2. None of the referenced instruments is correctly patched.
3. Broken instrument definition.
4. Required USB DMX device disconnected.

The `isBroken` boolean alone does not identify which cause applies.

### 2.3 Lighting Command Language

Official basic forms:

```text
instrument = value
instrument.parameter = value
group = value
group.parameter = value
```

Spaces around `=` are optional. If the parameter is omitted, QLab uses the instrument's defined default parameter. For `group.parameter`, QLab applies the value only to members that have that parameter. `home` uses the defined home value; `pass` explicitly excludes the target from the cue adjustment.

QLab supports more syntax—ranges, ad hoc groups, pull from another cue, and compound values—but it is outside the proposed MVP.

### 2.4 Light Dashboard

The Light Dashboard represents Live and Audition levels, provides immediate control, and can record or update Light Cues. It is deliberately outside this phase. Reading the patch or a cue's text is not equivalent to reading the current look, determining the “active” lighting cue, or simulating the accumulated result of previous cues.

## 3. Current repository implementation

### 3.1 Prior Git state

State observed before creating this document:

```text
 M README.md
?? docs/cue_detail_read_coverage_probe_report.md
?? docs/runtime_concurrency_probe_report.md
?? docs/runtime_tool_probe_report.md
```

Those changes predate this document and are out of scope.

### 3.2 Exposed MCP tools

Ten tools detected. Seven are read-only inspection tools:

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_status`
4. `qlab_get_workspace_settings`
5. `qlab_get_workspace_setting_details`
6. `qlab_query_cues`
7. `qlab_get_cue_details`

Three tools target the write flow and were not used for this work:

1. `qlab_check_write_readiness` — non-mutating preflight, but part of the write flow.
2. `qlab_create_cue`
3. `qlab_update_cues`

The server does not expose GO, stop, panic, or raw OSC as MCP tools.

### 3.3 Current Light Patch read

`src/qlab_mcp/settings/workspace.py` uses the workspace-qualified address `settings/light/patch`. It tries UDP first and uses TCP as a fallback for large payloads.

Perfil `safe`:

- Returns `summary`, `groups`, `instrument_index`, and `definition_counts`.
- `instrument_index` uses the columns `name`, `comment`, `patched`, `conflicted`, `definition`, `manufacturer`, `parameter_count`, and `parameter_names`.
- Deduplicates instruments present both at the top level and inside groups.
- Explicitly omits `instrument.definition.parameters` and `instrument.parameters[].definitionParameter`.

Perfiles `technical` y `exhaustive`:

- Preserve the Light Patch payload under `details.patch` after applying general redaction.
- Allow inspection of definitions and deep parameters, but do not yet provide a stable normalized model.

The settings summary view does not read the Light Patch in the safe profile; it returns `patch_read: "skipped"` and advertises the available detail request. This avoids downloading a large payload unintentionally.

### 3.4 Current Light Cue read

`AUTO_LIGHT_KEYS` contains exactly:

```text
lightCommandText
alwaysCollate
subcontroller
```

`qlab_query_cues(primary_filter="type", primary_value="Light")` locates cues and returns compact identity/status. `qlab_get_cue_details(profile="auto"|"inspector_safe")` adds common fields, timing, and the three Light Cue-specific fields. The MCP does not analyze `lightCommandText`; it only returns it.

The current health logic derives a generic warning when `isBroken=true`. It does not distinguish an invalid command, incomplete patch, broken definition, or missing device.

## 4. Actual runtime findings

All calls used an explicit UUID. No write-facing tool, playback, Dashboard, or raw OSC call was made.

### 4.1 Connection and workspaces

`qlab_check_connection(require_read_access=true)` without a UUID returned:

```json
{
  "ok": false,
  "status": "workspace_ambiguous",
  "qlab_reachable": true,
  "workspace_count": 3,
  "message": "QLab is reachable, but multiple workspaces are open and no workspace_id was provided."
}
```

Detected workspaces:

| Workspace | UUID | QLab | Readable cue lists |
| --- | --- | --- | ---: |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 5 |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 1 |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 7 |

All three explicit checks returned `ok=true`, `status="ready"`, `workspace_readable=true`, and `qlab_version="5.5.10"`.

### 4.2 Settings summary

En los tres UUID, esta llamada:

```json
{
  "mode": "summary",
  "sections": ["light"],
  "profile": "safe"
}
```

returned the same Light contract:

```json
{
  "summary": {
    "details_available": true,
    "patch_read": "skipped",
    "message": "Use qlab_get_workspace_setting_details with section='light' and kind='light_patch' to inspect the light patch."
  }
}
```

It also advertised `{"section":"light","kind":"light_patch","ref":null}` in `available_detail_requests`.

### 4.3 Safe Light Patch

Call used per workspace:

```json
{
  "section": "light",
  "kind": "light_patch",
  "profile": "safe",
  "workspace_id": "<Explicit UUID>"
}
```

Relevant exact results:

| Workspace | `patch_present` | Instruments | Groups | Transport | Unpatched | Conflicts |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| `<TEST_WORKSPACE_NAME>` | true | 59 | 6 | `tcp_fallback` | 2 | 0 |
| `<TEST_WORKSPACE_NAME>` | true | 0 | 0 | `udp` | 0 | 0 |
| `<TEST_WORKSPACE_NAME>` | true | 60 | 13 | `tcp_fallback` | 12 | 0 |

`patch_present=true` with zero elements represents a correctly returned but empty patch; it does not mean that instruments exist.

The first test workspace returned:

```json
{
  "definition_counts": {
    "Generic Dimmer": 46,
    "Generic RGBWA+UV": 13
  },
  "technical_payloads_omitted": [
    "instrument.definition.parameters",
    "instrument.parameters[].definitionParameter"
  ]
}
```

The observed unpatched instruments were `32 Cuna` and `104 FRONTAL`. The RGBWA+UV fixtures published seven parameter names: `color`, `red`, `green`, `blue`, `white`, `amber`, `uv`.

The third test workspace returned `{"definition_counts":{"Generic Dimmer":60}}`. Unpatched instruments: `07 PC refuerzo 1`, `10 PC refuerzo 4`, `37 Contra L medio`, `38 Contra L arriba`, `40 Contra R centro`, `41 Contra R arriba`, `46 Sala 2`, `46 Sala 3`, `46 Sala 4`, `48 Cabina`, `49 Cabina`, and `50 Puntual butaca`.

The complete arrays of 59 and 60 instruments and the complete group-member lists are not reproduced here. The figures, exceptional names, and keys above come directly from the response; omitting them avoids turning the document into a runtime dump.

### 4.4 Light Cue query

Arguments used:

```json
{
  "primary_filter": "type",
  "primary_value": "Light",
  "profile": "basic_safe",
  "max_cues_scanned": 5000,
  "max_results": 10,
  "workspace_id": "<Explicit UUID>"
}
```

| Workspace | Escaneadas | Light Cues | Devueltas | `query_completeness` | `truncated` | Motivo |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `<TEST_WORKSPACE_NAME>` | 316 | 90 | 10 | `complete` | true | `max_results` |
| `<TEST_WORKSPACE_NAME>` | 30 | 1 | 1 | `complete` | false | — |
| `<TEST_WORKSPACE_NAME>` | 1424 | 933 | 10 | `complete` | true | `max_results` |

`status="partial"` in the first and third workspaces indicates a result limit, not an incomplete scan: both returned `scanned_all_cues=true` and `id_only_unscanned_count=0`.

### 4.5 Representative cue details

Profile used: `inspector_safe`.

Primer workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "type_specific": {
    "lightCommandText": "20 Calle Arbol = 100\n21 Calle Arbol = 100",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {
    "preWait": 0,
    "duration": 2.5,
    "postWait": 0,
    "continueMode": 0,
    "continueModeLabel": "do_not_continue"
  },
  "status": {
    "armed": true,
    "isBroken": false,
    "isWarning": false
  }
}
```

Segundo workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "number": "12",
  "name": "LIGHT_DISARMED_BROKEN",
  "type_specific": {
    "lightCommandText": "all = home",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {"duration": 5},
  "status": {
    "armed": false,
    "isBroken": true,
    "isWarning": false
  }
}
```

Tercer workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "number": "LX0",
  "name": "OSCURO",
  "type_specific": {
    "lightCommandText": "all = home",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {"duration": 5},
  "status": {
    "armed": true,
    "isBroken": false,
    "isWarning": false
  }
}
```

The excerpts reduce common fields unrelated to lighting; displayed values and key names have not been reinterpreted.

## 5. What can be read through OSC

- Identidad de workspaces abiertos y sus UUID.
- Complete Light Patch documented through `/settings/light/patch`.
- Instruments and groups, including membership.
- `patched` and `conflicted` state per instrument.
- Embedded definition, manufacturer, version, `isBroken`, and default parameter.
- Physical and virtual parameters published by QLab, home values, percentage/DMX scale, and 8/16-bit type.
- Light Cue list and common state.
- Complete `lightCommandText` text.
- `alwaysCollate` y `subcontroller`.
- Duration, waits, continue mode, armed, broken, and warning.

## 6. What these reads do not provide

- Normalized DMX addresses per parameter: they do not appear in the official schema published for `/settings/light/patch`.
- Current Live state of the Light Dashboard, yellow modifications, originating levels, or accumulated look.
- Confirmation of real physical output, visible stage light, or end-to-end Art-Net, sACN, or USB DMX health.
- Exact cause of `isBroken=true`; it must be inferred from the patch/command and may require human inspection.
- Final result of running a Light Cue sequence, including collation, historical order, curves, and previous values.
- Complete validation of the LCL grammar through a dedicated read-only OSC endpoint; QLab exposes text and broken state, not an AST or structured diagnostic.

The OSC Dictionary does contain setters and Dashboard/cue commands. Their existence does not make them reads or include them in this phase.

## 7. Proposed read model

The model will compose the existing settings, query, and cue-details data; another MCP aggregator is not needed.

```json
{
  "workspace_id": "UUID",
  "instruments": [
    {
      "name": "string",
      "comment": "string|null",
      "patched": true,
      "conflicted": false,
      "definition": {
        "name": "string|null",
        "manufacturer": "string|null",
        "version": "number|string|null",
        "broken": false,
        "default_parameter_index": 0,
        "default_parameter_name": "intensity|null"
      },
      "parameter_names": ["intensity"]
    }
  ],
  "groups": [
    {
      "name": "string",
      "instrument_names": ["string"],
      "parameter_names": ["string"]
    }
  ],
  "parameters": [
    {
      "scope": "instrument|group",
      "owner_name": "string",
      "name": "string",
      "unique_name": "string|null",
      "type": "scalar|pantilt|rgbcolor|cmycolor|muxer|unknown",
      "broken": false,
      "home_value": null,
      "home_value_dmx": null,
      "value_is_percentage": null,
      "two_bytes": null
    }
  ],
  "light_cues": [
    {
      "unique_id": "UUID",
      "number": "string",
      "name": "string",
      "duration": 0,
      "armed": true,
      "broken": false,
      "warning": false,
      "always_collate": false,
      "subcontroller": false,
      "command_text": "string"
    }
  ],
  "warnings": [],
  "errors": [],
  "unsupported_or_unavailable_fields": []
}
```

Model rules:

- Preserve original names and text; add normalized fields without replacing the source payload.
- Distinguish `null`/unavailable from `false`, `0`, and an empty collection.
- Derive `default_parameter_name` from `definition.defaultParameter` and the parameter map. If it cannot be resolved, leave `null` and add a warning.
- An empty patch is a successful result with empty arrays.
- An instrument with `patched=false`, `conflicted=true`, or a broken definition generates a structured warning, not a transport error.
- Keep `instrument_index` for compatibility; add `instruments[]` and `parameters[]` without breaking existing consumers.
- Declare omissions in `unsupported_or_unavailable_fields`; never invent addresses, Live levels, or the exact cause of a broken cue.

## 8. Read-only LCL analyzer MVP

Minimal future tool:

```text
qlab_analyze_light_command_text(workspace_id: string, command_text: string)
```

The tool will read the Light Patch for the supplied UUID and will not send setters. Getting text from a cue remains the responsibility of `qlab_get_cue_details`; no second mode keyed by `cue_ref` is added.

### 8.1 Supported grammar

One assignment per line:

```text
target [ "." parameter ] "=" value
value := number | "home" | "pass"
```

Optional spaces around `=` and at line ends are accepted. Empty lines are ignored. The original text and line number are preserved.

### 8.2 Resolution

1. Find an exact target among instruments and groups.
2. If none exists, try a unique case-insensitive match and set `normalized_match=true`.
3. More than one normalized match produces `ambiguous_target`; no match produces `unknown_target`.
4. Target with an explicit parameter:
   - Instrument: verify that it has the parameter.
   - Group: expand only members that have it; incompatible members remain in `skipped_members`.
5. Target without a parameter:
   - Instrument: resolve its `defaultParameter`.
   - Group: resolve each member's default; the result may contain different parameters.
6. `all` is not an implicit analyzer keyword. It is valid only when a group named `all` exists in that workspace.
7. `home` and `pass` are accepted as symbolic values; the analyzer does not calculate the resulting Live state.

Per-line output:

```json
{
  "line": 1,
  "source": "Back.red = 50",
  "status": "valid|warning|invalid|unsupported",
  "target": {
    "input": "Back",
    "resolved_name": "back|null",
    "kind": "instrument|group|null",
    "exists": true,
    "normalized_match": true
  },
  "parameter": {
    "input": "red|null",
    "exists": true,
    "defaulted": false
  },
  "value": {"kind": "number|home|pass", "raw": "50"},
  "affected": [
    {"instrument": "110 CONTRA", "parameter": "red"}
  ],
  "skipped_members": [],
  "warnings": [],
  "errors": []
}
```

### 8.3 Syntax outside the MVP

Return `status="unsupported"`, never a partial interpretation, for:

- Rangos y listas: `1 - 3 = 50`, `1, 2 = 50`.
- Grupos ad hoc: `[1 - 3] = 50`.
- Pull desde cue: `10 = cue A`.
- Compound values or functions: color, pan/tilt, muxers, and equivalent forms.
- Operators, expressions, multiple assignments on one line, or unrecognized text.
- Any valid LCL form not explicitly included in the MVP grammar.

The analyzer does not reorder, prune, or replace commands. It also does not simulate duplicate commands, historical sequence, fade, `alwaysCollate`, subcontroller, Dashboard, or DMX.

### 8.4 Minimal expected examples

| Entrada | Resultado esperado |
| --- | --- |
| `Front = 100` | Target resolved; instrument default; affected members listed |
| `Back.red = 50` | Valid group; only members with `red` |
| `All = 0` | Valid only if group `all` exists; normalized match may be possible |
| `Front = home` | Defaults resolved; home values available as metadata |
| `Back = pass` | Affected members identified; no look simulation |

## 9. MCP changes required in later phases

1. Expand safe Light Patch normalization:
   - Add `instruments[]`, `groups[].parameter_names`, and `parameters[]`.
   - Resolve broken definitions and default parameters.
   - Keep `instrument_index` and `definition_counts` for compatibility.
2. Add structured warnings:
   - Unpatched instruments, conflicts, broken definitions/parameters, and incomplete metadata.
   - Distinguish unexposed data, profile omissions, and transport failures.
3. Add `qlab_analyze_light_command_text` with the grammar above.
4. Reuse `qlab_query_cues` and `qlab_get_cue_details`; do not create `qlab_get_light_model` or another aggregator until need is demonstrated.
5. Keep the TCP fallback for large payloads and require UUIDs in every new tool.

## 10. Safety rules

- Only documented read-only OSC and MCP inspection tools.
- Always use an explicit UUID when multiple workspaces are open.
- GO, playback, start, stop, panic, audition, and preview are prohibited.
- Raw OSC and Live Dashboard control are prohibited.
- `dashboard/setLight`, `dashboard/clear`, `newCueWithAll`, `newCueWithChanges`, `recordAllToLatest`, `updateSelectedCues`, `collateAndStart`, setters, and ordering/prune/replace operations are prohibited.
- Modifying the Light Patch, instruments, groups, definitions, DMX addresses, and Light Cues is prohibited.
- Treat `lightCommandText` as untrusted data: enforce size/line limits and do not execute or forward it to QLab.
- A `valid` analysis means “accepted and resolvable by this MVP,” not a guarantee of physical output or equivalence with QLab's internal parser.
- Never hide unknown syntax: return `unsupported` with the original line and text.

## 11. Test plan for the future runtime probe

### 11.1 Unit tests

- Normalize an empty patch, simple instrument, RGBWA+UV fixture, mixed group, and broken definition.
- Resolve valid, missing, and out-of-map `defaultParameter` values.
- Preserve 8/16-bit, percentage/DMX, home, and parameter type data.
- Detect unpatched/conflicted states without turning them into transport errors.
- Test the five MVP examples.
- Test an unknown target, unknown parameter, and target made ambiguous by normalization.
- Test a group where only some members have the parameter.
- Reject ranges, ad hoc groups, `cue`, compound values, and expressions as `unsupported`.
- Verify that the parser never calls setters or generates mutating OSC addresses.

### 11.2 Simulated MCP integration

- `qlab_get_workspace_setting_details(profile="safe")` preserves `instrument_index` and adds normalized arrays.
- `technical` preserves the deep payload without changing redactions.
- TCP fallback produces the same model as UDP.
- The analyzer requires a valid UUID, limits size, and returns per-line partial errors without aborting independent lines.
- An empty patch permits analysis only as `unknown_target`, without raising an exception.

### 11.3 Read-only runtime

- Repeat against the three UUIDs in the snapshot.
- Confirm 59/0/60 instruments and 6/0/13 groups while the workspaces remain unchanged.
- Repeat the complete Light Cue query and record `matched_count`, `scanned_all_cues`, and truncation.
- Read several cues per workspace, including a broken cue from the test workspace and cues with group/parameter commands.
- Compare the analyzer with patch identity, groups, and parameters without executing cues.
- Record any difference as a workspace change or model incompatibility; never “correct” QLab automatically.

### 11.4 Acceptance criteria

- Zero mutating messages sent to QLab.
- Every read is workspace-qualified with a UUID.
- The model distinguishes empty, omitted, unavailable, warning, and error states.
- Every LCL line produces a deterministic, traceable result.
- Syntax outside the MVP is explicitly marked.
- Future changes preserve existing contracts or document versioning/migration.
