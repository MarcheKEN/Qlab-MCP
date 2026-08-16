# Executive Summary

This audit migrated repository-authored prose to English while preserving code, tests, identifiers, safety wording, and runtime behavior. The primary migration commit is `9bccefa` (`docs: migrate repository-authored prose to English`), based on `8037aacaa1f653f7e2ea10d530c9b093a0388a7f`; follow-up archive cleanup is included in the final worktree.

No production Python or test files changed. The resulting repository-authored documentation and skills are English, with the intentional non-English test/runtime data listed below.

# Language Policy

English is the canonical language for repository-authored documentation, skills, prompts, tool descriptions, schemas, errors, logs, comments, and user-facing text. Non-English text is allowed only when it is executable/test data, an observed QLab value, an external/imported quotation or artifact, or a required protocol/fixture sentinel.

# Repository Scope

The audit covered tracked files and relevant local files under the repository root. It reviewed source, tests, active documentation, archive material, skills, hidden directories, project configuration, and ignored local artifacts without exposing local credentials or paths.

# Filesystem Inventory

- Tracked files: 225.
- Tracked documentation files: 116 under `docs/`.
- Tracked source files: 54 under `src/`.
- Tracked test files: 17 under `tests/`.
- Tracked skill files: 23 under `skills/`.
- Tracked `.superpowers/` files: 4; tracked `.github/` files: 1.
- Non-ignored untracked files: 0.
- No filename renames were required.

# Hidden Files and Directories

Reviewed `.codex/`, `.github/`, `.superpowers/`, `.vscode/`, `.pytest_cache/`, and generated `.DS_Store` material. The exact `.agents`, `.agent`, `AGENTS.md`, and `agents.md` names are absent. The equivalent hidden agent path actually present is `.codex/agents/`, containing five ignored local TOML agent definitions; all are English. Ignored machine-local, generated, and cache content was not added to the migration commit.

# `.agents` Review

`.agents/` is absent from this checkout, which explains why the reported directory cannot be found here. No tracked or non-ignored `.agents` content required translation. `.codex/agents/` is the local equivalent found by the filesystem scan; its five ignored definitions were inspected, contain no Spanish, and remain excluded from commits.

# Agent and Hidden Path Classification

| Path or explicit file set | Git state | Classification | Spanish | Translate | Commit |
| --- | --- | --- | --- | --- | --- |
| `.codex/agents/fastmcp-mcp-researcher.toml` | Ignored | Local agent config | No | No | No |
| `.codex/agents/qclass-researcher.toml` | Ignored | Local agent config | No | No | No |
| `.codex/agents/qlab-applescript-researcher.toml` | Ignored | Local agent config | No | No | No |
| `.codex/agents/qlab-docs-researcher.toml` | Ignored | Local agent config | No | No | No |
| `.codex/agents/qlab-osc-researcher.toml` | Ignored | Local agent config | No | No | No |
| `skills/qclass-research/agents/openai.yaml` | Tracked | Project-authored skill metadata | No | No | Yes |
| `skills/qlab-5-5-10-osc/agents/openai.yaml` | Tracked | Project-authored skill metadata | No | No | Yes |
| `skills/qlab-5-5-10-reference/agents/openai.yaml` | Tracked | Project-authored skill metadata | No | No | Yes |
| `skills/qlab-5-applescript/agents/openai.yaml` | Tracked | Project-authored skill metadata | No | No | Yes |
| `tests/test_agent_skill_bindings.py` | Tracked | Project-authored test | No | No | Yes |
| `docs/development/research/2026-08-13-tool-result-agent-ux-audit.md` | Tracked | Project-authored research | No | No | Yes |
| `docs/development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md` | Tracked | Project-authored research | One phrase, translated | Yes | Yes |
| `docs/user/agent-workflows.md` | Tracked | Project-authored user documentation | No | No | Yes |
| `docs/superpowers/plans/2026-08-13-qlab-mcp-agent-ux-and-edit-cleanup.md` | Tracked | Project-authored plan | No | No | Yes |
| `.github/workflows/python-app.yml` and `.gitignore` | Tracked | Project configuration | No | No | Yes |
| `.superpowers/sdd/.../task-{1,2,3,9}-report.md` | Tracked | Project-authored process reports | No | No | Yes |
| `.codex/config.toml`, `.vscode/mcp.json` | Ignored | Local configuration; may contain secrets | No | No | No |
| `.superpowers/sdd/` briefs, diffs, progress, and `.gitignore` | Ignored | Local process artifacts | No | No | No |
| `.pytest_cache/`, `.DS_Store`, `.venv/`, `dist/`, `engineering-review/` generated files | Ignored | Generated/cache/dependency material | No | No | No |
| `.venv/.../griffe/_internal/agents/` | Ignored | Installed dependency | No | No | No |

# `.superpowers` Review

The four tracked `.superpowers/` files were reviewed and contain English authored content. Ignored local planning material under `.superpowers/sdd/` was not staged.

# Production Code

