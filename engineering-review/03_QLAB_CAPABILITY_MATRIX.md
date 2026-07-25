# 03 — QLab Capability Matrix

## Version and source boundary

- Runtime tested: QLab **5.5.10**.
- Local checked-in OSC Dictionary: QLab 5 reference snapshot, but it has no recorded source date/version/checksum.
- Current official manual observed during the review: QLab **5.6.2**. QLab 5.6 adds `/pathSmooth` and `/pathLoop`; neither appears locally or in implementation/tests.
- Primary references: local `docs/references/qlab_osc_dictionary.md`, `docs/references/osc_queries.md`, official [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/), [OSC Queries](https://qlab.app/docs/v5/scripting/osc-queries/), [change log](https://qlab.app/docs/v5/general/change-log/), and [QLab 5.6 release notes](https://qlab.app/release-notes/5.6).

“Supported” below means the current MCP deliberately represents the workflow, not that every OSC property exists.

## Protocol behavior

| Area | Classification | Evidence and constraint | Value / priority |
| --- | --- | --- | --- |
| Workspace discovery and exact resolution | Well supported | `/workspaces`; zero/multiple omission fails closed; names resolve to UUIDs in `qlab.py:117+` | Essential; keep |
| Multiple-workspace safety | Mostly supported | Public operations qualify workspace; application-wide `/workspaces`/overrides are intentional. Same cue number across real workspaces is unverified | High; add contract test |
| Cue number/UUID addressing | Mostly supported | Exact UUID resolution before writes; UUID heuristic in `osc/addressing.py:8+` could misclassify an unusually long dashed cue number | High; small edge test |
| `selected` / `playhead` / `active` reads | Partially supported | Reads permit aliases; writes reject them. `active` can be plural but deep-detail aggregation is not explicit | Medium; reject or aggregate clearly |
| Synchronous replies | Mostly supported | Strict sender/address and JSON parsing; QLab `deprecated`/`warning` fields are discarded | High; preserve metadata |
| Custom UDP reply port | Partially supported | Client binds `QLAB_REPLY_PORT` but never sends required `/udpReplyPort {port}` | **P1 correctness** |
| UDP authenticated idle lifecycle | Partially supported | Connected-workspace cache has no 61-second expiry; no `/forgetMeNot`, `/udpKeepAlive`, reconnect-on-denial or `/disconnect` | **P1 correctness** |
| TCP + SLIP | Mostly supported | Double-END SLIP and per-connection auth; protocol-faithful fragmentation tests missing | P1 tests |
| OSC updates | Missing | No `/updates 1/0`, `/update/workspace/...` receiver or persistent socket; a test uses obsolete plural `/updates/workspace` | Defer until lifecycle design |
| OSC Queries | Experimental | Network cue text may contain `#...#`; syntax/queryability/continuous updates not validated. `qlab_query_cues` is unrelated local filtering | Low unless operator workflow emerges |
| Boolean setters | Mostly supported | Python bool only; does not expose numeric/string/toggle forms | Safe and clear; leave |
| Integer/float arguments | Mostly supported | Registry validators and OSC int32/float32; range/schema mismatch remains | Improve schemas |
| Enums | Mostly supported | Sampled Continue/Group/Fade/Devamp values match local dictionary; reply-form variation tests absent | Add contract fixtures |
| Saved values | Mostly supported | Broad registry, gates, read-before and fresh readback | Core strength |
| `/live` values | Partially verified / experimental | `secondColorName/live` executed successfully on the inactive Memo and was restored; exhaustive read returned only `properties.secondColorName`, so saved/live read-key separation remains unverified | Keep narrow; fix read-key evidence before widening |
| Classic relative `+/-` | Missing | Inventory records metadata; executor emits neither `/property/+` nor `/property/-` | Defer; needs explicit API semantics |
| QLab 5.5 address-embedded deltas | Missing | No `/property/+/delta` or `/-/delta` | Defer with previous item |
| Deprecated aliases | Partially supported | Known routes gated `deprecated_osc`; QLab warnings not surfaced | Preserve warning fields |
| Raw OSC/playback | Intentionally excluded | Server excludes GO/stop/panic/raw OSC and all playback; appropriate safety/product boundary | Keep excluded |

## Practical capability matrix

| QLab area | Classification | Current surface | Main gap / recommendation |
| --- | --- | --- | --- |
| Application commands | Read-only / intentionally excluded | Version, workspaces, global overrides | Keep transport/output application actions excluded |
| Workspaces | Mostly supported | Discovery, connect scopes, show mode, exact targeting | Fix custom reply port/idle auth; real multi-workspace test |
| Cue lists | Mostly supported | Shallow tree, IDs, bounded index; structural destination | Exact post-create placement incomplete |
| Generic cue properties | Mostly supported | Read profiles; safe saved edits; confirmation gates | Stabilize schemas/capability source |
| Group | Mostly supported | Read, mode/playlist edits, List/Group moves | Maintain; Cart placement still blocked |
| Audio | Mostly supported | Rich reads and many saved properties; blank creation | High-value next: operator-safe Audio basics, no playback |
| Mic | Partially supported | Read and selected safe fields | Validate practical basics before widening |
| Video | Partially supported | Strong reads; many saved routes with safety phases | Finish only operator workflows; add QLab 5.6 path fields if useful |
| Camera | Partially supported | Read and selected registry support | Low priority versus Audio/Mic/operator workflow |
| Text | Partially supported | Read plus proven `text/format/fontName`; RGBA routes demoted/unverified | Keep risky rich/color routes planned-only |
| Fade | Mostly supported saved writes | Read and extensive gated/rollback-aware edits | Mature; avoid expanding numeric matrix without use case |
| Light | Partially supported | Read inventory/analyzer; write surface heavily gated | Output safety/maintenance high; defer broad write support |
| Network | Partially supported | Patch reads and selected saved cue text/types | External side effects; keep output execution excluded |
| MIDI | Partially supported | Reads and selected saved properties | External output risk; no playback |
| MIDI File | Read-only / partial | Read inspection; limited planned registry | Low practical priority |
| Timecode | Mostly supported saved configuration | Reads, status summary, safe fields | Never output in tests; keep playback excluded |
| Transport | Partially supported | Read/target fields; no playback | Maintain target safety; do not expose execution |
| Devamp | Partially supported | Registry/validated saved operations | Existing evidence adequate; prioritize stability |
| GoTo | Partially supported | Reads/target metadata | Do not trigger in MCP |
| Target | Partially supported | Exact target-ID editing with confirmation gates | High risk; retain UUID-first workflow |
| Arm / Disarm | Partially supported | Generic `armed` saved property | Boolean proof exists historically; safe on inactive fixture only |
| Wait | Mostly supported | Read, blank creation, duration/common edits | Useful low-risk cue type |
| Memo | Mostly supported | Read, blank creation, common edits | Best reversible test fixture |
| Audio output patches | Read-only | Summary/detail and redaction | Writes are application/show configuration; keep read-only |
| Audio maps | Read-only | Summary/detail, compact vs technical | Keep read-only |
| Video stages | Read-only | Eight stages discovered; regions/routes detail | Stage writes are high maintenance; defer |
| Video routes | Read-only | Four routes; disconnected state reported | Keep read-only; diagnostics valuable |
| Lighting dashboard | Unable to verify / intentionally not exposed | No safe documented status endpoint | Do not invent values |
| Light patch | Read-only | Safe/technical inventory with TCP fallback | Keep read-only |
| Override controls | Read-only | Current override state returned | Mutation intentionally excluded |
| Workspace status | Mostly supported, derived | Warnings/triggers/timecode/settings plus explicit `not_exposed` sections | Honest and useful; leave architecture |
| Update subscriptions | Missing | TTL reads only | Defer until persistent lifecycle is justified |

## Expansion cost and testability

- New ordinary saved property: low/medium if it fits an existing spec; needs dictionary evidence, validator, registry entry, dry-run address assertion, QLab readback and rollback.
- New specialized cue family: high today because `operations.py` routes/detects/annotates/validates/executes in several places and documentation has separate ledgers.
- `/live`: high safety/semantic cost because saved versus live readback must be distinguished and output can be visible/audible. One inactive Memo `secondColorName/live` route now has current runtime proof, but the read response does not expose a separate `/live` key.
- Relative setters: medium protocol cost but high API ambiguity; define whether MCP accepts delta operations, absolute desired state, or both before code.
- New QLab release: currently high drift risk because local references are unversioned and coverage tests prove consistency only against that snapshot.
- Updates: high lifecycle cost (persistent sockets, shutdown, backpressure, reconnect, subscription ownership). Not justified merely for completeness.

## Priority conclusion

Prioritize transport correctness, current-version reference pinning, one capability manifest, exact placement creation, and safe operator read/cut-list workflows. Defer output control, raw OSC, subscription infrastructure, broad Light/MIDI/Network writes, unrestricted Script/file editing, and numerical property coverage without a named show workflow.
