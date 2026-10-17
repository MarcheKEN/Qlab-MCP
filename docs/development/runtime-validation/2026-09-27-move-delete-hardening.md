# Move/Delete hardening — 2026-09-27

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Evidence boundary

Implemented on `codex/cue-editing-tools`. Local verification: **3106 tests and
47 subtests passed** with `.venv/bin/python -m pytest -q`; `git diff --check`
passed. The sandbox-only run could not bind the simulated transport servers
(`PermissionError: [Errno 1] Operation not permitted`); the successful full run
used permission for local sockets. Live fixture results after the MCP restart
are recorded below.

A fresh in-process FastMCP Client still lists **48 tools**, with the additive
Delete argument and Move/Delete progress arrays in the public schemas. Tests
call public tools using simulated readers and also capture protocol errors.
The earlier [live matrix](2026-09-27-move-delete-cues.md) predates this update;
it does not validate the new implementation against the installed MCP.

## Changes and regression coverage

- Move checks complete affected source/destination orders before every step,
  during convergence, and in a final audit. Nested container orders under moved
  Groups are included, and reviewed Group contents are bound to the token.
  No-op setters remain skipped while structure is verified. Tests cover correct
  target placement with incorrect sibling/source/subtree structure, successful
  cross-parent and populated Group moves, stale Group tokens and final drift.
- Both executors retain confirmed results/counts on intermediate or final read
  failure. `pending_cue_ids` identifies setters not sent; `uncertain_cue_ids`
  identifies attempted operations without confirmed outcomes. Final audit
  errors do not append a duplicate cue result. Failure injection covers activity
  and structure reads before, between and after setters, plus Delete readback.
  Existing delayed convergence, timeout confirmation and 50-item tests remain.
- Delete defaults to preserving recursive roots. `delete_container=true` needs
  an exact Group, `recursive=true`, and omitted `cue_ids`. Descendants precede
  the root; failures stop the batch. Fresh pre-setter reads reject newly populated
  Groups and changed parent orders. New mode is capped at 500 total deletes;
  root-preserving mode retains 500 descendants. Tests cover empty/nested Groups,
  descendant failure, concurrent child insertion, mode-bound tokens, invalid
  combinations and boundaries. Cue List/Cue Cart root deletion stays blocked.

`failed_count` retains its existing meaning: unconfirmed operations, including
pending ones. All earlier operations may be confirmed even when the final audit
fails. Readback is observational; OSC batches are not atomic. Process/client
interruption can still prevent delivery of any final response. Never retry an
ambiguous operation automatically.

## Reproducing and recording calls

Run the local regression tests:

```sh
.venv/bin/python -m pytest -q tests/test_write_mode.py tests/test_delete_mode.py tests/test_server_tools.py -k 'move or delete'
git diff --check
```

`scripts/capture_move_delete.py` captures a single reviewed call through a
FastMCP client, including raw protocol `content`, `structuredContent`, `isError`,
metadata, transport exceptions and elapsed time. It does not retry, generate
fixtures, or obtain/execute tokens automatically. Tokens and known sensitive
fields are redacted in both structured and JSON text content. Keep raw request
files private; returned names and UUIDs remain for verification.

```sh
PYTHONPATH=src .venv/bin/python scripts/capture_move_delete.py /private/tmp/mcp-config.json /private/tmp/plan-evidence.json < /private/tmp/reviewed-plan-request.json
```

The MCP configuration must identify the intended server; no automatic server
selection occurs. Requests contain `tool` and `arguments`. Default execution
requires `dry_run=true`; a real call additionally requires `--execute`, explicit
`dry_run=false`, and the exact reviewed `confirm_token`. Existing evidence files
are never overwritten. Use one process/session for the dry-run and real call
when using stdio: tokens are tied to the server process. The CLI's independent
stdio invocations are suitable for dry-runs; real confirmation requires a
persistent server connection or `capture_call` within one Client session.

## Installed MCP and Computer Use acceptance — 2026-09-27

