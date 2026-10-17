# OSC Text/fonts and Video FX — 2026-10-09

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Scope and environment
## Post-restart installed-MCP confirmation — 2026-10-09

After the user restarted the connector, the installed MCP reported 74 tools
(47 reads/27 writes), including `qlab_get_fonts`; the retired generic editor
was absent. `qlab_check_connection` and `qlab_check_write_readiness` confirmed
the exact single workspace, QLab 5.5.10, Edit Mode and edit permission. Final
readbacks confirmed both fixtures restored and inactive; Computer Use showed
zero Active Cues.

Additional calls through the installed MCP connector:

- Fonts returned 529 names and 181 families/styles.
- Text range/word tests applied font size 67 to word index 2 in temporary ASCII
  text; the dry run resolved it to UTF-16 range `[8,5]`. A 25%/13% selection
  on the original 38-unit text resolved to `[0,5]`; the inspector showed only
  `Codex` blue. Both changes and the temporary content were restored. QLab UI
  showed the final original text uniformly white.
- A partial `fontFamilyAndStyle` edit using the already observed Helvetica Neue
  Bold tuple passed its production dry run, emitted `fontName=HelveticaNeue-Bold`
  for UTF-16 range `[0,5]`, and read back unchanged full companion metadata.
- A full-format restoration that included `alignment` was rejected in dry run
  because that JSON attribute is not validated. A full color edit across the
  original em dash was also blocked by the current non-Latin policy. Neither
  sent a setter; fresh range-only restoration returned the five changed
  characters to white, verified by fresh MCP read and UI. This confirms these
  are deliberate capability limits, not successful writes.
- EdgeWork radius changed 10 → 8 → 10; QLab UI showed both values. Intensity
  remained `2.6191787719726562` throughout.
- On the disarmed Text fixture, Gamma add, Exposure insert at 0, Gamma move
  from 1 to 0, Exposure delete and Gamma delete each used an individual signed
  dry run, one setter and fresh stack read. UI showed Gamma before Exposure
  with Gamma power 1; the final UI showed no effects.

No cues were executed. These checks validate the new public paths on the
restarted MCP; they do not expand Unicode, alignment, shadow or FX-default
support beyond the stated limits.


QLab 5.5.10, workspace `8E86FE91-668B-560C-B738-4D581B5A7498`, exact path
`<redacted-local-path-851cab375f>.qlab5`.
Edit Mode and Edit access were checked; no cues were running, paused or
executed. Fixtures: Text `1A325917-012D-5A98-97C3-968E623092EB`
(cue 147, disarmed), Video `CC889BBC-471F-5039-854E-5F61184B73D6`
(v11, inactive image). Computer Use only inspected/selected inspector tabs.

The new source was exercised through FastMCP `Client(mcp).call_tool`, not a
claim that the already-running connector loaded changed Python files. Source
catalogue: 74 tools (47 reads, 27 writes). Last installed observation: 73;
a user restart is needed. Version/package/release remain unchanged.

Each production change used baseline → signed dry run → one setter → fresh
full verification. Restoration used new dry runs/tokens. The companion
[JSON evidence](2026-10-09-osc-text-fonts-video-fx.json) omits tokens and records
setter addresses, arguments, native readbacks and restorations.

## Fonts and Text

- New `qlab_get_fonts` returned 529 exact PostScript names and 181 families
  via native `/fontNames` and `/fontFamiliesAndStyles` over TCP. Helvetica Neue
  exposed 14 styles. The inventories do not map each name to a family/style
  or establish glyph coverage.
- Latin `Á` selected by UTF-16 range changed size 72 → 67 → 72 without
  unexpected font metadata changes. Surrogate boundaries remain strict.
- Native scalar percentage experiments on the 19-unit text
  `uno dos tres cuatro` selected start/length 5/5, 6/5 and 10/5 for starts
  25%, 33% and 50% with length 25%. QLab rounds to nearest, including half-up
  at 9.5. Production resolves typed percentages to these integer UTF-16 ranges
  and emits one internally generated JSON setter.
- Native word indices 0–3 matched ranges 0/3, 4/3, 8/4 and 13/6. Production
  exposes word selection only for ASCII alphanumeric words separated by plain
  spaces. Other whitespace/punctuation/Unicode tokenization is blocked.
- To test partial fonts, complete Regular and Bold tuples were first observed
  through the same cue's global font setter/getter. An experimental fixture
  preparation used those observations to seed mixed runs. That bootstrap bypass
  is absent from production; an unobserved partial font tuple is rejected.
