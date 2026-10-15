# Text selection follow-up — 2026-10-11

## Scope and sources

Extend existing typed Text formatting operations without new tools, arguments,
dependencies or playback capabilities. QLab 5.5.10; the installed connector
confirmed one `redacted-test-workspace` workspace and the source FastMCP client confirmed Edit
access. Computer Use checked the expected workspace path, zero active cues and
the disarmed Text fixture. It only inspected/navigated the UI.

References: the repository OSC dictionary's Text messages; QClass Day 2,
07:10:32–07:11:33 (Text inspector/context, not protocol evidence);
[official OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
and [QLab 5.5 change log](https://qlab.app/docs/v5/general/change-log/).
The latter mentions shadow attributes, but does not establish a readable baseline
or the normalization behavior for this installed cue.

## Verified and implemented

- Whole-text blue color on the original Latin text with an em dash passed full
  effective-format verification and UI contrast, then a fresh-token restoration.
- On `«Árbol»—luz “azul”`, UTF-16 range `[6,6]` changed only `»—luz “` to blue.
  Every other attribute remained unchanged; fresh restoration merged equivalent
  runs. Final color-only support adds only NBSP, guillemets, curly double quotes
  and em dash to the existing ASCII/Latin scope. Typography does not inherit
  this expansion; other punctuation/scripts remain blocked.
- A disposable normalization harness sent documented native
  `/text/format/color/word/{index}` setters through the existing FastMCP editor,
  retaining preflight, signed confirmations, one setter and full run verification.
  Indices 0/1/2 exactly selected `[1,5]`, `[8,3]`, `[13,4]` on that fixture.
  Tab/LF and CR fixtures also matched the expected word ranges. No raw address
  argument, probe option or harness code was added to the public server.
- The ordinary production editor then resolved typed word selectors on
  `«Árbol»—luz “azul”\none\ttwo`: word 0 red, word 2 green and word 4 size 48.
  Three sequential JSON setters verified all effective intervals and neighbors.
  Computer Use showed red `Árbol`, green `azul`, unchanged white punctuation and
  smaller `two`. Production uses absolute UTF-16 ranges, not native word routing.
- Word selection now accepts ASCII alphanumeric/Latin words separated by space,
  tab, CR/LF, NBSP, `«»`, `“”` and `—`. Apostrophes, hyphens, other punctuation,
  decomposed combining marks and other scripts remain unproved and rejected;
  supported explicit ranges are available instead.

## Experiment that stayed blocked

An exploratory color-only edit of the emoji in `Árbol—luz\nA😀B 中文 é`
changed its font metadata to Apple Color Emoji. The requested color was applied,
but verification rejected the unrequested font substitution. The executor sent
one setter, stopped and left the two pending operations unsent; no retry occurred.
Manual restoration used a new dry run/token to restore the original content and
its first-character formatting. Final production guards continue blocking emoji,
other scripts and unverified punctuation, even for color. No fallback mapping or
default font was inferred from the experiment.

## Shadows and remaining work

All 12 Text cues returned by the installed MCP's complete bounded type query
were read; none supplied shadow color, radius or offset values in the fragments.
A final partial-shadow dry run failed preflight with zero setters. Full and
partial shadow JSON transport/line scope remain blocked. A fixture with readable
existing shadow metadata is needed to prove changes and restoration; absent
attributes are not zero/default values. No shadow was created blindly.

Complex contractions/delimiters, non-Latin fallback, combining-mark word
segmentation and other font mappings remain pending. This is a bounded Text
extension, not closure of every possible Text format or Video FX parameter.

## Closeout

Fresh reads verified the original content and full formatting restored:
`Codex MCP text test — placeholder only`, Helvetica Neue Bold 72, white,
center aligned, with no effects. The fixture stayed disarmed/inactive. Computer
Use confirmed restoration and returned to the initial Wait/Basics selection.
No cues, signals, GO, Preview or Send were used.

The [sanitized evidence](2026-10-11-text-selections.json) distinguishes native
research probes from ordinary source MCP calls, including the rejected emoji
experiment. The installed connector supplied baseline/inventory reads; these
new source changes need a connector restart before installed-version acceptance.

### Installed connector acceptance after restart

The restarted MCP was tested directly through its public tools on the same
disarmed fixture. Four write calls sent six setters: temporary content, three
word edits, the punctuation/NBSP color range and original-content restoration.
All returned `updated` with fresh readback. Computer Use showed red `Árbol`,
green `azul`, smaller `two`, the blue `»—luz ` range and final white original text.
Full Text data and cue state exactly matched baseline after restoration.
Invalid word indices, typography across unvalidated punctuation and partial
shadows failed preflight with zero setters. A malformed range using `start`
instead of the schema's `index` was rejected before planning. No playback ran.
See [installed evidence](2026-10-11-text-installed-recheck.json). This completes
installed-version acceptance for the bounded extension; remaining limits above
are unchanged.

### Extended installed tests

A second installed-MCP pass tested `Árbol luz azul\none\ttwo\rfin`.
Typed 25% length resolved to seven UTF-16 units; length `-1` covered the tail.
One batch applied four format operations, including combined color/font size.
Fresh fragments and inspector screenshots agreed: red prefix, smaller `azul`,
green size-36 `one`, and blue `two`/`fin`. Uniform restoration merged the mixed
runs into one without losing font metadata. Four successful write calls sent
seven setters, each preceded by a fresh dry run; final full Text/state matched
baseline exactly.

Twelve negative requests were rejected: out-of-bounds/zero/decimal ranges,
percentage above 100, boolean font size, invalid color, unknown attribute,
partial alignment, unavailable underline transport, duplicate destinations,
valid operation followed by an invalid operation, and old confirmations after
baseline changes. Fresh readback proved no changes from these rejected requests.
The 150 focused Text/visual tests passed again. No playback ran. See
[extended evidence](2026-10-11-text-extended-recheck.json). This pass does not
validate arbitrary Unicode, shadows, playback, or every public editor.

Live evidence records 20 write calls and 22 setters: 19 calls verified their
requested changes; the emoji experiment failed full-format verification and
stopped after its first setter. Final content and complete state matched baseline.

Automated verification: 150 focused Text/visual tests passed; the full suite
reported 1805 passed, 35 skipped and 61 subtests passed. Public catalogue
inspection returned 74 tools with unchanged Text arguments. `git diff --check`
passed. An initial sandboxed suite could not bind its test UDP/TCP sockets and
was interrupted; the permitted local-socket run is the authoritative result.
