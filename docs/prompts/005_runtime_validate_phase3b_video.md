# Prompt 005 — Runtime Validate Video Phase 3B Translation, Video-only

Use high reasoning. Work objectively, carefully, and in a strict safety loop.

Use only QLab MCP tools.

Do not edit code.
Do not run pytest.
Do not use terminal.
Do not commit.
Do not modify docs.
Do not use raw OSC.

This is a **runtime validation prompt** after a manual MCP restart.

## 0. Context

Video Phase 3B has been implemented locally.

Local tests passed before this runtime validation:

* Focused: `1411 passed`
* Full: `1633 passed, 37 subtests passed`

Implemented behavior:

* Real-write gate for Video `translation/x`
* Real-write gate for Video `translation/y`
* Video-only for this phase
* Token prefix: `confirm:videoTranslation:v1:`
* Saved mode only
* UUID cue_ref only
* Exactly one cue
* Exactly one property
* Fresh baseline/hash before setter
* Exactly one setter
* Numeric readback verification
* Rollback requires new dry-run and new token
* Setter timeout + matching readback is accepted as `status="updated"` with warning `setter_timeout_but_readback_matched`

Phase 3A opacity is already closed for Video, Camera, and Text. Do not retest Phase 3A unless needed as a small regression check.

## 1. Main goal

Validate that Phase 3B works in QLab runtime for **Video cues only**:

```text
translation/x
translation/y
```

The required runtime flow is:

```text
baseline → dry-run/token → real write → readback → rollback dry-run/new token → rollback real write → final baseline
```

You must validate `translation/x` and `translation/y` separately.

Do not test Camera/Text real writes as success paths. Camera/Text translation must remain blocked / dry-run-only.

## 2. Safety scope

Use only the test workspace:

```text
mcp_prueba
```

Prefer explicit workspace UUID:

```text
95F0A03D-140E-4673-974A-E76748EBB023
```

Use cue list:

```text
MCP_VIDEO_WRITE_FIXTURE
```

This workspace contains multiple Video, Camera, Text, Fade, Stop and broken visual cues intended for MCP testing.

## 3. Hard prohibitions

Do not use:

* GO
* playback
* start
* stop
* load
* audition
* panic
* preview
* `/live`
* Dashboard
* raw OSC
* Workspace Video writes
* Video FX
* fileTarget
* camera patch
* video input patch
* stage changes
* stage assignment
* route changes
* region changes
* rotation
* quaternion
* rotate
* resetRotation
* scale real writes
* crop real writes
* anchor real writes
* text real writes
* text formatting writes
* font writes
* Camera real writes
* Text real writes
* batch real writes
* multi-property real writes
* create/delete/move/rename cues

If any tool response suggests a prohibited operation is about to happen, stop immediately and report.

## 4. Required safety checks before any real write

Before any `dry_run=false` call:

1. Confirm QLab is reachable.
2. Confirm the selected workspace is `mcp_prueba`.
3. Confirm workspace UUID is `95F0A03D-140E-4673-974A-E76748EBB023`.
4. Confirm QLab version if reported.
5. Confirm Edit Mode if reported.
6. Confirm running cues count is `0` if available.
7. Confirm paused cues count is `0` if available.
8. Confirm auditioning cues count is `0` if available.
9. Confirm selected cue is a healthy Video cue:

   * `type="Video"`
   * `isBroken=false`
   * `isWarning=false`
   * `isRunning=false`
   * `isPaused=false`
   * `isAuditioning=false`
10. Confirm the planned operation is saved mode, not `/live`.
11. Confirm the planned operation address is workspace/cue UUID-qualified.

## 5. Suggested target cue

Prefer the known healthy Video cue:

```text
v4 Video2
```

Known UUID from previous validations:

```text
1EE5940A-858B-4F63-BE6A-2CA3D2B8C7F2
```

If this cue is unavailable or unhealthy, select another healthy Video cue from `MCP_VIDEO_WRITE_FIXTURE`, but report why.

Do not use a show cue. Do not use a broken cue for the success path.

## 6. Baseline capture

Read and save a baseline for the selected Video cue before any write.

Capture at least:

* workspace name
* workspace UUID
* cue list name
* cue uniqueID
* cue number
* cue name
* cue type
* armed
* isBroken
* isWarning
* isRunning
* isPaused
* isAuditioning
* opacity
* translation/x
* translation/y
* scale/x
* scale/y
* anchor/x if exposed
* anchor/y if exposed
* cropTop
* cropBottom
* cropLeft
* cropRight
* blendMode
* clockType
* stage/stageID/stageName/stageNumber if exposed
* file target presence if exposed, but do not modify it
* videoEffects summary if exposed, but do not modify it