- Unmodified source then changed word `one` to observed Helvetica Neue Regular
  and size 67, and applied blue color to a typed 33%/33% range. The effective
  run verifier preserved all other attributes. Computer Use showed smaller
  Regular `one`, blue Regular `two`, and white Bold `three`.
- Full font/size/color were restored while the fixture was ASCII, then original
  content restored. Final text and formatted detail exactly equal baseline:
  `Codex MCP text test — placeholder only`, HelveticaNeue-Bold, 72, white.

Emoji fallback previously changed fontName/family/style unexpectedly. Broad
non-Latin selections remain blocked rather than accepting those extra changes.
Partial shadows cannot be validated: available fixtures omitted those attributes
from `/text/format`. No default or shadow metadata was invented. Not all Latin
characters, fonts or percentage boundaries were live tested; full readback still
checks every attribute and stops on unexpected normalization.

## Native FX identity and saved parameters

QLab's flat `/videoEffects` dictionaries do not themselves identify an effect.
The implementation uses keys only to bound documented native named queries.
A named `/videoEffect/{type}/parameters` getter must match one unique indexed
payload. Explicit native metadata remains supported. Repeated/ambiguous payloads
and incomplete stacks block writes; no inference from UI labels authorizes them.

The Video fixture was natively identified as EdgeWork, confirmed by its UI
label. Radius 10 → 8 → 10 passed signed source MCP verification and UI contrast.
Its out-of-band intensity 2.61917877 was preserved. Write bands were not widened.
Negative named getters returned native errors rather than fabricated identity.

Repeated identical inventory reads on the same TCP session intermittently
suppressed replies even after earlier alwaysReply setup. A per-read prepared
UUID getter followed by fresh identity-bound inventory solved the reproduction,
including empty stacks. This is an observed session behavior, not a proven
internal QLab diagnosis. Setters still have their own preparation, fresh full
readback and no retry after ambiguous timeout.

## Structural FX production verification

An experimental rehearsal checked candidate defaults. The final rehearsal
used unmodified production code, the 5.5.10 version guard, complete snapshots
and fresh Fade-target inventory. Starting with the Text fixture's empty stack:

1. Add Gamma: default `inputPower=1`, enabled true.
2. Set Gamma `inputPower=1.4`: native float `1.399999976158142`.
3. Insert Exposure at 0: default `inputEV=0`, preserving Gamma.
4. Move Gamma from 1 to 0: Gamma/Exposure order, parameters and neighbors intact.
5. Delete Exposure at 1, then delete Gamma at 0, each with a new token.
6. Fresh native stack `[]`; Computer Use displayed `(no video effects)`.

The modified stack and Gamma 1.400 were also contrasted with UI in the rehearsal.
Each operation sent exactly one setter. Add/insert only accept validated
Gamma/Exposure defaults and reject a repeated type. Delete requires a provable
reconstruction with known defaults and in-band saved parameters; this is a
preflight proof, not automatic rollback. Move requires complete identity and
neighbor verification. Insert/delete/move reject any Fade targeting the cue or
an incomplete fresh workspace traversal. Effects not covered by the live
fixtures are not declared verified merely because catalogue entries exist.

## Automated and catalogue verification

Full suite: **1670 passed, 35 skipped, 61 subtests passed**. Coverage includes
font payload types/TCP, native identity and denial handling, repeated effects,
structural version/default gates, stale Fade dependencies, empty inventory
preparation, Text UTF-16/percentage/word/font conflicts, unknown attributes,
merged runs and the existing signed token/UDP/TCP/no-retry regressions.

`Client(mcp).list_tools()` confirmed 74 tools, strict fonts workspace UUID,
output schema, 47 read annotations and no generic editor. Tool contracts and
README inventory were updated. `git diff --check` passed.

## Remaining limits

Blocked: partial shadows and missing attributes; new partial font tuples;
non-Latin/emoji fallback; complex word tokenization; repeated/ambiguous FX;
new effect defaults beyond Gamma/Exposure; structural versions other than
5.5.10; index shifts with a Fade dependent; Fade FX activation flags.

Video, Camera and Text share the implementation. This turn's live FX fixtures
were Video and Text; Camera has automated coverage, without a new Camera FX
write. No GO, Preview, Send, external signals, AppleScript or playback occurred.
