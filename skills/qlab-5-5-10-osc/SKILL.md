---
name: qlab-5-5-10-osc
description: "Exact navigation of the QLab 5 OSC Dictionary for addresses, arguments, types, view/edit/control/query permissions, replies, update notifications, workspace prefixes, selected cues, /live, and +/-; use it for any QLab 5.5.10 OSC question and never invent a missing path."
---

# QLab 5.5.10 OSC Dictionary

Use the supplied dictionary to locate and cite exact syntax. The content is technical: preserve slashes, capitalization, property names, argument order, `live`, `+`, `-`, wildcards, and JSON.

## Sources

- Official source: [QLab's OSC Dictionary](https://reference.qlab.app/docs/v5/scripting/osc-dictionary-v5/).
- Repository copy: [`docs/references/qlab_osc_dictionary.md`](../../docs/references/qlab_osc_dictionary.md).
- Portable copy of this skill: [`references/qlab_osc_dictionary.md`](references/qlab_osc_dictionary.md).
- Provenance: [`references/source-manifest.json`](references/source-manifest.json).

The official page is authoritative. The repository manifest identifies the imported copy as `QLab 5; exact patch unknown`; therefore, the skill name must not hide that patch uncertainty. For claims specifically new in 5.5.10, check the official page and change log.

## Deterministic search

1. Search for the literal first (`rg -n '^### /cue/.*/preWait|/preWait' references/qlab_osc_dictionary.md`).
2. Confirm the syntax line, the `view | edit | control | query | +/-? | Live` table, description, and examples.
3. Distinguish action, read, write, query, reply, and notification.
4. Check the target: `cue_number`, `cue_id`, `selected`, playhead, wildcard, or `/workspace/{id}`.
5. If there is no entry, respond literally: `Not found in the supplied QLab OSC Dictionary.` Do not generate a path by analogy.

## Critical rules

- `Live` always goes at the end: `/cue/x/opacity/+/live`, not `/cue/x/opacity/live/+`.
- `+/-` accepts argument form and, starting with QLab 5.5, a form included in the address when the entry permits it.
- `/selected` and a cue number are not equivalent to a unique cue ID.
- Messages without a workspace prefix may reach every workspace listening on that port; use the exact UUID when isolation matters.
- Reply and update are not the same: replies answer a message; `/update/...` notifies requested changes.
- Check permissions and passcode before any write. This skill does not authorize sending OSC or making a runtime connection.

## Intent index

| Intent | Reference |
|---|---|
| transport, updates, replies, booleans, live, +/- | [Navigation](chapters/navigation.md) |
| application, workspace, cue, Group, Audio, Video, Camera, Text, Light, Fade, Network, MIDI, Timecode, Script | exact copy of the [Dictionary](references/qlab_osc_dictionary.md) |
| auditable samples | [Samples](chapters/samples.md) |
| general QLab concepts | [qlab-5-5-10-reference](../qlab-5-5-10-reference/SKILL.md) |