If some fields are not exposed by the available profile, report that they were unavailable. Do not invent them.

The most important baseline fields are:

```text
translation/x
translation/y
opacity
scale/x
scale/y
crop values
blendMode
clockType
```

## 7. Choosing test values

Use small reversible changes only.

For `translation/x`:

```text
requested_x = baseline_x + 10
```

For `translation/y`:

```text
requested_y = baseline_y + 10
```

If `+10` would be risky or unreasonable, use `+1`.

Do not use a large offset. Do not intentionally move the image far off stage.

If baseline is not numeric, stop and report.

Requested values must be finite numbers:

* no NaN
* no Infinity
* no -Infinity

## 8. Validate `translation/x`

### 8.1 Dry-run for translation/x

Call `qlab_update_cues` with:

* `workspace_id = 95F0A03D-140E-4673-974A-E76748EBB023`
* `dry_run=true`
* one update item only
* `cue_ref = exact selected Video cue UUID`
* `profile = "video_basic"`
* property/path = `translation/x`
* requested value = `requested_x`
* mode = `saved`
* `confirm_gates=[]`

Confirm all of the following:

* response is successful
* status is dry-run/planned
* `confirm_token` is present
* token prefix is exactly:

```text
confirm:videoTranslation:v1:
```

* `real_write_possible=true`
* `requires_confirm_token=true`
* `executed_operations=[]`
* no setter executed
* no QLab value changed yet
* planned operation is exactly one setter candidate
* planned operation path/address targets:

```text
/workspace/{workspace_id}/cue_id/{cue_id}/translation/x
```

* planned operation does not contain `/live`
* planned operation does not mention scale/crop/anchor/rotation/stage/Video FX/fileTarget/text
* if `updateq_plan` is present:

  * it should indicate planned/gated write
  * `will_modify_qlab=false`
  * `no_executed_operations=true`

After dry-run, reread the cue or relevant value and confirm `translation/x` still equals the original baseline.

### 8.2 Real write for translation/x

Only proceed if the dry-run is perfect.

Call `qlab_update_cues` with:

* `dry_run=false`
* same workspace UUID
* same cue UUID
* same profile
* same property/path `translation/x`
* same requested value
* mode `saved`
* exactly one confirm gate: the token from the dry-run

Confirm all of the following:

* status is `updated`
* exactly one setter was executed
* setter path/address is workspace/cue UUID-qualified
* setter path ends in `/translation/x`
* setter path does not contain `/live`
* no other setter was executed
* `executed_operations` contains only the expected `translation/x` operation
* `real_write_enabled=true` where exposed
* `real_write_possible=true` where exposed
* `requires_confirm_token=true` where exposed
* `planned_only_reason` is absent or null for the successful real write
* if `updateq_plan` is present:

  * `status="updated"`
  * `safety.no_executed_operations=false`
  * `safety.will_modify_qlab=true`
  * no prohibited safety flags are violated

Readback:

* readback value for `translation/x` must match `requested_x`
* numeric tolerance:

  * abs `1e-5`
  * rel `1e-6`

Timeout handling:

If the setter times out but readback matches requested value:

* accept as success
* status should still be `updated`
* warning should include:

```text
setter_timeout_but_readback_matched
```

If setter timeout occurs and readback is missing or mismatched:

* report uncertain failure
* do not retry the setter
* proceed only to safety readback; do not continue with more writes

### 8.3 Post-write check for translation/x

After the real write, reread the cue.

Confirm:

* `translation/x = requested_x`
* `translation/y` unchanged
* opacity unchanged
* scale/x unchanged
* scale/y unchanged
* crop values unchanged
* blendMode unchanged
* clockType unchanged
* cue name unchanged
* cue number unchanged
* cue type unchanged
* cue is not running
* cue is not paused
* cue is not auditioning

### 8.4 Rollback translation/x

Rollback must use a new dry-run and a new token.

Call `qlab_update_cues` with:

* `dry_run=true`
* property/path = `translation/x`
* requested value = original baseline_x
* same cue UUID
* same profile
* mode saved
* empty confirm_gates

Confirm:

* new `confirm:videoTranslation:v1:` token appears
* token is not the same logical operation as the forward token
* dry-run executes no operations

Then call real write:

* `dry_run=false`
* same rollback requested value
* confirm_gates = [rollback token]

Confirm:

* status `updated`
* exactly one setter
* readback equals original baseline_x
* no mutating retry
* no `/live`

After rollback, reread the cue and confirm `translation/x` is exactly back to initial baseline within numeric tolerance.

## 9. Validate `translation/y`

Repeat the same flow for `translation/y`.

### 9.1 Dry-run translation/y

* dry_run=true
* cue UUID exact
* profile video_basic
* property/path `translation/y`
* requested value `requested_y`
* mode saved
* confirm_gates=[]

