Use $caveman full + Ponytail.

Task: implement Video Phase 3B — real write gate for translation/x and translation/y, Video cues only.

Context

The repo is clean and tests are green after the docs reorganization.

Current confirmed state:

Video Phase 3A opacity real write is closed for Video, Camera, and Text.
Phase 3A runtime validation passed:
dry-run emits confirm:videoOpacity:v1
real write executes exactly one saved /opacity setter
readback confirms requested value
rollback requires a new dry-run/token
no playback, no /live, no unrelated writes
Post-restart smoke validation passed:
QLab reachable
workspace mcp_prueba ready
Video/Camera/Text queries work
cue details and update capabilities load
dry-run translation/x succeeds and baseline remains unchanged

Now implement Phase 3B locally only.

Do not use QLab runtime tools in this pass. Do not run MCP tools. Do not do runtime validation.

Goal

Enable real writes only for:

translation/x
translation/y

Initial scope:

cue type: Video only
profile: video_basic
mode: saved
cue_ref: UUID only
exactly one cue
exactly one property
requested value: finite number
token required
fresh baseline required
readback verification required
rollback requires a new dry-run/token
Explicitly blocked

Do not enable:

Camera translation real writes
Text translation real writes
scale/x, scale/y
crop
anchor
rotation / quaternion / rotate / resetRotation
stage / stageID / stageName / stageNumber
Video FX
fileTarget
video input patch / camera patch
Text text or text formatting
/live
playback / GO / Dashboard / raw OSC
Workspace Video writes
batch writes
multi-property writes

Camera/Text may remain dry-run-only for translation/x and translation/y.

Token contract

Use a new token prefix:

confirm:videoTranslation:v1:

Do not reuse the opacity token.

Payload must include:

version = 1
operation_kind = "video_phase3b_translation_write"
workspace_id
cue_id
cue_ref
cue_type = "Video"
profile = "video_basic"
property = "translation/x" or "translation/y"
path = "translation/x" or "translation/y"
mode = "saved"
baseline
baseline_sha256
requested
risk_tier = "high"
capability_gate = "video_visual"
mcp_secret_version

Use the existing Phase 3A / Light HMAC pattern.

Dry-run behavior

For valid Video Phase 3B candidates:

dry_run=true
no setter sent
executed_operations=[]
confirm_token present
real_write_possible=true
requires_confirm_token=true
phase3b_video_translation_candidate=true
planned address must be workspace/cue UUID-qualified:
/workspace/{workspace_id}/cue_id/{cue_id}/translation/x
/workspace/{workspace_id}/cue_id/{cue_id}/translation/y

For non-eligible cases:

no token
real_write_possible=false
requires_confirm_token=false
no setter
existing Phase 2 dry-run-only behavior preserved
Real write behavior

Allow dry_run=false only when all gates pass:

exactly one update item
exactly one property
cue_ref is UUID
profile is video_basic
cue type is fresh-read Video
property/path is translation/x or translation/y
mode is saved
exactly one valid confirm token
requested value matches token
workspace/cue/profile/type/property/path/mode match token
fresh baseline matches token baseline and baseline hash
cue is not broken
cue is not warning
cue is not running
cue is not paused
cue is not auditioning

armed=false may remain notice-only, same as Phase 3A.

Execute exactly one setter:

/workspace/{workspace_id}/cue_id/{cue_id}/translation/x

or:

/workspace/{workspace_id}/cue_id/{cue_id}/translation/y

Then perform fresh readback.

Success only if readback matches requested value using the existing numeric tolerance:

abs = 1e-5
rel = 1e-6

Timeout policy:

setter timeout + readback matches → status="updated" with warning setter_timeout_but_readback_matched
setter timeout + readback missing/mismatch → uncertain failure, no retry
setter returns normally + readback mismatch → verification failure, no retry

No mutating retry.

Rollback

Rollback is not automatic.

Rollback requires:

New dry-run from current translation baseline.
New confirm:videoTranslation:v1: token.
One real setter.
Fresh readback.

Old forward token must not authorize rollback.

Files likely to touch

Likely:

src/qlab_mcp/write/operations.py
src/qlab_mcp/write/registry.py
tests/test_write_mode.py
maybe docs/current/workorders/003_plan_phase3b_translation.md if status needs a note

Avoid broad refactors.

Tests to add or adjust

Add focused tests for:

Dry-run/token
Video translation/x dry-run emits confirm:videoTranslation:v1
Video translation/y dry-run emits confirm:videoTranslation:v1
token payload contains required fields
planned operation address is UUID-qualified
executed_operations=[]
real_write_possible=true
requires_confirm_token=true
Scope blocks
Camera translation/x remains dry-run-only with no token
Text translation/x remains dry-run-only with no token
Video scale/x real write still rejected
Video crop real write still rejected
Video anchor real write still rejected
/live rejected
batch rejected
second property rejected
cue number rejected
Real write success
valid token allows exactly one translation/x setter
valid token allows exactly one translation/y setter
readback match returns status="updated"
timeout + matching readback returns status="updated" with warning
Token rejects before setter
fake token rejected
tampered token rejected
wrong workspace rejected
wrong cue rejected
wrong profile rejected
wrong cue type rejected
wrong property/path rejected
stale baseline rejected
requested mismatch rejected
broken cue rejected
warning cue rejected
running cue rejected
paused cue rejected
auditioning cue rejected
non-finite values rejected: NaN, Infinity, -Infinity
Rollback
old forward token cannot authorize rollback
rollback requires new dry-run/new token
Regression
Phase 3A opacity behavior unchanged
non-opacity Phase 2 Video/Camera/Text behavior unchanged
Light/Audio/Fade behavior unchanged
Commands

Run:

.venv/bin/pytest -q tests/test_write_mode.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
Return

Return:

A. Root cause / implementation approach
B. Files changed
C. Phase 3B behavior implemented
D. Tests added
E. Tests run and results
F. Confirmation that only Video translation/x|y real writes were enabled
G. Confirmation that Camera/Text translation remain dry-run-only
H. Whether MCP restart is required
I. Next action: runtime validation prompt after manual MCP restart