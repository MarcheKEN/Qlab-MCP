# QLab MCP

**Give AI agents tools to inspect, create and edit QLab workspaces.**

QLab MCP **0.4.0** connects an MCP-compatible agent to QLab 5, primarily through
OSC. It can organize cues, configure supported properties and inspect workspace
settings. Selected local functions use fixed AppleScript bridges on macOS.
The Light Patch editor also edits the saved local workspace archive under a
guarded close, replace and reopen workflow.

**Developed and tested with QLab 5.5.10 on macOS.** Other QLab versions may
behave differently and have not been validated by this project.

The server provides **82 tools: 50 read-only and 32 gated writes**.
Writes are disabled by default and require a reviewed preview and confirmation.

[Capabilities](#capabilities) · [Installation](#installation) ·
[Configuration](#configuration) · [Tools](#tool-groups) ·
[Documentation](#documentation)

## Capabilities

### What it can do

| Area | Supported work |
| --- | --- |
| Inspect | Discover workspaces, find cues, read properties and diagnose reported problems. |
| Organize | Create cues, edit names/numbers, move cues and reorder Lists/Carts. |
| Configure | Edit supported Audio, Video, Light, Text, MIDI and other cue settings. |
| Workspace settings | Read six settings domains; edit selected General, Audio and Video properties. |
| Light Patch | Read current OSC data and saved local patch configuration in one call; batch create, edit, rename and delete instruments and groups. Manage definitions with a separate catalogue and editor. |
| Local documents | Inspect documents; open, save or clean-close under specific safeguards. |
| Local media | Find authorized files and analyze audio without playing it. |

AppleScript covers local document operations, Load Time, Target assigned number
and selected native triggers. It requires a running `/Applications/QLab.app`
and macOS Automation permission for the MCP host. Ordinary cue access uses OSC.
Light Patch file editing requires local QLab **5.5.10/build 5510**. USB-DMX
assignments store the supplied device identity; they do not discover a device
or prove it is connected. Definition creation/import initially supports scalar and validated RGB variants;
other native variants remain inspectable with explicit import blocks. See the
[definition workflow](docs/user/agent-workflows.md#light-definitions) and [Light Patch workflow](docs/user/agent-workflows.md#edit-the-light-patch)
for recovery and readback limits.

### What it does not do

- Execute cues: no GO, playback, stop, panic or Audition tools.
- Send arbitrary OSC, run arbitrary AppleScript or perform `/live` writes.
- Expose every QLab Inspector setting, Audio Maps or Script compilation.
- Delete root Cue Lists/Carts or execute Cart cell moves.
- Guarantee playback or physical output from a successful configuration change.

Capabilities depend on cue type, readable state and safety gates. Runtime
evidence is scoped to **QLab 5.5.10**; other versions and every possible setting
combination are not claimed as validated. See [supported scope and remaining
limits](docs/status/roadmap.md).

## Installation

### 1. Requirements

- QLab 5 running on macOS, with workspace OSC access configured.
- Python **3.11 or newer**; the commands below use the CI baseline, Python 3.11.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
- An MCP-compatible client that can launch a local **stdio** server.

OSC can target a configured remote QLab host. AppleScript functions require the
MCP server and QLab on the same Mac; they are unavailable for remote QLab.

### 2. Install from the repository

```bash
git clone https://github.com/MarcheKEN/Qlab-MCP.git
cd Qlab-MCP
uv sync --locked --no-editable --python 3.11
```

This installs a snapshot of the project into `.venv`. After updating the
checkout, repeat the sync to install the new source.

### 3. Configure QLab

In the workspace, open **Workspace Settings → Network → OSC Access**:

1. Enable OSC access using the checkbox at the top left.
2. Use **Add Passcode**, or edit an existing passcode row. QLab passcodes are
   four-digit numbers. Enable **View** for inspection and **Edit** if you want
   gated changes. **Control** permits playhead movement and cue start/stop;
   this MCP does not expose playback controls.
3. Copy that passcode into `QLAB_PASSCODE` in your MCP client's environment.
   Preserve any leading zero. For passcode-free inspection, the **No Passcode**
   row must allow View; existing-workspace writes still require a passcode.
4. Check the listening ports:

| QLab setting | Default | Use with this MCP |
| --- | --- | --- |
| OSC Listen Port (TCP and UDP) | `53000` | Set `QLAB_OSC_PORT` to this workspace port. |
| Plain Text Listen Port (UDP) | `53535` | Not used by this server; leave it at its default. |

Set `QLAB_HOST=127.0.0.1` when QLab and the MCP server run on the same Mac,
or use the QLab Mac's reachable address for remote OSC access. The server's
`QLAB_REPLY_PORT` setting is separate from both QLab listening ports.
See [QLab's OSC Access documentation](https://qlab.app/docs/v5/fundamentals/workspace-settings/#the-osc-access-tab).

### 4. Connect your MCP client

#### Codex

Add the following to **`~/.codex/config.toml`**, preserving existing settings.
Codex uses TOML rather than the JSON format shown for other clients below.

```toml
[mcp_servers.qlab]
command = "/absolute/path/Qlab-MCP/.venv/bin/python"
args = ["-m", "qlab_mcp.server"]

[mcp_servers.qlab.env]
QLAB_HOST = "127.0.0.1"
QLAB_OSC_PORT = "53000"
QLAB_PASSCODE = "REPLACE_WITH_QLAB_PASSCODE"
QLAB_ENABLE_WRITE = "false"
QLAB_WRITE_DRY_RUN_DEFAULT = "true"
```

Replace the absolute path and passcode with your own values. Omit
`QLAB_PASSCODE` only for passcode-free inspection configured in QLab above.
Keep this configuration private because it contains your passcode.

Restart Codex after saving. In the desktop app, check that `qlab` is enabled
in the MCP settings, then start a new conversation and ask:

> Use the QLab MCP to check the connection and list the available workspaces.
> Do not modify anything.

The agent should call `qlab_check_connection`. If several workspaces are open,
choose the intended workspace by its exact UUID. To allow edits later, follow
[Enabling writes](#enabling-writes); connecting alone does not enable them.
See [the official Codex MCP guide](https://developers.openai.com/codex/mcp/)
for configuration options.

#### Other MCP clients

Configure your client to launch the installed Python interpreter with
`-m qlab_mcp.server`. For clients using an `mcpServers` JSON configuration:

```json
{
  "mcpServers": {
    "qlab": {
      "command": "/absolute/path/Qlab-MCP/.venv/bin/python",
      "args": ["-m", "qlab_mcp.server"],
      "env": {
        "QLAB_HOST": "127.0.0.1",
        "QLAB_OSC_PORT": "53000",
        "QLAB_ENABLE_WRITE": "false",
        "QLAB_WRITE_DRY_RUN_DEFAULT": "true"
      }
    }
  }
}
```

Replace the absolute path with your checkout location. Other clients may use
TOML or a settings form: provide the same command, arguments and environment.
The client starts the server; a separate terminal server is not required.

Add the matching `QLAB_PASSCODE` to the environment for passcode-protected access.
Restart/reload the connector, then ask the agent to call `qlab_check_connection`.
Choose an exact workspace UUID if several are open.

For startup failures or missing tools, see [setup and troubleshooting](docs/user/setup-and-troubleshooting.md).

### Optional: audio analysis

To use `qlab_analyze_audio_file`, add the audio dependencies:

```bash
uv sync --locked --no-editable --python 3.11 --extra audio
```

FFmpeg and ffprobe must also be available in the **MCP process PATH**.
The server does not install them automatically. Analysis reports source-file
measurements and estimated beats, with explicit continuation pages; it does not
include QLab trims, effects or playback. See [audio analysis](docs/user/agent-workflows.md#audio-file-analysis).

## Configuration

Set variables in the **MCP client's server environment**. A value set only in a
terminal may not reach a desktop client. Restart the connector after changes.

| Variable | Default | Purpose |
| --- | --- | --- |
| `QLAB_HOST` | `127.0.0.1` | QLab host address. |
| `QLAB_OSC_PORT` | `53000` | QLab workspace OSC port. |
| `QLAB_REPLY_PORT` | `53001` | Reply-port configuration; see transport note below. |
| `QLAB_TIMEOUT` | `2.0` | Seconds per OSC transaction/native script. |
| `QLAB_CACHE_TTL` | `10.0` | Safe-read cache lifetime in seconds. |
| `QLAB_PASSCODE` | Not set | Workspace passcode; required for existing-workspace writes. |
| `QLAB_ENABLE_WRITE` | `false` | Enable gated write operations. |
| `QLAB_WRITE_DRY_RUN_DEFAULT` | `true` | Preview writes unless explicitly requested otherwise. |
| `QLAB_UPDATE_DEBUG` | `false` | Add Edit diagnostics; does not bypass safeguards. |

**Transport:** normal requests use TCP when a passcode is configured. Otherwise,
UDP uses isolated ephemeral reply ports; `QLAB_REPLY_PORT` does not designate a
persistent listener in that path. Some read paths have a separate TCP fallback.
`QLAB_TIMEOUT` is separate from client startup and overall tool-call timeouts.

### Enabling writes

Set `QLAB_ENABLE_WRITE=true` and `QLAB_PASSCODE`, grant Edit access in QLab,
and keep the workspace in Edit Mode. Leave the dry-run default enabled.
Before a real existing-workspace change, the agent must:

1. Resolve exact workspace and target UUIDs.
2. Check `qlab_check_write_readiness`.
3. Request `dry_run=true` and review the plan, changes and warnings.
4. Submit the returned fresh confirmation token(s), execute once and read back.

Batches are sequential and non-atomic. Do not retry an uncertain mutation;
there is no automatic rollback. Keep Audition disabled. Document Open uses a
separate empty-inventory preflight; Save includes all unsaved edits, and Close
refuses dirty documents. See [write workflows](docs/user/agent-workflows.md#common-write-gate).

File search, analysis and assignment require conversational consent for the
needed files. The server cannot verify that consent; OS permissions still apply.
Technical profiles and document inventories can expose paths or show content.
See [security and privacy](SECURITY.md).

## Tool Groups

Expand a category to see its tools. Each tool appears once below. Exact
parameters, capability gates and examples are in the [full tool catalogue](docs/user/tools.md)
and [agent workflows](docs/user/agent-workflows.md). Cue-family inventories are
scoped to one Cue List and include nested Groups; all edits below configure
saved state and do not execute cues.

<details>
<summary><strong>Workspace and discovery</strong> — 6 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_check_connection` | Check QLab access, open workspaces and permissions. |
| `qlab_check_write_readiness` | Check whether existing-workspace writes are available. |
| `qlab_get_workspace_overview` | Map cue lists, Groups and cue structure. |
| `qlab_get_workspace_status` | Summarize cue health, routing problems and timecode. |
| `qlab_query_cues` | Find cues by type, name, state or other filters. |
| `qlab_get_cue_details` | Inspect generic health, targets and editing capabilities. |

</details>

<details>
<summary><strong>Cue Lists, Carts and structure</strong> — 9 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_cue_lists` | List root Cue Lists and Carts. |
| `qlab_get_cue_list_details` | Read one list and its bounded cue tree. |
| `qlab_get_cue_cart_details` | Read one Cart and its occupied cells. |
| `qlab_create_cue_lists` | Create empty root Cue Lists or Carts. |
| `qlab_edit_cue_lists` | Edit list/Cart properties and incoming timecode settings. |
| `qlab_move_cue_lists` | Reorder root Cue Lists and Carts. |
| `qlab_create_cues` | Create 1–100 template-backed cues. |
| `qlab_move_cues` | Move existing cues between supported List/Group positions. |
| `qlab_delete_cues` | Delete leaves or Group contents; root List/Cart deletion is blocked. |

</details>

<details>
<summary><strong>Audio and Mic cues</strong> — 6 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_audio_cues` | List Audio cues within one Cue List. |
| `qlab_get_audio_cue_details` | Read Audio timing, media, levels and slices. |
| `qlab_edit_audio_cues` | Edit Audio properties, media, timing and supported levels/slices. |
| `qlab_get_mic_cues` | List Mic cues within one Cue List. |
| `qlab_get_mic_cue_details` | Read Mic patches, channels, timing and levels. |
| `qlab_edit_mic_cues` | Edit Mic properties, routing and supported levels. |

</details>

<details>
<summary><strong>Video, Camera and Text cues</strong> — 9 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_video_cues` | List Video cues within one Cue List. |
| `qlab_get_video_cue_details` | Read Video media, geometry, timing, audio and selected FX. |
| `qlab_edit_video_cues` | Edit Video properties, media, geometry and supported FX. |
| `qlab_get_camera_cues` | List Camera cues within one Cue List. |
| `qlab_get_camera_cue_details` | Read Camera inputs, geometry, audio and selected FX. |
| `qlab_edit_camera_cues` | Edit Camera properties, routing, geometry and supported FX. |
| `qlab_get_text_cues` | List Text cues within one Cue List. |
| `qlab_get_text_cue_details` | Read Text content, formatting, geometry and selected FX. |
| `qlab_edit_text_cues` | Edit Text content, readable formatting, geometry and supported FX. |

</details>

<details>
<summary><strong>Light and Group cues</strong> — 6 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_light_cues` | List Light cues within one Cue List. |
| `qlab_get_light_cue_details` | Read saved Light commands and cue settings. |
| `qlab_edit_light_cues` | Edit supported Light commands and cue settings. |
| `qlab_get_group_cues` | List Groups within one Cue List. |
| `qlab_get_group_cue_details` | Read Group mode, Playlist settings and bounded children. |
| `qlab_edit_group_cues` | Edit Group properties, mode and supported Playlist settings. |

</details>

<details>
<summary><strong>Control, Target, Devamp and Fade cues</strong> — 8 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_control_cues` | List control cues, including Target, Devamp, Wait and Memo. |
| `qlab_get_control_cue_details` | Read control settings, targets, Load Time and assigned number. |
| `qlab_edit_control_cues` | Edit mixed control cues, including saved Load Time. |
| `qlab_edit_target_cues` | Configure Target cues and their assigned cue number. |
| `qlab_edit_devamp_cues` | Configure Devamp targets and saved behavior. |
| `qlab_get_fade_cues` | List Fade cues within one Cue List. |
| `qlab_get_fade_cue_details` | Read Fade targets and supported level/geometry settings. |
| `qlab_edit_fade_cues` | Configure compatible Fade targets, parameters and flags. |

</details>

<details>
<summary><strong>MIDI and Timecode cues</strong> — 7 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_midi_cues` | List MIDI and MIDI File cues, with optional type filtering. |
| `qlab_get_midi_cue_details` | Read MIDI message settings or MIDI File settings. |
| `qlab_edit_midi_cues` | Configure supported saved MIDI messages. |
| `qlab_edit_midi_file_cues` | Assign MIDI files and edit supported timing/patch settings. |
| `qlab_get_timecode_cues` | List Timecode cues within one Cue List. |
| `qlab_get_timecode_cue_details` | Read MTC/LTC configuration and patch references. |
| `qlab_edit_timecode_cues` | Configure saved Timecode values and supported outputs. |

</details>

<details>
<summary><strong>Network and Script cues</strong> — 6 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_network_cues` | List Network cues within one Cue List. |
| `qlab_get_network_cue_details` | Read Network patches, messages and fade configuration. |
| `qlab_edit_network_cues` | Edit saved Network messages and supported settings. |
| `qlab_get_script_cues` | List Script cues within one Cue List. |
| `qlab_get_script_cue_details` | Read Script settings; technical mode includes source. |
| `qlab_edit_script_cues` | Edit Script Basics and supported triggers; never compile or run. |

</details>

<details>
<summary><strong>Workspace settings</strong> — 15 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_workspace_general_settings` | Read minimum GO time and selection/playhead lock. |
| `qlab_get_workspace_audio_settings` | Read Audio patches and an optional selected matrix level. |
| `qlab_get_workspace_video_settings` | List Video inputs, stages and output routes. |
| `qlab_get_workspace_light_settings` | Read current OSC data plus saved local patch addresses, outputs, groups and workspace definitions; large results expose follow-up pages. |
| `qlab_edit_light_patch` | Preview or apply a batch to the saved local Light Patch; close, replace and reopen the same workspace. |
| `qlab_get_light_definitions` | Browse bundled, personal and saved-workspace definitions; filter the catalogue or select exact channel/virtual-control detail. |
| `qlab_edit_light_definitions` | Import, create, update, rename or delete workspace definitions with preview and confirmation; global libraries remain unchanged. |
| `qlab_get_workspace_midi_settings` | Read MIDI patches or one exact patch. |
| `qlab_get_workspace_network_settings` | Read Network patches or one exact patch. |
| `qlab_get_video_stage` | Read one stage and its regions. |
| `qlab_get_video_output_route` | Read one output route and its destination. |
| `qlab_get_video_region` | Read one region and an optional control point. |
| `qlab_edit_workspace_general_settings` | Edit minimum GO time or selection/playhead lock. |
| `qlab_edit_audio_output_patch` | Edit patch name, cue outputs, levels or mute/solo settings. |
| `qlab_edit_video_stage` | Rename an existing stage. |
| `qlab_edit_video_output_route` | Change an output route’s guide visibility. |
| `qlab_edit_video_region` | Edit supported region geometry, grid, guide or control point. |

</details>

<details>
<summary><strong>Media, fonts and effect metadata</strong> — 4 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_search_media_files` | Find local files by filename after file-access consent. |
| `qlab_analyze_audio_file` | Measure audio levels, bands and estimated beats; no playback. |
| `qlab_get_fonts` | List QLab application font names and families/styles. |
| `qlab_get_video_effect_catalogue` | Browse documented Video FX metadata in pages of up to 10. |

</details>

<details>
<summary><strong>Local workspace documents</strong> — 4 tools</summary>

| Tool | What it does |
| --- | --- |
| `qlab_get_workspace_document` | Read document state and the full local workspace inventory. |
| `qlab_open_workspace` | Open an existing document only when no workspace is open. |
| `qlab_save_workspace` | Save all pending edits to an existing document path. |
| `qlab_close_workspace` | Close an inactive document only when it has no unsaved edits. |

</details>

## Read Model

Start with connection and a bounded overview. Find the relevant cues, then use
the matching family detail tool. Read only the settings needed for those cues.
Check pagination, truncation, errors and unavailable fields before claiming a
complete review. A structural index is not full health or output validation.

## Documentation

| Need | Guide |
| --- | --- |
| Install or fix a connection | [Setup and troubleshooting](docs/user/setup-and-troubleshooting.md) |
| Choose tools and follow write procedures | [Agent workflows](docs/user/agent-workflows.md) |
| Review and organize a workspace | [Workspace authoring](docs/user/workspace-authoring.md) |
| Inspect exact tool scope | [Public tool catalogue](docs/user/tools.md) |
| Check supported and pending work | [Current state](docs/status/current-state.md) · [Roadmap](docs/status/roadmap.md) |
| Understand safeguards | [Security policy](SECURITY.md) |
| Contribute or inspect internals | [Contributing](CONTRIBUTING.md) · [Architecture](docs/development/architecture.md) |
| Browse all documentation | [Documentation index](docs/README.md) |

The repository includes an optional
[workspace-authoring skill](.agents/skills/qlab-workspace-authoring/SKILL.md)
for agents that discover project skills. It guides use of the existing tools;
it adds no permissions or capabilities and is not installed by the Python package.

## License

Original code and authored documentation: [MIT](LICENSE), copyright 2026 MarcheKEN.
Imported QLab/QClass references and other third-party material have separate
terms; see [NOTICE](NOTICE).
