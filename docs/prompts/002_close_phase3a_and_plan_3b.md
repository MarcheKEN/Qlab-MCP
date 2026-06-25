Use $caveman full + Ponytail.

Task: close Video Phase 3A in docs and create the plan for Video Phase 3B.

Context:
The small Phase 3A wording fix is assumed done.
Video Phase 3A opacity real write has been runtime-validated for:

* Video
* Camera
* Text

Confirmed Phase 3A behavior:

* dry-run emits `confirm:videoOpacity:v1`
* real write executes exactly one saved `/opacity` setter
* readback confirms requested opacity
* setter timeout + matching readback is treated as `status="updated"` with warning `setter_timeout_but_readback_matched`
* rollback requires a new dry-run/token
* final baseline restored
* no playback, no GO, no `/live`, no Dashboard, no raw OSC
* no Workspace Video writes, Video FX, fileTarget, camera patch, stage, rotation, translation/scale/crop/text/font real writes

Do not implement Phase 3B yet in this task.
This is a docs/planning task only.

Tasks:

1. Update docs/current/active_roadmap.md
   Mark closed:

* Video Phase 1
* Video Phase 1D
* Video Phase 2A
* Video Phase 2B
* Video Phase 2C
* Video Phase 3A opacity real write for Video/Camera/Text

Set next:

* Video Phase 3B translation real write

2. Create docs/current/workorders/002_close_phase3a_docs.md
   Include:

* Phase 3A final status: closed
* Video opacity runtime result summary
* Camera opacity runtime result summary
* Text opacity runtime result summary
* safety confirmation
* known accepted deviation: QLab setter timeout but readback matches
* note that this is accepted as success with warning

3. Create docs/current/workorders/003_plan_phase3b_translation.md
   Scope:

* Phase 3B should enable real writes only for:

  * `translation/x`
  * `translation/y`
* First implementation target: Video cues only
* Later extension: Camera/Text only after Video runtime validation
* profile initially: `video_basic`
* mode: saved only
* cue_ref: UUID only
* exactly one cue
* exactly one property
* finite numeric values only
* token required
* baseline hash required
* fresh read before setter
* readback numeric tolerance same as Phase 3A
* rollback requires new dry-run/token

Block:

* `scale/x`, `scale/y`
* crop
* anchor
* rotation/quaternion/rotate/resetRotation
* stage/stageID/stageName/stageNumber
* Video FX
* fileTarget
* camera patch/video input patch
* Text `text` and text formatting
* `/live`
* playback/GO/Dashboard/raw OSC
* Workspace Video writes
* batch/multi-property writes

Token:
Use a new prefix, do not reuse opacity token:
`confirm:videoTranslation:v1:`

Payload should include:

* version
* operation_kind = `video_phase3b_translation_write`
* workspace_id
* cue_id
* cue_ref
* cue_type
* profile
* property/path: `translation/x` or `translation/y`
* mode=saved
* baseline
* baseline_sha256
* requested
* risk_tier=high
* capability_gate=video_visual
* mcp_secret_version

Acceptance:

* dry-run produces token only for valid Video translation/x or translation/y candidate
* non-translation video properties remain unchanged
* real write executes exactly one setter
* readback matches requested value
* timeout + matching readback succeeds with warning
* mismatch/missing readback fails uncertain; no retry
* rollback with new token restores baseline

Runtime validation handoff:

* human must restart MCP before runtime validation
* start with one healthy Video cue only
* use test workspace `mcp_prueba`
* no playback/live/unrelated writes
* do not test Camera/Text until Video passes

4. Do not change code except docs.
5. Run no QLab runtime.
6. If there are markdown lint/tests available, run them; otherwise report docs-only.

Return:
A. Files created/updated
B. Phase 3A status summary
C. Phase 3B scope summary
D. What the next implementation prompt should be