`src/` was reviewed without edits. Existing user-facing prose is English. The `¿?` value in `src/qlab_mcp/cues/editorial.py` is an intentional ambiguity sentinel, not authored prose.

# Public MCP Surface

FastMCP inspection reports exactly 14 tools. `qlab_edit_general_settings` is present; the retired `qlab_update_cues` name is absent. Generated tool descriptions and instructions are English. No API names, schemas, identifiers, or safety gates were changed.

# Tests

`tests/` was reviewed without edits. Unicode values in token, reader, and Light analyzer tests are deliberate coverage data, not documentation. The full suite passed after running with the required socket permissions.

# Documentation

Active README, user, development, status, and superpowers-plan documentation was translated where repository-authored Spanish remained. Links, commands, paths, tool names, protocol terms, and safety claims were preserved.

# Skills

The authored `skills/` tree was translated to English, including skill instructions, chapters, agent metadata under `skills/*/agents/openai.yaml`, and the QClass skill metadata. No new skill or dependency was added. The ignored local `.codex/agents/*.toml` definitions were reviewed but are not part of the repository change.

# Archive

Repository-authored archive plans, architecture graphs, runtime reports, and the deep research report were translated. Imported QClass transcripts, references, and source artifacts were treated as external/imported material and retained verbatim.

# Hidden / Untracked Project Files

There are no non-ignored untracked project files. The filesystem reported 6,559 ignored paths, dominated by `.venv/`, caches, build output, and local process material. Ignored `.codex/agents/*.toml`, `.codex/config.toml`, `.vscode/mcp.json`, `.superpowers/sdd/` briefs/diffs, caches, generated artifacts, and local review material were excluded from the commit.

# Files Renamed

None.

# Intentional Non-English Exceptions

- `src/qlab_mcp/cues/editorial.py:15,58` and related reader fixtures: `¿?` ambiguity-sentinel data.
- `tests/test_tokens.py`, `tests/test_light_command_analyzer.py`, and `tests/test_qlab_reader.py`: Unicode test inputs such as `ñ`, `é`, `ÑÓÁ`, and `¿?`.
- `docs/development/runtime-validation/2026-08-13-qlab-mcp-0-3-0-live.md:115-116`: observed QLab cue names `Amanecer frío` and `Entrada cálida`.
- `docs/archive/runtime_probes/runtime_tool_probe_report.md:104`: literal probe value `ÑÑó`.
- `docs/archive/workorders/completed/026_fade_cue_safe_editing.md:81`: the fixture/workspace name `pruebas-fade`.
- `docs/archive/light/light_read_model_plan.md:247-249,501`: observed QLab instrument and group names such as `Cuna`, `FRONTAL`, `PC refuerzo`, `Contra`, `Cabina`, and `CONTRA`.
- These values are observed QLab fixture/user data retained to preserve the runtime record; they are not repository-authored prose.


# Secrets / Local Files Excluded

Local credentials, passcodes, personal paths, `.vscode/mcp.json`, `.codex/` state, caches, generated build output, and other ignored machine-local files were not staged or published.

# Behavioral Diff Review

The migration changes documentation language only. `git diff -- src tests` is empty. Tool names, schemas, cue identifiers, confirmation flows, safety wording, commands, and links were preserved. No QLab runtime mutation was performed.

# Automated Verification

- `uv lock --check`: passed.
- `uv run fastmcp inspect fastmcp.json`: passed; 14 tools.
- `uv run pytest -q`: 2649 passed, 41 subtests passed.
- `uv run pytest -q tests/test_packaging.py`: 2 passed.
- `uv build --out-dir /private/tmp/qlab-mcp-build`: wheel and sdist built successfully.
- Structured FastMCP inspection: 14 tool entries; no accented Spanish prose; `qlab_edit_general_settings` present; `qlab_update_cues` absent.
- `git diff --check`: passed.
- Independent hidden/agent-path scan: no Spanish in `.codex/agents/`, `.github/`, `.superpowers/`, `.vscode/`, or tracked `skills/*/agents/` metadata.
- Follow-up repository-authored prose scan: translated the sole remaining phrase `sopa de letras` to `word-salad`; rerun found no authored Spanish prose.

The default sandbox initially blocked loopback socket binding with `PermissionError: [Errno 1] Operation not permitted`; the same failure reproduced in the reader and OSC transport tests. The suite passed unchanged when rerun with the required permission.

# Review Findings

The independent review of `8037aac` to `9bccefa` found no P0 or P3 issue and no production or test behavior change. It identified that the required migration report and retained-data inventory were not present in the primary commit; this follow-up report and the archive cleanup resolve those P1/P2 documentation findings.

The final filesystem recheck found no `.agents` directory or equivalent tracked project configuration containing Spanish. It did find one remaining Spanish metaphor in the agent-UX research document; that phrase was translated in the bounded follow-up commit.

# Remaining Non-English Content

No repository-authored Spanish prose remains in the audited scope. Remaining non-English strings are the intentional data and imported-artifact exceptions listed above.

# Conclusion

Repository-authored content is now English. The migration is behavior-preserving, locally verified, and limited to documentation, skills, and the language-policy/report records.