The restarted installed MCP exposed **48 tools**, including `delete_container`
on `qlab_delete_cues`. Write readiness was `ready` for W1, W2, and W3. QLab
5.5.10 was served by `<redacted-local-path-2e4542d9aa>.app`; Computer Use was
bound to that instance. A second `/Applications/QLab.app` instance could not
listen on the OSC ports and was not used for visual evidence.

- **W1** (`8E86FE91-668B-560C-B738-4D581B5A7498`): recorded source/destination
  child UUID arrays, created Group `8773E25D-E54F-530C-A629-16C653BE2D5C`
  with Memos `B21B5BE2-01BF-53C3-8C0B-D05D91983C3C` and
  `6015D86A-BCF7-5787-8CA6-970ED5A77797`, verified a same-parent no-op, moved
  the populated Group to another parent and back, and read back both parent
  orders plus its child UUIDs. The default recursive delete removed the two
  Memos and preserved the empty Group; direct empty-Group deletion then removed
  that root. A second populated fixture (`7B1F87F6-06CE-52E3-9E62-C170E4EA1209`,
  Memos `78474B24-E415-58B8-9810-1EBD4BAFE70C` and
  `9284AB73-1B1D-572A-AC89-3EC6373CC3D5`) planned children before root. Executing
  its token with `delete_container=false` returned `preflight_failed`,
  `deleted_count=0`, both children pending, and no uncertain IDs; no OSC mutation
  was sent. A fresh token with `delete_container=true` confirmed all three
  deletions. A separate empty Group (`CD36D5A4-F4F0-56F2-AC19-7616BFEEEE77`)
  was removed as one operation with the new mode. Final source and destination
  arrays exactly matched their recorded baselines.
- **W2** (`C2ADCE41-17C1-5610-BBA3-F43D0F46162A`): moved populated Group
  `C9CDC515-FE26-5AC9-BECE-238B924C4384` (Memo
  `CA099E30-E98C-575A-9230-CB944E91C972`) from the 13-cue source list to the
  2-cue destination. Readback preserved the Memo under the Group. Opt-in deletion
  confirmed both IDs removed. Both original direct-child arrays and order were
  restored exactly.
- **W3** (`9D9FDE61-4388-5E9D-B5E2-D28840C882DD`): moved populated Group
  `FB419577-5FBE-59A3-B108-7E667F7D7984` (Memo
  `09B25355-7B8B-504E-B72A-E6153A859659`) from the 2-cue `Scripts` list into
  the 27-child `Pruebas intro` list and back. Structural readbacks confirmed
  parent, index, child UUID, and complete direct-child orders. Opt-in deletion
  confirmed both fixture IDs removed; both lists exactly matched their original
  arrays. The separate Cue List `6C0C90FD-0699-5B49-B503-A47C5A1AA93D` was not
  written; its large contents were not fully re-audited in this turn.

Computer Use in W1 visually showed the temporary Group with its two Memo
children, then the cross-parent state via source/destination child counts. The
final screen showed only original Memo cue 104 in `Cue list vacia`, 7 original
children in `MCP_GROUP_WRITE_FIXTURE`, and **241 cues in 18 lists and carts**.
W2 and W3 were verified through installed MCP structural readback, not Computer
Use. Failure injection, 500-item boundaries, and blocked root List/Cart deletion
were verified by local tests rather than by inducing failures or large batches
in live workspaces. No GO, playback, Save, Panic, root List/Cart deletion, or
automatic retry/rollback was used. Confirmation tokens are not recorded here.

## Later Move batch checks

For `qlab_move_cues`, an installed-MCP batch with duplicate source UUIDs and a
50-move batch whose anchors referred to other moved cues both returned
`preflight_failed`; neither sent OSC or moved cues. A 50-item batch using
destination indices then passed verification, but the items were already in
those positions, so it exercised the batch limit and readback rather than 50
actual changes. Local validation also rejects `destination_parent_id` values
that refer to another cue in the same batch. Same-batch dependent moves remain
unsupported; use an unaffected anchor or separate reviewed calls.