Confirm:

* token present
* prefix `confirm:videoTranslation:v1:`
* real_write_possible=true
* requires_confirm_token=true
* executed_operations=[]
* planned address ends in `/translation/y`
* no `/live`

### 9.2 Real write translation/y

* dry_run=false
* same cue
* same requested value
* confirm_gates=[token]

Confirm:

* status updated
* exactly one setter
* setter ends in `/translation/y`
* no `/live`
* readback matches requested_y
* timeout+matched behavior accepted with warning

### 9.3 Rollback translation/y

* new dry-run to original baseline_y
* new token
* real write
* readback equals original baseline_y

Final after rollback:

* translation/x equals original baseline_x
* translation/y equals original baseline_y

## 10. Rejection probes

Run these only after both axes have been rolled back successfully.

Each rejection must:

* fail before any setter
* have `executed_operations=[]`
* leave QLab unchanged
* not use `/live`
* not start playback

### 10.1 Fake token

Attempt `translation/x` real write on the Video cue with a fake token.

Expected:

* rejected
* no setter
* `executed_operations=[]`

### 10.2 Cue number instead of UUID

Attempt `translation/x` using cue number instead of UUID.

Expected:

* rejected
* UUID required
* no setter

### 10.3 Camera translation real write attempt

Pick a healthy Camera cue.

Attempt real write for:

```text
translation/x
```

with `profile="camera_basic"`.

Expected:

* rejected or remains Phase 2 dry-run-only
* no Phase 3B token can authorize Camera
* no setter
* `executed_operations=[]`

### 10.4 Text translation real write attempt

Pick a healthy Text cue.

Attempt real write for:

```text
translation/x
```

with `profile="text_basic"`.

Expected:

* rejected or remains Phase 2 dry-run-only
* no Phase 3B token can authorize Text
* no setter
* `executed_operations=[]`

### 10.5 Video scale still blocked

Attempt Video real write:

```text
scale/x
```

Expected:

* rejected
* no setter
* `executed_operations=[]`

### 10.6 Video crop still blocked

Attempt Video real write for one crop property, for example:

```text
cropTop
```

Expected:

* rejected
* no setter
* `executed_operations=[]`

### 10.7 `/live` blocked

Attempt live mode or `/live` operation for translation.

Expected:

* rejected before setter
* no `/live` setter
* no mutation

### 10.8 Batch blocked

Attempt two update items in one real-write request.

Expected:

* rejected
* no setters

### 10.9 Second property blocked

Attempt one item with both:

```text
translation/x
translation/y
```

Expected:

* rejected
* no setters

### 10.10 Broken Video cue blocked

If a broken Video cue exists in the fixture, attempt `translation/x`.

Expected:

* rejected due broken/unhealthy cue
* no setter

If no broken Video cue is available, report skipped.

### 10.11 Stale token behavior

If safe and practical:

1. Dry-run `translation/x` to get token A.
2. Do not execute token A.
3. Perform a separate dry-run/token write only if needed to alter baseline, then rollback.
4. Try token A after baseline changed.

Expected:

* stale baseline rejected
* no setter

If this would require extra unnecessary writes, skip and report that stale baseline is covered by unit tests.

## 11. Final full baseline check

At the end, reread the success-path Video cue.

Confirm:

* `translation/x` equals initial baseline
* `translation/y` equals initial baseline
* opacity equals initial baseline
* scale/x equals initial baseline
* scale/y equals initial baseline
* crop values equal initial baseline
* blendMode equals initial baseline
* clockType equals initial baseline
* name equals initial baseline
* number equals initial baseline
* type equals initial baseline
* not running
* not paused
* not auditioning

Also confirm workspace activity:

* running count 0
* paused count 0
* auditioning count 0 if available

## 12. Report format

Return a clear report with these sections:

A. Workspace and QLab version
B. Selected Video cue and initial baseline
C. `translation/x` dry-run result
D. `translation/x` real write result
E. `translation/x` rollback result
F. `translation/y` dry-run result
G. `translation/y` real write result
H. `translation/y` rollback result
I. Rejection probes result
J. Final baseline intact: yes/no
K. Safety confirmation
L. Bugs/deviations
M. Recommendation: close Phase 3B for Video or fix something

## 13. Acceptance criteria

Phase 3B Video runtime validation passes only if:

* both axes dry-run with token
* both axes execute exactly one setter
* both axes read back correctly
* both axes roll back with new token
* final baseline equals initial baseline
* all rejection probes block before setter
* no `/live`
* no playback
* no unrelated writes
* Camera/Text remain blocked for real translation writes

If any acceptance criterion fails, do not call Phase 3B closed. Report what failed.
