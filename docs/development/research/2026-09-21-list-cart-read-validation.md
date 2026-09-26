# Combined List/Cart reads — 2026-09-21

## Contract and sources

`qlab_get_cue_lists` returns all sidebar lists and carts using only the shallow
inventory and current-container reads. Entries retain their OSC type (`Cue List`,
`Cue Cart`, or `Cart`) and canonical UUID. Counts distinguish lists, carts and
total containers. The legacy excluded-cart count is zero.

`qlab_get_cue_list_details` and `qlab_get_cue_cart_details` share exact selection,
workspace resolution, identity checks, state/timecode reads, partial errors,
redaction and deadlines. List details return bounded nested contents and
playhead aliases. Cart details return grid dimensions and occupied cells with
positions read from each exact child. Cart contents metadata does not duplicate
the cell collection. Technical profiles include notes and the allowlisted payload.

Official sources:

- [Cue Carts](https://qlab.app/docs/v5/fundamentals/cue-carts/): grid semantics,
  no playhead, no Group children, Basics/Triggers/Grid Size inspector.
- [OSC Dictionary](../../references/qlab_osc_dictionary.md): workspace
  `cueLists/shallow`, `currentCueListID`, cue `valuesForKeys`, `children/shallow`,
  `cartRows`, `cartColumns`, `cartPosition`, common identity/state, and
  Group/List/Cart timecode messages.

Coverage is the documented container read surface, not an arbitrary dump of
every child cue Inspector. Sync activation and MTC/LTC source selection remain
explicit OSC limitations. Timecode components/text are representations of the
same clock or trigger, not separate settings. Notes are omitted in safe reads;
key-based redaction does not remove secrets embedded in free text.

## Runtime evidence

QLab 5.5.10; fresh in-process FastMCP client loading this checkout, existing QLab
connection configuration, writes disabled. No GO, cue setters or save. The
desktop MCP had been restarted before the validation; the script still loads
the checkout directly so the observed code and schemas are unambiguous.

| Workspace UUID | Lists | Carts | Inventory |
| --- | ---: | ---: | --- |
| `2BE85FBF-91A8-49AE-9617-C58B3332BF92` | 5 | 0 | ok |
| `95F0A03D-140E-4673-974A-E76748EBB023` | 17 | 1 | ok |
| `03D261B1-9D06-42F4-8F6A-B52E30B6821D` | 4 | 0 | ok |
| `A192C068-0974-4624-90BD-56D68BF0286B` | 8 | 0 | ok |

One exact List per workspace passed safe and technical detail reads, with a
30-descendant bound. Truncation was reported separately and was expected.
Incoming clock values were unavailable; timecode configuration was readable.

Cart `9820BBAE-2DA6-4C3B-B933-24F9354EEFD6` in workspace
`95F0A03D-140E-4673-974A-E76748EBB023` returned OSC type `Cart`, dimensions 4×4,
and one Memo `FAA47041-E720-42B1-B09E-BD221D0675EE` at OSC position `[1, 1]`.
Both profiles returned `ok`, no errors, and a complete grid.

## Computer Use comparison

QLab's visible sidebar confirmed the same four inventories without mutation:

- Memoria: `311 cues in 5 lists`.
- mcp_prueba: `241 cues in 18 lists and carts`; its sidebar showed `17 Lists and
  1 Cart`. Opening `Cue cart vacia` showed a 4×4 grid with one Memo in the
  first cell, matching the OSC cart detail.
- Practica_Show_Completo: `137 cues in 4 lists`.
- MATADERO: `1802 cues in 8 lists`.

The UI counts and the OSC list/cart counts agree. The UI additionally exposes
presentation details (for example cue numbers and inspector labels) that these
container tools intentionally do not claim to replicate.

The first runtime pass exposed an incorrect numeric assumption for
`timecodeTrigger`; QLab returns an object with hours/minutes/seconds/frames/bits.
The final model uses strict typed components, with malformed-payload regression
tests. This is runtime shape evidence supplementing the dictionary's description.

## Synthetic coverage

Mixed/empty inventories, current Cart, UUID/type/identity mismatch, strict
limits, bounded contents, invalid dimensions/coordinates, duplicate positions,
secondary timeout without retry, technical-only notes, timecode validation,
FastMCP input/output schemas and exact public inventory (23 tools).

Final full suite: `2831 passed, 39 subtests passed` using
`PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider`.
`git diff --check` passed.
