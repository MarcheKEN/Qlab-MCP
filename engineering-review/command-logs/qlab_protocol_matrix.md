# QLab protocol matrix command log

```text
sed -n '1,240p' /Users/filarmonica/.codex/skills/qlab-docs-assistant/SKILL.md
rg -n -i "OSC Dictionary|QLab 5\.5|address-embedded|multiple workspaces|deprecated" /Users/filarmonica/.codex/memories/MEMORY.md
sed -n '1,240p' /Users/filarmonica/.codex/skills/qlab-docs-assistant/references/official-source-map.md
sed -n '1,280p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt
wc -l /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt
sed -n '281,760p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt
nl -ba /Users/filarmonica/.codex/memories/MEMORY.md | sed -n '232,370p'
sed -n '761,980p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt
rg --files docs/references src tests | rg 'qlab_osc_dictionary|osc_queries|transport|workspace|cue|osc|query|write|server|allowlist|models|config'
wc -l docs/references/qlab_osc_dictionary.md docs/references/osc_queries.md src/qlab_mcp/osc/addressing.py src/qlab_mcp/osc/messages.py src/qlab_mcp/osc/client.py src/qlab_mcp/settings/workspace.py src/qlab_mcp/cues/refs.py src/qlab_mcp/cues/query.py src/qlab_mcp/allowlist.py src/qlab_mcp/write/osc_inventory.py
rg -n '(/workspace|/cue|/live|\+|-|update|reply|connect|disconnect|workspace|selected|playhead|uniqueID|uniqueId|toggle|boolean|bool|enum|deprecated|5\.5)' src/qlab_mcp/osc src/qlab_mcp/settings src/qlab_mcp/cues src/qlab_mcp/write src/qlab_mcp/allowlist.py src/qlab_mcp/server.py
nl -ba src/qlab_mcp/osc/addressing.py
nl -ba src/qlab_mcp/osc/messages.py
nl -ba src/qlab_mcp/osc/client.py | sed -n '1,360p'
nl -ba src/qlab_mcp/cues/refs.py | sed -n '1,390p'
rg -n '^class QLabReader|def (check_connection|get_workspaces|get_cue_lists|get_selected|get_running|get_cue_values|get_cue_children|_request|_cached_request|_resolve_workspace|_workspace)' src/qlab_mcp
nl -ba src/qlab_mcp/qlab.py | sed -n '1,390p'
nl -ba src/qlab_mcp/runtime/connection.py | sed -n '1,470p'
nl -ba src/qlab_mcp/runtime/connection.py | sed -n '470,700p'
nl -ba docs/references/osc_queries.md
rg -n '^#{1,4} ' docs/references/qlab_osc_dictionary.md
nl -ba docs/references/qlab_osc_dictionary.md | sed -n '1,220p'
rg -n '^(/|```text$)|/workspaces|/version|/updates|/udpReplyPort|/connect|/workspace/\{|deprecated|Deprecated|replaced|cue_id|cueList|selected|playhead|playbackPosition|active' docs/references/qlab_osc_dictionary.md
rg -n 'Cue Messages|Cue messages|cue messages|Cue OSC|The following OSC messages pertain to cues|cue_number|cue_id prefix|cue_id' docs/references/qlab_osc_dictionary.md | sed -n '1,180p'
nl -ba docs/references/qlab_osc_dictionary.md | sed -n '2730,2775p'
nl -ba docs/references/qlab_osc_dictionary.md | sed -n '550,770p'
rg -n '"live"|/live|relative|increment|decrement|address_embedded|address-embedded|embedded|delta|\+/' src/qlab_mcp tests/test_write_mode.py tests/test_osc.py
nl -ba tests/test_write_mode.py | sed -n '4660,4845p'
nl -ba tests/test_write_mode.py | sed -n '5060,5145p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '5500,5685p'
rg -n '"[^"\n]*/[+-](?:/|\")|f"[^"\n]*/[+-](?:/|\")|/[+-]/' src/qlab_mcp tests || true
nl -ba src/qlab_mcp/write/registry.py | sed -n '1860,2010p'
nl -ba src/qlab_mcp/write/registry.py | sed -n '1,520p'
rg -n '^def _validate|VALID_|_VALUES|continue_mode|group_mode|target_mode|second_trigger_action|color_condition|clock_type|fade_type|geo_mode|levels_mode|rotation_type|timecode' src/qlab_mcp/write/registry.py | sed -n '1,260p'
nl -ba src/qlab_mcp/write/registry.py | sed -n '2025,2265p'; nl -ba src/qlab_mcp/write/registry.py | sed -n '2390,2475p'
nl -ba docs/references/qlab_osc_dictionary.md | sed -n '2950,3015p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '3430,3468p'
nl -ba src/qlab_mcp/write/registry.py | sed -n '1315,1375p'; rg -n 'customString|rawString|query|#/' src/qlab_mcp/write/operations.py src/qlab_mcp/write/registry.py src/qlab_mcp/allowlist.py src/qlab_mcp/server.py tests/test_write_mode.py | sed -n '1,220p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '5960,6185p'
rg -n '^def valid_osc_message_text|valid_osc_message_text' src/qlab_mcp/write; nl -ba src/qlab_mcp/write/network_patch_types.py | sed -n '1,200p'
rg -n '(/updates|/update/|alwaysReply|udpReplyPort|forgetMeNot|udpKeepAlive|disconnect)' src/qlab_mcp tests
nl -ba tests/test_osc.py | sed -n '1,340p'
nl -ba src/qlab_mcp/write/deletes.py | sed -n '150,245p'; rg -n 'alwaysReply' src/qlab_mcp/write/deletes.py tests/test_delete_mode.py
rg -n 'deprecated|Deprecated' src/qlab_mcp | sed -n '1,240p'
nl -ba src/qlab_mcp/write/registry.py | sed -n '1515,1585p'; nl -ba src/qlab_mcp/write/osc_inventory.py | sed -n '1,290p'
rg --files tests | rg 'registry|coverage|inventory'; nl -ba tests/test_update_registry_coverage.py | sed -n '1,360p'
rg -n 'pathSmooth|pathLoop' docs/references/qlab_osc_dictionary.md src/qlab_mcp tests || true
rg -n '_resolve_workspace_id_strict|_resolve_workspace_strict|_cue_address\(|_workspace_address\(' src/qlab_mcp/cues src/qlab_mcp/settings src/qlab_mcp/status.py src/qlab_mcp/write | sed -n '1,320p'
nl -ba src/qlab_mcp/cues/details.py | sed -n '1,190p'
nl -ba src/qlab_mcp/cues/query.py | sed -n '1,470p'
nl -ba src/qlab_mcp/cues/details.py | sed -n '330,470p'; rg -n 'selected|playhead|playbackPosition|active|_is_active_cue_ref' src/qlab_mcp/cues/details.py src/qlab_mcp/cues/profiles.py src/qlab_mcp/models.py src/qlab_mcp/server.py | sed -n '1,240p'
nl -ba src/qlab_mcp/cues/details.py | sed -n '200,335p'; nl -ba src/qlab_mcp/models.py | sed -n '385,420p'
rg -n '^def _is_exact_cue_uuid|UUID' src/qlab_mcp/write/operations.py src/qlab_mcp/write/deletes.py src/qlab_mcp/write/moves.py; nl -ba src/qlab_mcp/write/operations.py | sed -n '320,370p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '2935,2955p'; nl -ba src/qlab_mcp/write/deletes.py | sed -n '1,70p'; nl -ba src/qlab_mcp/write/moves.py | sed -n '700,730p'
rg -n 'toggle' src/qlab_mcp/write src/qlab_mcp/models.py src/qlab_mcp/server.py src/qlab_mcp/allowlist.py
nl -ba src/qlab_mcp/write/registry.py | sed -n '2280,2345p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '3498,3530p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '5658,5695p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '6310,6338p'
nl -ba src/qlab_mcp/write/registry.py | sed -n '1265,1315p'; nl -ba src/qlab_mcp/write/registry.py | sed -n '1395,1470p'
.venv/bin/python -c 'from qlab_mcp.write.registry import profile_catalog; c=profile_catalog(); print("live specs:"); [print(p,n,s["real_write_enabled"],s["planned_only_reason"]) for p,v in c.items() for n,s in v["properties"].items() if "live" in s["modes"]]; print("profiles",len(c))'
env PYTHONPATH=src .venv/bin/python -c 'from qlab_mcp.write.registry import profile_catalog; c=profile_catalog(); print("live specs:"); [print(p,n,s["real_write_enabled"],s["planned_only_reason"]) for p,v in c.items() for n,s in v["properties"].items() if "live" in s["modes"]]; print("profiles",len(c))'
rg -n 'secondColorName.*live|live.*secondColorName' tests src docs/current
rg -n 'secondColorName|colorName/live' src/qlab_mcp/allowlist.py src/qlab_mcp/cues/profiles.py tests/test_write_mode.py docs/references/qlab_osc_dictionary.md | sed -n '1,180p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '11755,11845p'; rg -n 'mode.*live|/live' src/qlab_mcp/write/operations.py | sed -n '1,180p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '11840,11920p'
rg -n 'client\.request\(.*\*|request\(operation|executed_operations|setter' src/qlab_mcp/write/operations.py | sed -n '1,260p'
nl -ba src/qlab_mcp/write/operations.py | sed -n '2390,2540p'
nl -ba src/qlab_mcp/config.py | sed -n '1,230p'; nl -ba tests/test_osc.py | sed -n '90,145p'
nl -ba src/qlab_mcp/allowlist.py | sed -n '520,565p'; nl -ba src/qlab_mcp/allowlist.py | sed -n '1,45p'; nl -ba src/qlab_mcp/cues/profiles.py | sed -n '1,40p'
nl -ba src/qlab_mcp/allowlist.py | sed -n '480,540p'
nl -ba src/qlab_mcp/write/osc_inventory.py | sed -n '285,390p'; rg -n '^def profile_catalog|registry_status|real_write_possible' src/qlab_mcp/write/registry.py src/qlab_mcp/write/osc_inventory.py
rg -n '^@mcp\.tool|^def qlab_' src/qlab_mcp/server.py
.venv/bin/pytest tests/test_osc.py tests/test_update_registry_coverage.py -q
git status --short
```
