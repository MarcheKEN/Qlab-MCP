Use $caveman full + Ponytail.

Task: fix the minor **Video Phase 3A updateq_plan.intent wording bug**.

Context:
Video Phase 3A opacity real write has been runtime-validated for Video, Camera, and Text.

Confirmed behavior:

* dry-run emits `confirm:videoOpacity:v1`
* real write executes exactly one saved `/opacity` setter
* readback confirms requested opacity
* rollback uses a new dry-run/token and restores baseline
* no playback, no `/live`, no Dashboard, no raw OSC
* no Workspace Video writes
* no Video FX
* no fileTarget
* no camera patch
* no stage changes
* no rotation
* no translation/scale/crop/text/font real writes

Bug:
For Camera/Text opacity real writes, `updateq_plan.intent` still says something like:
`Executed saved opacity change on Video cue.`

Required fix:
Use the actual cue type in `updateq_plan.intent`:

* Video → `Executed saved opacity change on Video cue.`
* Camera → `Executed saved opacity change on Camera cue.`
* Text → `Executed saved opacity change on Text cue.`

Also check the dry-run planned intent. If it is hardcoded to `Video cue`, make it use the actual cue type too.

Do not change:

* token format
* token validation
* gates
* setter paths
* registry behavior
* write behavior
* Phase 3A safety rules
* Phase 2 non-opacity dry-run-only behavior
* Light/Audio/Fade behavior
* project layout

Expected files:

* likely `src/qlab_mcp/write/operations.py`
* likely `tests/test_write_mode.py`

Tests to add/adjust:

* Video opacity dry-run intent says Video
* Camera opacity dry-run intent says Camera
* Text opacity dry-run intent says Text
* Video opacity real-write intent says Video
* Camera opacity real-write intent says Camera
* Text opacity real-write intent says Text
* non-opacity Video/Camera/Text Phase 2 behavior unchanged

Run:
`.venv/bin/pytest -q tests/test_write_mode.py tests/test_update_registry_coverage.py`
`.venv/bin/pytest -q`

Return:
A. Root cause
B. Files changed
C. Tests run and result
D. Confirmation that only wording/reporting changed
E. Whether MCP restart is required
