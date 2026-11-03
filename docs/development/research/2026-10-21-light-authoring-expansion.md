# Lighting authoring: evidence and remaining design gates

Research on QLab **5.5.10/build 5510**, 2026-10-21. This is not a claim of
complete lighting support. Dashboard, live operation and global-library writes
remain excluded. [Normalized native evidence](../runtime-validation/2026-10-21-light-authoring-research.json)
contains hashes and interpreted samples, not vendor libraries or workspace binaries.

## Lighting Command Language

Sources: [official command language](https://qlab.app/docs/v5/lighting/lighting-command-language/),
[patch editor](https://qlab.app/docs/v5/lighting/light-patch-editor/), local QClass
Day 3, 51:45–53:04 (`all`), 1:00:58–1:01:43 (ranges), and
2:34:50–2:39:24 (pulls/palettes). QClass examples are explanatory evidence;
native acceptance below is a separate observation.

| Feature | Evidence | MCP consequence |
| --- | --- | --- |
| Instrument/group, optional parameter | Manual; existing tools | Preserve names and command order; omitted parameter normally uses its default. |
| Numeric values, percentage/raw units | Manual; existing scalar definitions | Units belong to the definition. Scalar width can be 8 or 16 bits. |
| `home`, `pass` | Manual; existing parser | Do not treat home as synonymous with zero or pass as a level. |
| `all = home` | QClass; native command accepted | Expand analysis to every known parameter of every instrument, not only defaults. `all.red = home` affects red only. |
| Mixed group parameters | Manual | Instruments lacking the explicit parameter are ignored; unresolved instrument references remain incomplete. |
| Lists and ranges | Manual; native named numeric-suffix sample | Analyzer now accepts lists and ascending matching-prefix numeric ranges. Missing members block; arbitrary ordering is not inferred. |
| Bracketed ad-hoc groups | Manual; native sample | Analyzer accepts corresponding bracketed selectors; preserve brackets in saved text. |
| Pulls and proportional pulls | Manual; native sample | Preserve dynamic links; writer support also needs referenced cue identity/content bound to confirmation. |
| Compound virtual values | Inspector exposes compound controls | Text encoding and interpretation still require samples; do not invent `rgb(...)` syntax. |
| `thru`/`true` | Not confirmed as LCL tokens in consulted sources | Not enabled. OSC boolean syntax is a different language. |

### Native command sample

The exact following text was entered in cue 001 using the native Text view:

```text
all = home
Frontal 1 - Frontal 3 = 25
Frontal 4, Frontal 5 = 50
[LED 1 - LED 3].red = 20
[LED 4, LED 5].blue = 30
Frontales = cue 010
LED Todos.intensity = cue 010 * .5
Frontal 8 = pass
```

Fresh `qlab_get_light_cue_details` returned the identical text, `isBroken=false`
and `isWarning=false`. This validates native Text-view acceptance of this sample,
not every combination, OSC setter canonicalization, calculated output or playback.
The original six commands were restored with the public MCP editor, dry run,
fresh confirmation and successful readback.

Graphify confirmed the shared path from `remaining_context.validate` to
`analyze_light_command_text`; tests cover that analyzer separately. Extend this
shared path rather than adding a second parser in the public tool. Keep the
existing text interface. Pull support must resolve exact source cue identity,
snapshot its command/dependency graph, detect cycles and recheck the same state
before execution. A syntactically valid pull is not a predicted lighting look.

## Light cue curves

The official [Light cue manual](https://qlab.app/docs/v5/lighting/light-cues/)
documents four curve types. The installed OSC dictionary's Light section has no
curve setter. `fadeEntries` belongs to Fade cues and is not evidence of a Light
cue curve API. The reviewed AppleScript dictionary does not supply that setter.

The active saved cue-list archive is `workspace.cueLists.NS.data`, itself an
NSKeyedArchiver object table. Reachable Light cues contain:

```text
LightCue.fade.shapes : FadeShapesFunction
  upShape / downShape : FadeShape
    type, curveParameter, shapeEntries
      FadeShapeEntry: t, v, previous, next
  mirrorShape, domain, resolution
```

Native captures established these stored type values:

| UI choice | Stored type |
| --- | --- |
| Custom | 0 |
| S-Curve | 1 |
| Parametric | 2 |
| Linear | 3 |

Changing the parametric intensity to **2.5**, using the local decimal format
`2,500`, stored `curveParameter=2.5` in both shapes. Uncommitted text and a save
sent before a menu action finishes are not valid capture evidence. Read the UI
after applying a value, then save separately and inspect the saved file.

### Accepted file-write proof

1. In cue 021, create and move an interior Custom control point natively.
2. Save with explicit user authorization and retain recovery bytes.
3. Prepare a sample using `prepare_curve_point_sample` in
   `scripts/inspect_light_authoring.py`. It changes only that existing point's
   `v` to `0.8`, preserving UIDs, links, other curves and unrelated objects.
4. Dry-run and execute public MCP Close on the clean inactive exact workspace.
5. Verify source/output hashes, install the prepared bytes at the same path,
   then dry-run and execute public MCP Open.
6. QLab reopened cleanly with the same UUID. The native inspector displayed
   the modified ascending curve; the descending curve remained unchanged.

Decoded comparison confirmed exactly **one inner object / one field** changed.
After the experiment, native Reset restored the original curves. All seven
existing Light cue curve snapshots matched the saved baseline; the patch
snapshot was unchanged. No cues were executed and no physical output was tested.

### Proposed public contract, not registered

Use a separate `qlab_edit_light_cue_curves` tool, as chosen by the user. Its
eventual contract should take exact workspace/cue UUIDs, typed ascending and/or
descending curve changes, dry run and confirmation. Omitted sides must remain
unchanged. Reuse the document transaction and recovery guarantees, but add curve
postconditions; a successful patch readback alone cannot verify curves.

The proof validates editing an **existing interior ascending Custom point**.
It does not yet validate adding/deleting linked points, all type transitions,
descending edits, mirrored/shared shapes or every parametric boundary. Keep the
public tool unregistered until these encodings and the transaction's curve
verification have acceptance tests. No supported numeric range for the
parametric intensity is inferred from one sample.

## More complete definitions

The bundled library was read using the existing bounded LZ4/keyed-archive decoder:
**5,793 definitions**, of which **2,336** passed current import validation.
Parameter occurrences: scalar 102,290; RGB 10,547; Pan/Tilt 1,937; One-to-Many
1,201; CMY 789; HSI 452. These are parameter counts, not fixture counts.

Observed catalogue forms include:

| Native type | Output bindings | Current write status |
| --- | --- | --- |
| `scalar` | Physical channel, width, units, home | Validated subset enabled |
| `rgbcolor` | Named color outputs | Validated RGB/white/warmwhite/amber subset enabled |
| `pantilt` | Map: pan, tilt | Readable, blocked for import/creation |
| `cmycolor` | Map: cyan, magenta, yellow | Readable, blocked for import/creation |
| `hsicolor` | Map: hue, saturation, intensity | Readable, blocked for import/creation |
| `muxer` | List of parameter names, including virtual color names | Readable, blocked for import/creation |

Catalogue JSON is not proof of the corresponding workspace archive class or its
accepted graph encoding. Do not map every non-scalar type to the RGB class.
Next native samples must cover each class, shared bindings, nested virtual links,
default parameters and the `lime` color binding. Import preservation comes before
typed creation. Validate references and cycles; virtual parameters add no physical
DMX channels. Existing instrument footprints and overlaps must remain validated.

## Reproduce and checks

Read-only capture (the CLI never installs its offline prepared sample):

```bash
PYTHONPATH=src .venv/bin/python scripts/inspect_light_authoring.py /absolute/workspace.qlab5 --catalogue
PYTHONPATH=src .venv/bin/python -m pytest tests/test_light_authoring_research.py tests/test_light_command_analyzer.py -q
```

The probe deliberately labels archive objects as possible templates/residuals;
it does not present an object-table scan as an active cue inventory. It bounds
archives/points, avoids following cyclic point links and checks file stability.
Synthetic tests cover cyclic references, invalid archives, exact reachable cue
selection, narrow point edits, endpoint rejection and non-finite inputs.

Focused regression run: **400 passed** across analyzer, research probe, Light/Group
readers, remaining-family writes, definitions and server contract tests. FastMCP
inspection completed with **82 tools**; no curve tool was registered. The virtual
environment's CLI shebang still points to an older checkout path, so inspection
used `.venv/bin/python .venv/bin/fastmcp inspect fastmcp.json --skip-env` without
changing the environment.

## Follow-up — 2026-10-22

The proposed curve tool is now registered and its bounded native acceptance is
recorded in [lighting completion](../runtime-validation/2026-10-22-light-authoring-completion.md).
That report also covers typed CMY, HSI, Pan/Tilt, One-to-Many and RGB lime writes.
The earlier blocked statements and 82-tool count above describe the research
checkpoint, not the current public contract. No playback or physical DMX proof
was added by these authoring tests.
