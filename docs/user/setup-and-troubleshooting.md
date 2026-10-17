# Setup and troubleshooting

## Install and start

The package requires Python 3.11 or newer. The CI baseline is Python 3.11;
macOS and a running QLab 5 instance are required for local AppleScript features.
OSC inspection can target the configured QLab host. From the repository root:

```bash
uv sync --locked --no-editable --python 3.11 --extra dev
.venv/bin/python -m qlab_mcp.server
```

This starts the stdio MCP server. Configure the MCP client to launch the absolute
path of this Python interpreter with arguments `-m`, `qlab_mcp.server`. The
non-editable installation contains a snapshot: repeat the sync after source
changes. For a deliberate source checkout launch, set `PYTHONPATH` to its
absolute `src` directory and keep that setting consistent with the checkout.
Never infer which source a running connector loaded from the folder visible
in an editor; restart the process after changing its command or environment.

Inspect definitions without connecting to QLab:

```bash
uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env
```

Expect 79 tools, including 49 reads and 30 gated writes. Definitions alone do
not establish QLab reachability. Use `qlab_check_connection` for live read access,
resolve one returned workspace UUID, then request a bounded overview.

## Process environment

[README configuration](../../README.md#configuration) lists the nine `QLAB_*`
settings and defaults. The client must pass them to the MCP process; values in
an interactive shell do not prove the desktop client inherited them. Keep
passcodes in client/environment configuration, never in tool requests or logs.
Changes require a process restart. Invalid boolean literals fail configuration;
numeric parsing is not a promise of complete range validation.

Three limits serve different purposes:

- **Client startup timeout:** time allowed to launch Python and complete MCP
  initialization. The client owns this setting.
- **Tool call timeout:** the public tool’s overall budget. Connection checks
  use 6 seconds, native document calls 30, family edits 180 and creation/audio
  analysis 300; inspect the tool metadata for each specific call.
- **`QLAB_TIMEOUT`:** individual OSC transactions and native script invocations;
  default 2 seconds. Increasing startup time does not change this limit.

Without a passcode, normal OSC requests announce an isolated ephemeral UDP reply
port. With a passcode, normal requests use a reader-scoped TCP/SLIP session.
`QLAB_REPLY_PORT` is therefore not a promise of one persistent UDP listener.
Selected read paths can use a separate TCP fallback. Network/firewall settings
must match the actual configured host and transport.

## Enabled connector but missing tools

An enabled entry records configuration; it does not prove initialization finished.
Read the client’s startup log and locate the decisive error before changing
QLab settings. Common checks:

1. Confirm the configured interpreter exists and imports `qlab_mcp` and FastMCP.
2. Confirm the absolute command, checkout and `PYTHONPATH` agree. A moved virtual
   environment can retain launchers pointing to its old interpreter; recreate
   or resync the environment at its intended location.
3. Confirm source and installed packages are actually downloaded. Cloud-managed
   folders can contain placeholders; keep the working source downloaded and
   place the runtime/cache outside cloud-managed storage when necessary.
4. Distinguish slow imports from OSC timeouts. Adjust the client startup limit
   only after fixing missing files or imports; a longer timeout cannot repair
   unavailable package contents.
5. Restart/reload the connector and inspect the catalogue again. Then test
   `qlab_check_connection`; do not test availability by executing a cue.

If catalogue discovery succeeds but QLab reads fail, inspect the configured
host/ports, workspace candidates, passcode result and `/connect` scopes. Multiple
workspaces need an explicit choice. Write readiness is separate from read access.

## Native document and Trigger failures

The fixed local bridge requires exactly one running `/Applications/QLab.app`,
a loopback host and Automation permission for the actual MCP host process.
It does not launch QLab or provide a remote fallback. Keep unavailable native
fields unknown; OSC data can still be useful. Open has its own empty-inventory
preflight; Save/Close and existing-cue edits require their documented readiness.
After an uncertain native event, inspect fresh state and never resend blindly.
See [document lifecycle](agent-workflows.md#workspace-documents) and
[native Triggers](agent-workflows.md#native-cue-triggers).

## Optional audio

```bash
uv sync --locked --no-editable --python 3.11 --extra audio --extra dev
.venv/bin/python -c 'import librosa, numpy, shutil; assert shutil.which("ffmpeg") and shutil.which("ffprobe")'
```

FFmpeg and ffprobe must be in the MCP process PATH, not merely available in a
separate terminal. The server never installs them on first use. Missing optional
backends produce dependency errors or skipped integration tests; base test
success does not validate audio measurements. Obtain or reuse scoped file-access
consent before search, inspection or assignment. Analysis never plays the file.
