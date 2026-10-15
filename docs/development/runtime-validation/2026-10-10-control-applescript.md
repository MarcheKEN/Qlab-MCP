# Fixed local AppleScript Control fields

Date: 2026-10-10. QLab 5.5.10, one running `/Applications/QLab.app` instance,
one authorized test workspace, Edit Mode and zero active cues. Workspace path,
UUID and fixture identities were checked privately. Private paths, cue names,
UUIDs and confirmation tokens are omitted from this report.

## Implemented contract

Two existing editors gain saved properties; no new tool is registered:

- `qlab_edit_control_cues`: Load `loadTime`, finite signed seconds. Negative
  values count back from the target's end; this is configuration, not `/loadAt`.
- `qlab_edit_target_cues`: Target `assignedNumber`, a unique existing workspace
  cue number or empty text to clear. This configures a future Target action;
  it does not change the Target cue's own number or its receiver's current target.
- `qlab_get_control_cue_details`: typed `load` or `assignment` sections, explicit
  AppleScript transport and edit capabilities. Successful combined reads report
  `coverage.source="documented_osc_and_applescript"`. Failed native reads retain
  OSC details, report the error and block the affected native property.

The fixed script receives JSON arguments, never user-provided AppleScript or
shell input. It requires local macOS, one already-running QLab at the exact app
path, existing write/Edit access configuration and macOS Automation permission.
It neither launches QLab nor bypasses permission failures. Other installations
and remote OSC hosts are blocked for these two fields.

The existing 1–50 cue executor supplies whole-batch preflight, signed five-minute
single-use tokens, reservation, fresh identity/dependencies and one setter per
operation. Tokens bind the tool, workspace, cue/type, previous/requested values
and target dependencies. Missing, null or invalid target evidence blocks preflight.
Target changes and renumbering dependencies require separate calls and fresh
dry runs. A failure proven before sending records no setter; uncertain failures
and timeouts trigger fresh readback, never a resend or automatic rollback.
OSC operations still prepare `/alwaysReply` in the setter connection; native
operations use their script's identity, activity and baseline checks.

Sources: installed `QLab.sdef` Load and Target classes, the repository's
[AppleScript reference](../../references/qlab_applescript_dictionary.md),
[official dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/),
[Load semantics](https://qlab.app/docs/v5/other-cues/transport-cues/) and
[Target semantics](https://reference.qlab.app/docs/v5/other-cues/target-cues/).
Documentation identified the capabilities; the following tests establish the
observed behavior in this QLab version.

## Runtime writes and inspector contrast

Tests used the updated source MCP through `Client(mcp)`. Every write followed
baseline → dry run with zero executed operations → fresh token → one setter →
fresh detail read → Computer Use inspection → restoration with a new token.
Computer Use only navigated and inspected; it performed no edits.

| Case | Observed changes and restoration |
| --- | --- |
| Load signed time | `0 → 1.25 → -2.5 → 0` seconds. Inspector showed `00:01.250`, `-00:02.500`, then `00:00.000`; fresh native reads agreed. |
| Target without receiver | Empty assigned number → an existing Memo number → empty. Saved values were readable; the disarmed placeholder remained broken because it had no receiver. |
| Target with receiver | Set an existing eligible Pause receiver through OSC; assign and clear the existing Memo number through AppleScript; clear the receiver through OSC. UI and fresh reads agreed, and the configured Target became healthy before restoration. |
| Invalid assigned number | Dry run rejected a nonexistent number, with zero executed operations. |
| Wrong cue type | Dry run rejected `loadTime` on Wait, with zero executed operations. |

There were **seven native setters and two OSC setters**, including restoration.
Each returned `updated` with one executed operation and matching fresh readback.
The receiver's own target and the Target cue's own number were unchanged.
Final reads confirmed Load `0`, Target assigned number empty and receiver empty;
both test cues remained disarmed and inactive. Returning these placeholders to
their original broken state is expected, not a playback certification.
The initial selected cue and Basics tab were restored after inspection.
Restoration covers property values; it does not restore the document's undo
history or claim an unchanged saved file/modified flag. No Save was requested.

## Automated verification and review

- Focused native bridge, Control reads/writes and public schemas: **286 passed**.
- Full suite: **1745 passed, 35 skipped, 61 subtests passed**. Local UDP/TCP tests
  ran outside the filesystem sandbox because it denies socket binding; the
  earlier sandbox permission error was not classified as a code failure.
- Public `Client(mcp).list_tools()`: **74 tools**, generic editor absent; only
  the two input property schemas and Control detail output were extended.
- Tests cover stale/expired/reused tokens, whole-batch rejection, mixed pending
  operations, native preparation/timeout errors, strict values, JSON argument
  injection, remote/write-disabled guards, assigned-number dependencies and
  unknown target evidence. Existing OSC UDP/TCP confirmation regressions pass.
- A fresh review identified missing target evidence being treated as empty.
  Regressions reproduced it, strict preflight rejection fixed it, and follow-up
  review reported no further actionable findings. Pre-launch validation and
  expired deadlines now consistently use the preparation-failure classification.
- Final source-MCP reads after the last changes confirmed restored values,
  nonpartial combined coverage and inactive/disarmed fixtures.
- Documentation links and `git diff --check` pass. No new dependencies, package
  version change or release; unrelated checkout changes were preserved.

## Connected MCP recheck after restart

The user restarted the MCP. Its live connection reported QLab 5.5.10, the exact
authorized workspace, Edit Mode, confirmed Edit access and a readable workspace.
The registered `qlab_edit_control_cues`, `qlab_edit_target_cues` and detail tool
then passed these additional runtime checks:

- Load `0 → 1.25 → 0` and `0 → -2.5 → 0`; MCP and inspector matched, including
  the negative display `-00:02.500`.
- A one-use token completed `0 → 0.75 → 0`; replaying it after restoration was
  rejected with zero setters. A token planned at baseline `0` was also rejected
  after another edit changed the baseline; the cue was restored to `0`.
- Target assigned number `"" → "140" → ""` matched the Cue Number inspector.
  Its own number stayed `161`, and its target receiver stayed empty.
- A healthy Pause receiver was temporarily assigned to the disarmed Target cue,
  which invalidated a pending assigned-number token. The stale token was rejected
  with zero setters, and the receiver was cleared using a new token. An initial
  attempt with a broken Pause placeholder was blocked at preflight with no setter.
- Boolean Load Time, numeric assigned number, nonexistent assigned number,
  Load Time on Wait, a forged token and a mixed valid/invalid batch were rejected
  before mutation. The mixed batch and token failures reported zero executed
  operations.

This post-restart pass used ten native setters and two OSC setters, all with
fresh dry runs, single-use tokens and fresh readback. Final MCP reads showed Load
`0`, Target assigned number empty, Target receiver empty, both cues disarmed and
inactive. Computer Use confirmed the restored values and returned the UI to its
initial selected cue. No cue action or external signal occurred.

## Limits and next step

The restarted connected MCP now exposes and exercises the updated schemas and
backend. This verifies these two fields on QLab 5.5.10 only.
No GO, Preview, Send, signals, `/live`, Audio Maps, arbitrary script execution,
Script compilation or physical output was tested or enabled by this phase.
Broader AppleScript Triggers and document lifecycle remain future work. Trigger
activation needs a separate policy because incoming signals can start cues;
these two saved fields do not grant that capability.
