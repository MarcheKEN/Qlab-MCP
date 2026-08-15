# QLab MCP 0.3.0: MCP Agent UX and Edit Cleanup Research

Date: 2026-08-13

Repository baseline: `codex/docs` at `7f1f13f5b012329cef2635beb2134d8b82e9475d`

Scope: repository, MCP/FastMCP, agent UX, and documentation research only

Runtime boundary: no QLab connection or mutation was used

## Executive conclusion

QLab MCP does not contain two batch-edit engines. The public tool
`qlab_edit_cues` calls a one-line `edit_cues()` wrapper, which delegates to the
real `update_cues()` implementation. The cleanup is therefore a small control-
flow correction: make `edit_cues()` own the existing implementation, redirect
the local singular wrapper, remove the plural historical method, and migrate
tests. Safety logic does not need to change.

The public 13-tool surface is already small and substantially better specified
than many MCP servers. Its largest UX problems are not missing prose. They are:

- important input relationships enforced only at runtime rather than expressed
  in JSON Schema;
- repeated universal safety text across server instructions, tool descriptions,
  README, user docs, and status docs;
- inconsistent output/error shapes in a few tools;
- documentation pages that serve several audiences at once;
- `FastMCP(...)` not receiving the project version, so initialization currently
  reports FastMCP `3.3.1` rather than QLab MCP `0.3.0` as the server version.

The recommended 0.3.0 iteration is deliberately narrow: remove the exact
`update_cues` compatibility layer, correct server metadata, centralize universal
agent rules, improve the 13 descriptions and parameter guidance semantically,
and make the existing documentation hierarchy navigable. It should not add new
QLab capabilities, alter write gates, introduce dynamic tool discovery, or
rebuild every schema.

## 1. Method and evidence boundary

The investigation used:

- current repository code, tests, generated FastMCP schemas, and documentation;
- an in-memory FastMCP client and `fastmcp inspect` with no QLab calls;
- official MCP, FastMCP, QLab, and project-maintainer sources;
- representative MCP servers selected for maintained code, documented contracts,
  and relevant safety/discovery patterns rather than stars alone.

The evidence hierarchy was:

1. MCP/FastMCP/QLab official documentation for protocol and product behavior;
2. current repository implementation for actual QLab MCP behavior;
3. current tests for protected behavior;
4. runtime documents only for their stated QLab version and fixture;
5. design inference, always labelled as a recommendation.

Current QLab web documentation describes QLab 5.6.3. This repository's concrete
runtime evidence remains scoped to QLab 5.5.10. General QLab behavior may be
checked against current official docs, but local timeout, Cart, Create, Move, and
Delete observations must not be promoted to 5.6.3 claims.

## 2. Exact repository baseline

| Item | Observed value |
|---|---|
| Branch | `codex/docs` |
| Worktree before research | clean |
| HEAD | `7f1f13f5b012329cef2635beb2134d8b82e9475d` |
| `origin/main` | `ccb2f45ed5e55e60c83aa2ba568b765726b3c86d` |
| Divergence | 3 local commits ahead, 0 behind |
| Local commits | `3f4656e`, `e638f8e`, `7f1f13f` |
| Project version | `0.3.0` in `pyproject.toml`, package, and lock |
| FastMCP / MCP lock | FastMCP 3.3.1 / MCP 1.27.1 |
| Public tools | exactly 13 |
| Public `qlab_update_cues` | absent |
| Internal `update_cues()` | present as the real batch implementation |

Authoritative tool inventory:

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_status`
4. `qlab_get_workspace_settings`
5. `qlab_get_workspace_setting_details`
6. `qlab_query_cues`
7. `qlab_get_cue_details`
8. `qlab_check_write_readiness`
9. `qlab_create_cue`
10. `qlab_create_cues`
11. `qlab_edit_cues`
12. `qlab_move_cues`
13. `qlab_delete_cues`

## 3. Internal legacy cleanup audit

### 3.1 Current control flow

```text
qlab_edit_cues
  -> QLabReader.edit_cues()       one-line public-name wrapper
  -> QLabReader.update_cues()     real batch implementation
     -> normalize and validate
     -> dry-run plan, or real preflight
     -> execute setters and fresh verification
     -> build batch result
