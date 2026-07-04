# QLab-MCP Documentation

## References

Base documents used to design and verify QLab OSC coverage.

- `references/qlab_osc_dictionary.md`
- `references/osc_queries.md`
- `references/video_phase1_osc_matrix.md`

## QClass Transcripts

Official QClass 5.5 class transcripts. These are reference material for QLab behavior, usage patterns, and recommended workflows.

- `qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`
- `qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`
- `qclass/September 2025 QClass 5.5 at the Voxel - Day 3.md`

## Prompts

The `prompts/` folder contains reusable Codex prompts for planned implementation steps.

These prompts are not source code and are not part of the runtime MCP behavior. They are execution instructions for agents. Each prompt should be numbered and focused on one concrete task.

Recommended usage:

1. Read `docs/README.md` first.
2. Read the relevant files in `docs/current/`.
3. Execute the next numbered prompt from `prompts/`.
4. Run the tests requested by the prompt.
5. Stop before any MCP runtime validation that requires a manual MCP restart.

Current convention:

- `001_...` small fixes or cleanup.
- `002_...` documentation/status updates.
- `003_...` planning for the next phase.
- `004_...` local implementation work.
- `005_...` runtime validation after manual MCP restart.

Prompts may reference docs and workorders, but the docs remain the source of truth for phase status and safety rules.

## Current Development Docs

Documents that still guide current implementation work.

- `current/active_roadmap.md`
- `current/workorders/002_close_phase3a_docs.md`
- `current/workorders/003_plan_phase3b_translation.md`
- `current/workorders/004_implement_phase3c_visual_scalars.md`
- `current/workorders/005_implement_phase3d_visual_appearance.md`
- `current/workorders/006_implement_phase3e_text_basics.md`
- `current/workorders/007_text_style_and_video_fx_read_plan.md`
- `current/workorders/008_video_fx_real_write_candidate.md`
- `current/workorders/009_video_completion_matrix.md`
- `current/workorders/010_video_docs_consistency_cleanup.md`
- `current/workorders/011_video_fx_scalar_v2_candidate.md`
- `current/workorders/012_geometry_completion_video_camera_text.md`
- `current/workorders/013_full_geometry_completion_video_camera_text.md`
- `current/workorders/014_rotation_quaternion_shutter_geometry.md`
- `current/workorders/015_quaternion_geometry_write.md`
- `current/workorders/016_safe_reset_rotation.md`
- `current/workorders/017_geometry_completion_smooth_and_defaults.md`
- `current/workorders/018_blend_mode_audit_and_completion.md`
- `current/workorders/019_video_io_selection_edit_cues.md`
- `current/workorders/020_video_embedded_audio_research.md`
- `current/workorders/021_video_audio_time_loops.md`
- `current/workorders/022_slice_markers_audio_video.md`
- `current/video_phase3a_opacity_real_write_plan.md`
- `current/video_phase2c_gate_test_vectors.md`
- `current/qlab_update_cues_runtime_checklist.md`
- `current/updateq_osc_coverage_snapshot.md`

## Archive

Historical plans and runtime reports. These are kept for traceability but should not be treated as the active implementation plan.

### Video

- `archive/video/video_phase2_updateq_edit_plan.md`

### Light

- `archive/light/light_read_model_plan.md`
- `archive/light/light_update_dry_run_plan.md`
- `archive/light/light_write_phase4_plan.md`
- `archive/light/light_write_phase5_plan.md`

### Runtime probes

- `archive/runtime_probes/cue_detail_read_coverage_probe_report.md`
- `archive/runtime_probes/runtime_concurrency_probe_report.md`
- `archive/runtime_probes/runtime_tool_probe_report.md`