```

`update_cues()` has only two production callers: `edit_cues()` and the local
single-item compatibility method `update_cue()`. There is no second batch
implementation and no duplicate safety path.

### 3.2 Dependency and observability map

| Location / symbol | Current role | Legacy name | Publicly observable | Recommended action | Risk |
|---|---|---:|---:|---|---|
| `server.py::qlab_edit_cues` | only MCP Edit tool | no | yes | keep name and behavior | low |
| `operations.py::edit_cues` | one-line wrapper | no | Python callers only | replace wrapper with existing batch body | low |
| `operations.py::update_cues` | canonical batch engine | yes | possible undocumented Python callers | remove after body transfer | medium compatibility risk |
| `operations.py::update_cue` | single-item local compatibility adapter | related, but not plural alias | possible undocumented Python callers | keep initially; call `edit_cues()` | low |
| private `_...update_batch...` helpers | implementation vocabulary | generic update | no | leave unless a later mechanical rename improves clarity | low; broad rename adds churn |
| `registry.py::update_cues_capability` | local variable | yes | variable no; payload yes | rename local variable only | low |
| readiness key `batch_update_cues` | duplicate capability payload | yes | yes | explicit 0.3 decision: remove only with a contract test and changelog | medium |
| readiness key `edit_existing_cue` | canonical capability payload | no | yes | retain | low |
| `CueUpdateInput`, `UpdateCuesResult`, status values and `updated_count` | input/output schema vocabulary | generic update | yes | retain for 0.3 unless a separate schema break is approved | high churn if renamed |
| `QLAB_UPDATE_*` error codes | machine-readable result contract | generic update | yes | retain | high client risk |
| `QLAB_UPDATE_DEBUG` | user configuration | generic update | yes | retain | medium migration risk |
| `updateq_plan`, `update_capabilities` | response fields | domain/result terminology | yes | characterize separately; do not sweep-renormalize | high schema risk |
| tests calling `reader.update_cues()` | coverage routed through old name | yes | no | migrate batch calls and test names to `edit_cues()` | low |
| `CHANGELOG.md` historical mentions | release history | yes | yes | preserve | none |
| `docs/archive/**`, `docs/qclass/**` | historical evidence or QLab teaching text | sometimes | historical | preserve | none |

The key boundary is exact: eliminating the `update_cues` compatibility layer
does not require deleting every legitimate English use of “update”. Statuses
such as `updated`, the input noun `updates`, stable error codes, and schema field
names are public contracts, not duplicate implementations.

### 3.3 Recommended post-cleanup architecture

```text
FastMCP qlab_edit_cues
  -> QLabReader.edit_cues()       owns the unchanged batch implementation
     -> existing normalize / plan / preflight / execute / verify helpers

QLabReader.update_cue()           optional single-item Python adapter
  -> QLabReader.edit_cues()

QLabReader.update_cues()          absent
```

The safest 0.3.0 choice is no deprecated plural alias: an undocumented Python
consumer calling `QLabReader.update_cues()` will break. Keeping an alias would
contradict the requested canonical state. This break must be named in the
changelog. The singular adapter can remain because it provides different
single-item result/error adaptation and is not the removed public batch alias.

Removing the public readiness key `batch_update_cues` is a separate, observable
choice. It duplicates `edit_existing_cue`; removing it would complete the
conceptual cleanup but must be treated as a deliberate 0.3.0 response-schema
break. It must not be hidden inside the method move.

## 4. Human documentation audit

### 4.1 Current roles and overload

| Area | Proper role | Current issue |
|---|---|---|
| `README.md` | project entry point | also acts as safety spec, full tool catalog, runtime evidence ledger, schema reference, and troubleshooting guide |
| `docs/user/` | safe operation and workflows | `README.md` compresses all writes into one long section; `tools.md` becomes a second Create guide |
| `docs/development/` | architecture and validation method | useful content, but `runtime-validation/edit-cues.md` has 266 lines and one Markdown heading |
| `docs/status/` | current truth and pending work | `roadmap.md` contains over 550 lines of closed history; indexes omit current-state and architecture audit |
| `docs/references/` | immutable imported source/reference material | well delimited; preserve |
| `docs/archive/` | historical evidence | well delimited; do not normalize historical names |
| `SECURITY.md` | threat model and policy | generally clear, but its universal token/setter/rollback wording does not fit all write tools |
| `CHANGELOG.md` | release history | clear; historical alias names must remain |
| `CONTRIBUTING.md` | contributor entry point | clear and appropriately small |

The heaviest README block is the write-safety/runtime material around lines
173–440. Tool signatures around lines 591–651 duplicate `docs/user/tools.md`.
Repeated token, dry-run, readback, playback, and runtime-evidence explanations
create the “sopa de letras” effect even when each statement is individually
correct.

### 4.2 Concrete truth/navigation defects

- `docs/README.md` and `docs/status/README.md` omit current-state and the 0.3.0
  architecture audit.
- the active roadmap lists only workorder 029 while current state lists 017,
  019, 021, 022, and 029;
- roadmap paths still point at pre-reorganization workorder locations;
- the OSC coverage snapshot conflicts with current evidence for Devamp, Fade,
  Network `customString`, and `cueTargetNumber`;
- current-state is correctly provisional during release preparation but cannot
  be called a reproducible final snapshot until it records the definitive SHA;
- `SECURITY.md` describes a universal “token + one setter + rollback” sequence,
  but Edit has per-operation tokens, Delete has no automatic rollback, and
  batches may contain several operations.

### 4.3 Minimum useful information architecture

No new top-level documentation system is needed. Reuse the existing hierarchy:

```text
README.md
  identity, boundaries, quick start, compact 13-tool matrix,
  universal workflow, safety summary, links

docs/user/README.md
  user index and first safe session
docs/user/tools.md
  concise authoritative tool catalog
docs/user/agent-workflows.md
  Read/Create/Edit/Move/Delete sequences, examples and common mistakes

docs/development/README.md
  contributor index
docs/development/architecture.md
  modules and contracts
docs/development/runtime-validation/*
  mutation-specific validation procedures and evidence boundaries

docs/status/current-state.md
  reproducible release snapshot
docs/status/roadmap.md
  active and blocked work only, linked to workorders/archive

docs/references/*
  immutable source material
docs/archive/*
  historical truth
```

`docs/user/agent-workflows.md` adds value because it holds multi-tool sequences,
good/invalid call examples, and recovery guidance that cannot fit independently
inside each tool description. It must not become a second schema reference.

### 4.4 README visual target

The README should be a technical landing page, not marketing copy. Recommended
shape:

1. one-paragraph purpose;
2. a three-column capability matrix: Read / Gated writes / Intentionally absent;
3. a short quick start;
4. the 13 tools grouped in a compact table;
5. one universal safe-write flow;
6. the evidence boundary:

   ```text
   planned structure
   ≠ runtime validated
   ≠ show ready for GO
   ```

7. links to user, security, development, status, and reference docs.

Detailed profiles, property lists, token internals, timeout observations,
fixtures, and runtime validation belong in deeper documents.

## 5. External MCP comparison

Counts below are observations at the access date and may be configurable. They
are not quality rankings.

| Project | Why selected | Framework / approximate surface | Useful patterns | Unsuitable for QLab |
|---|---|---|---|---|
| AWS Labs MCP | official broad cloud collection with design guide | Python, FastMCP/Pydantic; many specialized servers | verb+noun naming, rich fields/enums, server instructions, resource-first discovery | monorepo breadth and emphatic prose do not replace hard gates |
| Azure MCP | mature official large API surface | .NET; namespace/consolidated/all modes, hundreds of tools | progressive surface, read-only mode, identity/RBAC, sensitive metadata | cloud RBAC cannot replace fresh QLab tokens/readback |
| Playwright MCP | official stateful automation | TypeScript SDK; ~24 core, ~69 with caps | observe → exact ref → act, opt-in capabilities, clear unsafe naming | arbitrary code escape hatch and ephemeral browser context are unacceptable for show control |
| Google gcloud MCP | official command-oriented server | TypeScript SDK/Zod; one broad command plus vertical tools | parse and reject before execution, permanent denylist, safe alternative in errors | generic `run_*` is the raw-OSC anti-pattern |
| Google MCP Toolbox | maintained configurable integration framework | Go; dynamic tools/toolsets | toolsets, single declarative source, docs/link checks | YAML/dynamic factory would add complexity and weaken QLab-specific gates |
| Supabase MCP | official database MCP with explicit production warning | TypeScript SDK/Zod; 29 default / 32 documented | project scope, feature groups, true read-only mode, compact results | SQL escape hatches and “avoid production” are insufficient for live shows |
| GitHub MCP Server | mature configurable developer API | Go SDK; 20+ toolsets and a reduced default | minimal default surface, read-only precedence, exclude lists, searchable catalog | method-consolidated writes can hide distinct risks; aliases prolong cleanup |
| Sentry MCP | carefully designed agent-facing diagnostic surface | TypeScript/Zod; 19 top-level, hard cap 25 | “use when”, related tools, semantic annotation tests, stable human output | embedded agents and generic execute indirection add non-determinism to writes |
| MCP Filesystem reference | small official reference with comparable 13-tool count | TypeScript SDK; 13 tools | closed scope, explicit annotations, inspect → dry-run → edit | boolean dry-run alone is weaker than QLab-bound confirmation |

### 5.1 Common strong patterns

- `snake_case`, verb-first names with a stable domain prefix when useful;
- smaller default catalogs, capability groups, or toolsets;
- descriptions that distinguish neighboring tools and state “when to use”;
- exact IDs/refs separated from human-readable labels;
- typed enums, ranges, batch limits, and output shapes;
- explicit read-only/destructive metadata, backed by real authorization;
- observation before mutation and a precise next tool;
- generated or source-linked catalogs to limit documentation drift;
- errors that tell the agent what safe corrective action is possible.

### 5.2 Patterns to reject

- arbitrary `run_command`, SQL, JavaScript, or raw protocol tools;
- treating annotations, origins, or descriptive words as a security boundary;
- enormous always-visible tool catalogs;
- hiding operations with different risk under one `method` discriminator;
- implicit current selection/playhead/active targets;
- automatic retries after an ambiguous mutation;
- internal LLM repair on deterministic, latency-sensitive write paths.

## 6. MCP and FastMCP findings

### 6.1 MCP protocol

Officially documented for the project's negotiated 2025-11-25 protocol:

- a Tool exposes `name`, optional `title` and `description`, `inputSchema`,
  optional `outputSchema`, and optional annotations;
- annotations are untrusted hints, not authorization or confirmation;
- `structuredContent` must conform to an advertised `outputSchema`;
- clients should provide human visibility/confirmation for sensitive calls;
- correctable execution failures should normally use a tool result with
  `isError: true`; malformed/unknown requests use protocol errors;
- server `instructions` are optional initialization data. A client may use them,
  but the protocol does not guarantee host-to-model delivery.

### 6.2 FastMCP framework

Officially documented:

- function docstrings produce the tool description;
- `description=` overrides that description;
- Google/NumPy/Sphinx parameter docstrings may be parsed;
- `Annotated[..., Field(description=...)]` has precedence for parameter text;
- Pydantic return models generate output schemas and structured content;
- `title`, `tags`, `ToolAnnotations`, `meta`, timeout, and server instructions are
  available;
- `Client(mcp)` and `fastmcp inspect --format fastmcp|mcp` support contract tests;
- `tags` and FastMCP metadata are framework extensions, not universal MCP signals.

Observed locally with FastMCP 3.3.1:

- `Client.initialize_result.instructions` receives all 3,249 current instruction
  characters;
- 13 tools expose titles, tags, all four annotations, input/output schemas;
- omitting `version=` from `FastMCP(...)` causes server initialization metadata to
  report `3.3.1`, not project version `0.3.0`;
- structured application errors with `status="error"` still appear as MCP
  `isError=false` unless the server uses the error channel;
- schemas are dereferenced by default (`dereference_schemas=True`). Changing that
  is a client-compatibility experiment, not a free token optimization.

Recommended interpretation:

- use server instructions for universal orientation and policy, but repeat each
  operation's critical safety boundary locally and enforce it in code;
- use docstrings for purpose/use/not-use/preconditions/follow-up;
- use `Field` for exact accepted meaning, format, limits, default, and token
  placement;
- keep output interpretation in model fields;
- do not rely on tags for generic clients;
- set the server's project version explicitly;
- characterize MCP error-channel behavior before changing existing result shapes.

## 7. Audit of the 13-tool agent-facing contract

Legend: R = read-only; W = mutating/non-destructive annotation; X = destructive.
Sizes are description / input schema / output schema characters.

| Tool | Meta | What works | Main agent-UX gap | Size |
|---|---|---|---|---:|
| `qlab_check_connection` | R | clear first tool, scopes/mode/candidates | distinguish connection check from full write readiness | 192 / 605 / 1686 |
| `qlab_get_workspace_overview` | R | bounded structural map, truncation | ranges are prose/runtime only; name-vs-UUID semantics weak | 216 / 1788 / 2035 |
| `qlab_get_workspace_status` | R | honest derived/not-exposed status | modes/ranges not represented as enum/constraints | 255 / 981 / 1130 |
| `qlab_get_workspace_settings` | R | summary/details and partial results | mode/request dependency and enums not expressed | 360 / 2129 / 1699 |
| `qlab_get_workspace_setting_details` | R | clear single-request compatibility route | only functional redundancy in public surface | 386 / 1243 / 1271 |
| `qlab_query_cues` | R | rich query purpose and completeness | filters/profiles/ranges are open strings; follow-up could be clearer | 493 / 1999 / 1964 |
| `qlab_get_cue_details` | R | profiles and deep inspection clear | `cue_ref` description is lost in generated schema; single output is wrapped differently | 417 / 1280 / 4358 |
| `qlab_check_write_readiness` | R | strong typed status and preflight role | instructions should call it the eighth read-only tool, not seventh inspector | 277 / 274 / 1371 |
| `qlab_create_cue` | W | strongest workflow/safety description | longest and repetitive; XOR placement only semantic | 717 / 1624 / 2253 |
| `qlab_create_cues` | W | sequence/non-rollback stated | prerequisites/token/readback less explicit; result items opaque | 295 / 1413 / 1246 |
| `qlab_edit_cues` | W | profiles, dry-run and gates explained | no concise after-use/readback/timeout rule; item can be schema-valid with no action | 495 / 2260 / 3846 |
| `qlab_move_cues` | W | sequential/non-atomic stated | placement XOR/ranges mostly prose; `destructiveHint=false` is debatable | 254 / 1671 / 1215 |
| `qlab_delete_cues` | X | destructive, sequential and root-preserving | target exclusivity is runtime-only; result items opaque | 381 / 1278 / 1364 |

All titles exist. Tags are consistent and useful to FastMCP-aware clients. The
read/write/destructive split is mostly consistent. `qlab_edit_cues` and
`qlab_move_cues` deserve an explicit annotation decision: current MCP wording
defines `destructiveHint=false` as additive-only, while both operations replace
or relocate existing state. Setting it to true would be more conservative, but
it is a visible metadata change and not a substitute for the existing gates.

Priority description weaknesses:

1. `qlab_create_cues`: too little workflow guidance compared with single Create.
2. `qlab_move_cues`: weak prerequisite/follow-up and exact placement guidance.
3. `qlab_edit_cues`: missing concise fresh-readback/ambiguous-timeout guidance.
4. `qlab_delete_cues`: missing explicit no-retry and post-disappearance guidance.
5. `qlab_get_cue_details`: generated `cue_ref` description and return wrapping.

The strongest descriptions today are connection, readiness, single Create, and
Delete's destructive boundary. The settings pair is understandable but publicly
redundant; removing the single-detail wrapper should be deferred because it is a
real tool/API change unrelated to Edit cleanup.

### 7.1 Schema findings

- exact UUID requirements are not consistently represented with `format: uuid`;
- Create, Move, and Delete exclusivity rules are validated at runtime but not
  represented by `oneOf`/dependent schemas;
- several available `Literal` types are intentionally flattened to `str`, so
  agents cannot discover enum values from the schema;
- common range and batch constraints live in prose/runtime only;
- Create batch, Move, and Delete use `list[dict[str, Any]]` result items;
- there are no machine-readable examples in the 13 schemas;
- existing schema hashes detect drift but are hard to diagnose without semantic
  assertions.

For 0.3.0, improve only constraints already enforced at runtime when FastMCP can
express them without introducing request-wrapper architecture. Complex XOR
schema redesign and fully typed result migrations should be separate, reviewed
contract changes.

### 7.2 Error findings

The tools mix two concepts:

- transport/framework failure through `ToolError`/MCP error signaling;
- structured domain result with `ok=false`, `status`, `error_code`, and sometimes
  `suggested_action`.

This is not automatically wrong, but the shapes are inconsistent. Connection
and readiness may raise where other reads return a domain error. Create/Edit have
richer error codes than Create batch/Move/Delete. A 0.3.0 task should first
characterize and document the distinction; broad envelope unification belongs
after release unless a concrete client bug is proven.

## 8. Cross-tool workflow audit

Universal agent protocol:

```text
resolve one workspace UUID
→ resolve concrete cue UUIDs through reads
→ capture fresh structural/health baseline
→ check write readiness
→ explicit dry-run and plan review
→ exact operation-specific confirmation where required
→ execute once, never auto-retry an ambiguous mutation
→ fresh readback and interpret the operation-specific result
```

The token and rollback rules are not universal:

- Read: no readiness, token, or rollback.
- Create: `confirm:createCue:v2` for single Create; exactly one placement selector;
  at most one `/new`; identity/placement readback; creation is not GO readiness.
- Edit: no global token; only planned gated operations return per-item tokens to
  copy into `confirm_gates`; verification depends on the property.
- Move: `confirm:moveCues:v1`; sequential, non-atomic; verify parent/order.
- Delete: `confirm:deleteCues:v1`; destructive, sequential, non-idempotent, no
  automatic rollback; verify disappearance or preserved root.

The current descriptions contain most ingredients but do not consistently name
the exact previous and next tool. Each public tool should contain at most one
short `Before:` and one short `After:` sentence when sequencing matters. The full
walkthrough and examples belong in `docs/user/agent-workflows.md`.

QLab product behavior and MCP policy must stay distinct. QLab itself permits cue
numbers, special refs, and OSC editing in Show Mode. QLab MCP intentionally
requires narrower exact UUID/Edit Mode/dry-run/readback workflows. These are
server safety choices, not claims about QLab limitations.

## 9. Server-level instructions design

Use server instructions, but reduce them from a per-tool miniature manual to a
universal contract:

- scope: read/inspect and gated structural writes only;
- exclusions: no GO, stop, panic, playback, audition, or raw OSC;
- resolve one workspace; use exact UUIDs for writes;
- inspect baseline and check readiness;
- dry-run and use the exact tool/item token required by the plan;
- execute once; timeout is neither success nor failure without fresh readback;
- batches are non-transactional unless a tool explicitly says otherwise;
- `created` or structurally edited does not mean runtime validated or GO-ready;
- runtime evidence boundary is QLab 5.5.10.

Do not rely on this text for enforcement or assume every host forwards it to the
model. Tool-local descriptions must retain operation-specific token, atomicity,
rollback, exact target, and follow-up rules.

## 10. Context-cost observations

Current compact components:

| Component | Approximate size |
|---|---:|
| 13 descriptions | 4,738 characters / 674 words |
| server instructions | 3,249 characters / 429 words |
| input schemas | 18,545 bytes |
| output schemas | 25,438 bytes |
| subtotal | 51,970 characters |
| serialized tool catalog plus instructions | about 55,876 characters |

A tokenizer-independent rough order is 13–14k tokens, but the exact value varies
by model and JSON encoding. Schemas, not descriptions, dominate the cost.

The realistic 0.3.0 optimization is not “make every description tiny”. It is to
remove repeated universal prose, improve high-value local statements, and avoid
new schema verbosity. A useful target is a measured reduction of repeated prose
with no loss of the semantic assertions below; no arbitrary percentage should be
a release gate. Schema dereferencing, dynamic toolsets, and model-specific prompt
compression require compatibility experiments and should be deferred.

## 11. Testing gaps and recommended semantic contracts

Retain exact inventory and schema hashes, but add focused assertions that explain
why a change matters:

- exactly 13 names, `qlab_edit_cues` present, public/internal plural alias absent;
- `FastMCP` initialize result reports project version `0.3.0` and non-empty
  universal instructions;
- every tool has title, useful tags, and all four annotations;
- read tools are read-only; Delete is destructive; explicit decision for Edit/
  Move destructive hints;
- every write description names dry-run, exact target, non-atomic/rollback rule,
  and operation-specific confirmation/readback where applicable;
- prerequisite/follow-up references point to existing tool names;
- `cue_ref`, workspace IDs, tokens, limits, and exclusivity have usable schema
  descriptions/constraints;
- in-memory `Client.call_tool` characterization for all eight read-only tools;
- explicit single/batch public shape test for cue details;
- domain errors versus MCP `isError` behavior documented and tested;
- current README inventory is generated or compared against the authoritative
  catalog;
- current-source `rg` guard for exact `update_cues` symbols, excluding archive,
  changelog history, and natural-language QClass material.

Avoid snapshots of entire prose strings. Assert short semantic phrases and
relationships, while hashes continue to detect unreviewed schema drift.

## 12. Explicit answers to the 27 research questions

1. **What is `update_cues` today?** The sole real batch Edit implementation,
   hidden behind a one-line `edit_cues()` wrapper.
2. **Duplicate behavior?** No; mainly inverted historical naming and tests routed
   through it.
3. **Safest removal?** Move the unchanged body to `edit_cues()`, redirect
   `update_cue()`, delete plural method, migrate tests, preserve safety helpers.
4. **Public effects?** MCP tool name need not change. Undocumented Python callers
   break; removing `batch_update_cues` or renaming schemas is separately breaking.
5. **Canonical Edit architecture?** MCP `qlab_edit_cues` → reader `edit_cues` → one
   existing normalize/plan/preflight/execute/verify pipeline.
6. **Overloaded README sections?** Write safety/runtime material, profiles/routes,
   signatures, evidence details, and troubleshooting.
7. **What belongs elsewhere?** Multi-tool walkthroughs in user workflows;
   implementation/token internals in development; evidence in status/archive.
8. **Repositories studied?** AWS Labs, Azure, Playwright, gcloud, MCP Toolbox,
   Supabase, GitHub, Sentry, and MCP Filesystem for breadth, maturity, safety, and
   agent-interface relevance.
9. **Common description patterns?** Purpose, use/not-use distinction, exact refs,
   prerequisites, limits, risk, output interpretation, and next action.
10. **Inappropriate patterns?** Arbitrary command/code/protocol tools, implicit
    targets, giant catalogs, generic mutating dispatchers, and auto-retry.
11. **Official FastMCP guidance?** Docstrings/Field descriptions generate agent
    schema text; typed returns generate structured output; titles, annotations,
    instructions, Client, and inspect are first-class facilities.
12. **Underused metadata?** Explicit server version, schema examples for truly
    ambiguous formats, stronger constraints, and possibly conservative Edit/Move
    destructive hints. Tags are already used well.
13. **Use server instructions?** Yes, for universal guidance, never as the only
    copy of critical safety rules.
14. **Centralize universal safety how?** One concise initialization contract plus
    hard code gates; keep tool-specific token/atomicity/rollback locally.
15. **Local description detail?** Purpose, when/not, prerequisite, unique limits
    and risk, result interpretation, and one next step—usually a short paragraph.
16. **Weak descriptions?** Create batch, Move, and portions of Edit/Delete; cue
    details also loses a parameter description in generated schema.
17. **Misleading/incomplete?** Current “seven inspector tools” count, generic
    universal token/rollback wording, and Edit/Move `destructiveHint=false` require
    correction or explicit rationale.
18. **Titles/tags/annotations?** Titles and tags are consistent; annotations are
    complete, with the Edit/Move destructive semantic question noted.
19. **Parameter descriptions strong enough?** Often good in prose, but exact UUID,
    enum, range, XOR, and non-empty-action constraints are not consistently
    machine-readable.
20. **Workflows discoverable?** Partly; ingredients exist but prerequisite and
    follow-up cross-references are inconsistent.
21. **Explicit cross-references?** Yes, one concise previous/next tool reference
    when sequencing is safety-relevant.
22. **Examples where?** Full good/bad calls in user workflows; tiny ambiguous-format
    examples in schema metadata; none essential only in docstring `Examples:`.
23. **Context removable?** Several thousand repeated prose characters may be
    centralized; the ~44k schema bytes dominate and should not be blindly cut.
24. **New tests?** Inventory/legacy guard, initialization version/instructions,
    semantic metadata, read call shapes, cue-details envelope, schema constraints,
    error-channel characterization, and docs/catalog consistency.
25. **Lowest-risk order?** Freeze baseline → remove internal plural alias → verify
    → fix server instructions/version → redesign metadata tool-by-tool → docs →
    semantic contracts → full CI/package verification.
26. **Breaking vs non-breaking?** Internal private/test renames and prose additions
    are non-breaking; removing Python `update_cues`, readiness keys, changing
    annotations, schemas, error envelopes, or output titles/shapes is observable.
27. **Defer beyond 0.3.0?** New capabilities, GO/playback/raw OSC, dynamic toolsets,
    settings-tool removal, schema-framework rewrite, error-envelope unification,
    transport refactor, historical moves, and model-specific optimization.

## 13. Sources

Accessed 2026-08-13. All important claims use official specifications,
documentation, or maintainer repositories.

| Source | Type | Authority / relevance |
|---|---|---|
| [MCP Tools 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | protocol spec | tool, result, safety and annotation contract matching negotiated protocol |
| [MCP Schema 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/schema) | protocol spec | exact wire types including `InitializeResult` |
| [MCP Lifecycle 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) | protocol spec | initialization/version negotiation |
| [FastMCP tools](https://gofastmcp.com/servers/tools) | official framework docs | docstrings, Pydantic, schemas, annotations and metadata |
| [FastMCP server](https://gofastmcp.com/servers/server) | official framework docs | server instructions/version/configuration |
| [FastMCP client](https://gofastmcp.com/v2/clients/client) and [testing](https://gofastmcp.com/servers/testing) | official framework docs | initialization and in-memory contract inspection |
| [FastMCP inspect](https://gofastmcp.com/cli/inspecting) | official framework docs | MCP/FastMCP contract inspection |
| [FastMCP release policy](https://gofastmcp.com/development/releases) | official framework docs | compatibility and pinning context |
| [QLab 5 docs](https://qlab.app/docs/v5/) | official product docs | current QLab behavior and version boundary |
| [QLab OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/) | official product reference | UUIDs, refs and OSC capabilities |
| [QLab workspace](https://qlab.app/docs/v5/fundamentals/workspace/) | official product docs | workspace, cue lists/carts and Edit/Show behavior |
| [AWS Labs MCP](https://github.com/awslabs/mcp) | official maintainer repo | specialized server and design patterns |
| [Azure MCP](https://github.com/microsoft/mcp/tree/main/servers/Azure.Mcp.Server) | official maintainer repo | large-surface scoping and read-only patterns |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | official maintainer repo | stateful observe/ref/action UX and capability groups |
| [gcloud MCP](https://github.com/googleapis/gcloud-mcp) | official maintainer repo | command parsing, denylist and least privilege |
| [MCP Toolbox](https://github.com/googleapis/mcp-toolbox) | official maintainer repo | toolset and generated-documentation patterns |
| [Supabase MCP](https://github.com/supabase/mcp) | official maintainer repo | project scope, feature groups and read-only mode |
| [GitHub MCP Server](https://github.com/github/github-mcp-server) | official maintainer repo | reduced default toolsets and contract evolution |
| [Sentry MCP](https://github.com/getsentry/sentry-mcp) | official maintainer repo | agent-facing descriptions and semantic metadata tests |
| [MCP Filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | official reference repo | closed scope, annotations and dry-run comparison |

## 14. Decision summary

Adopt for 0.3.0:

- one canonical `edit_cues()` implementation;
- concise universal server instructions plus tool-local critical rules;
- explicit project version in FastMCP initialization;
- semantic metadata/schema tests around the fixed 13-tool surface;
- compact README and one user agent-workflow guide;
- correction of current navigation/status truth without rewriting archives.

Defer:

- dynamic toolsets or a new abstraction layer;
- broad schema and error-envelope redesign;
- removal of the settings compatibility tool;
- new QLab operations or any runtime validation;
- model-specific prompt/token optimization;
- changes to token semantics, transport, or write safety.
