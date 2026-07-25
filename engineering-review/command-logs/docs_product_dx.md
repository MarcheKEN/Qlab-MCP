# Documentation and Product DX Command Log

Commands are listed in execution order. The `env UV_CACHE_DIR=... uv lock
--check` command appears twice because it was executed twice.

```text
sed -n '1,240p' /Users/filarmonica/.codex/skills/qlab-docs-assistant/SKILL.md

sed -n '1,240p' /Users/filarmonica/.codex/skills/qlab-docs-assistant/references/official-source-map.md

sed -n '1,260p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '261,620p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '621,980p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

rg -n -i "documentation maintenance|QClass|developer experience|packaging|project direction|public write surface|README|pyproject|startup|operator friction" /Users/filarmonica/.codex/memories/MEMORY.md

sed -n '79,158p' /Users/filarmonica/.codex/memories/MEMORY.md && sed -n '35,76p' /Users/filarmonica/.codex/memories/MEMORY.md && sed -n '215,254p' /Users/filarmonica/.codex/memories/MEMORY.md

sed -n '1,240p' /Users/filarmonica/.codex/memories/rollout_summaries/2026-07-14T14-30-38-MQBz-docs_audit_fix_fastmcp_instructions_and_delete_docs.md

git status --short && git branch --show-current && git rev-parse --short HEAD && rg --files -g 'README*' -g 'pyproject.toml' -g 'uv.lock' -g 'fastmcp.json' -g 'AGENTS.md' -g 'CONTRIBUTING*' -g 'CHANGELOG*' -g 'docs/**' -g '!docs/references/qlab_osc_dictionary.md' -g '!docs/references/osc_queries.md' | sort

wc -l README.md pyproject.toml fastmcp.json docs/README.md docs/current/README.md docs/current/active_roadmap.md docs/current/coverage/osc_coverage_snapshot.md docs/current/research/architecture/deep-research-report.md docs/qclass/*.md docs/guides/*.md docs/current/workorders/README.md docs/current/workorders/active/README.md docs/current/workorders/blocked/README.md docs/current/workorders/completed/README.md && rg -n '^#{1,4} ' README.md docs/README.md docs/current/README.md docs/current/active_roadmap.md docs/current/coverage/osc_coverage_snapshot.md docs/current/research/architecture/deep-research-report.md docs/guides/*.md docs/current/workorders/README.md docs/current/workorders/active/README.md docs/current/workorders/blocked/README.md docs/current/workorders/completed/README.md pyproject.toml fastmcp.json

nl -ba README.md | sed -n '1,180p'; nl -ba README.md | sed -n '180,380p'; nl -ba README.md | sed -n '380,581p'

nl -ba pyproject.toml; nl -ba fastmcp.json; rg -n '^name = "(fastmcp|mcp|python-osc|pydantic|pytest|pytest-asyncio|ruff|mypy|hatchling|setuptools|wheel)"|^version = ' uv.lock | sed -n '1,180p'; rg --files -g '.python-version' -g '.env*' -g 'Dockerfile*' -g 'Makefile' -g 'justfile' -g 'tox.ini' -g 'noxfile.py' -g '.pre-commit-config.yaml' -g '.github/**' -g 'scripts/**' -g 'tests/**' | sort | sed -n '1,260p'

nl -ba docs/README.md; nl -ba docs/current/README.md; nl -ba docs/current/workorders/README.md; nl -ba docs/current/workorders/active/README.md; nl -ba docs/current/workorders/blocked/README.md; nl -ba docs/current/workorders/completed/README.md; nl -ba docs/guides/README.md; nl -ba docs/qclass/README.md; nl -ba docs/references/README.md; nl -ba docs/current/plans/README.md; nl -ba docs/current/research/README.md; nl -ba docs/current/architecture/README.md

nl -ba docs/current/active_roadmap.md | sed -n '1,210p'; nl -ba docs/current/active_roadmap.md | sed -n '210,410p'; nl -ba docs/current/active_roadmap.md | sed -n '410,575p'

nl -ba docs/current/coverage/osc_coverage_snapshot.md | sed -n '1,90p'; nl -ba docs/current/coverage/osc_coverage_snapshot.md | sed -n '340,389p'; rg -n -i "generated|regenerate|source of truth|authoritative|current|status|pending|runtime validated|runtime validation|planned-only|implemented" docs/current/coverage/osc_coverage_snapshot.md docs/current/workorders/*.md docs/current/workorders/completed/*.md | sed -n '1,300p'

nl -ba docs/current/coverage/osc_coverage_snapshot.md | sed -n '66,170p'; nl -ba docs/current/coverage/osc_coverage_snapshot.md | sed -n '170,270p'; nl -ba docs/current/coverage/osc_coverage_snapshot.md | sed -n '270,355p'

nl -ba docs/guides/edit_cues_runtime_checklist.md | sed -n '1,280p'

rg -n "FastMCP\(|@mcp\.tool|def qlab_|instructions=|description=|ToolAnnotations|annotations=" src/qlab_mcp/server.py src/qlab_mcp -g '*.py' | sed -n '1,320p'; nl -ba src/qlab_mcp/server.py | sed -n '1,180p'; nl -ba src/qlab_mcp/server.py | sed -n '180,430p'; nl -ba src/qlab_mcp/server.py | sed -n '430,760p'

nl -ba src/qlab_mcp/server.py | sed -n '150,235p'; nl -ba src/qlab_mcp/server.py | sed -n '840,1135p'

nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '1,140p'; rg -n -i "pre[- ]?show|tech table|workspace status|cue list|cue cart|audition|panic|go button|show mode|edit mode|programmer|operator|backup|network|MIDI|timecode|notes|flag|warning|broken|patch|routing|stage|audio map|light patch|collaborat|copy|move|template|workflow|rehears|sound check|video check|line check" docs/qclass/*.md | sed -n '1,360p'

rg --files -g '.gitignore' -g 'LICENSE*' -g 'NOTICE*' -g 'SECURITY*' -g 'CONTRIBUTING*' -g 'CHANGELOG*' -g '.github/**' -g 'docs/**' | sort | sed -n '1,260p'; nl -ba .gitignore 2>/dev/null || true; git ls-files | rg '(^|/)(\.DS_Store|__pycache__|.*\.pyc$)' | sed -n '1,160p'; rg -n -i "uv sync|uv run|fastmcp|stdio|install|setup|configuration|QLAB_ENABLE_WRITE|QLAB_PASSCODE|QLAB_OSC_PORT|QLAB_REPLY_PORT|Claude|Codex|MCP client|json" README.md docs fastmcp.json pyproject.toml -g '*.md' -g '*.toml' -g '*.json' | sed -n '1,360p'

git ls-files | rg '(^|/)(\.DS_Store|__pycache__|[^/]+\.pyc)$' || true; git check-ignore -v docs/.DS_Store docs/current/.DS_Store docs/qclass/.DS_Store docs/references/.DS_Store tests/__pycache__/test_osc.cpython-314.pyc || true; git ls-files pyproject.toml uv.lock fastmcp.json README.md LICENSE LICENSE.md CONTRIBUTING.md CHANGELOG.md SECURITY.md .github/workflows | sort

rg -n "0\.2\.0|__version__|version" src README.md docs pyproject.toml fastmcp.json -g '*.py' -g '*.md' -g '*.toml' -g '*.json' | sed -n '1,260p'; rg -n -i "license|macOS|python 3|supported QLab|QLab 5\.5|QLab 5\.6|compatib|release|version policy|changelog|upgrade|migration|security|secret|passcode" README.md docs pyproject.toml -g '*.md' -g '*.toml' | sed -n '1,360p'

nl -ba src/qlab_mcp/__init__.py; git log -8 --date=short --pretty=format:'%h %ad %s' -- README.md pyproject.toml src/qlab_mcp/__init__.py docs/current/active_roadmap.md docs/current/coverage/osc_coverage_snapshot.md docs/current/workorders/README.md docs/qclass/README.md; git log -1 --format='%h %ad %s' --date=iso-strict -- uv.lock; git log -1 --format='%h %ad %s' --date=iso-strict -- pyproject.toml

rg -n -A18 -B2 '^name = "qlab-mcp"' uv.lock; git diff -- pyproject.toml uv.lock src/qlab_mcp/__init__.py README.md docs/current/active_roadmap.md docs/current/coverage/osc_coverage_snapshot.md docs/current/workorders/README.md; git status --short

uv lock --check

env UV_CACHE_DIR=/private/tmp/qlab-review-uv-cache uv lock --check

env UV_CACHE_DIR=/private/tmp/qlab-review-uv-cache uv lock --check

nl -ba uv.lock | sed -n '336,360p'; nl -ba uv.lock | sed -n '618,632p'; nl -ba uv.lock | sed -n '1040,1065p'; git status --short

rg -n "workspace_id.*UUID|UUID.*workspace|normalize.*workspace|validate.*workspace|require.*workspace|workspace display|display name" src/qlab_mcp/write src/qlab_mcp/runtime src/qlab_mcp/qlab.py tests/test_write_mode.py tests/test_delete_mode.py tests/test_server_tools.py | sed -n '1,360p'; rg -n "WorkspaceId|workspace_id" tests/test_server_tools.py | sed -n '1,260p'

nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '274,320p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '340,430p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '475,522p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '1210,1280p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '1408,1450p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 3.md' | sed -n '4400,4545p'

nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md' | sed -n '3788,3810p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md' | sed -n '5488,5534p'; nl -ba 'docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 3.md' | sed -n '3168,3210p'

nl -ba docs/references/qlab_osc_dictionary.md | sed -n '1,55p'; nl -ba docs/references/osc_queries.md | sed -n '1,55p'; rg -n -i "5\.6|5\.5|updated|generated|source|retrieved|snapshot|upstream|date" docs/references/README.md docs/references/qlab_osc_dictionary.md docs/references/osc_queries.md | sed -n '1,220p'

.venv/bin/python -c 'import importlib.metadata as m, qlab_mcp; print("module", qlab_mcp.__version__); print("metadata", m.version("qlab-mcp"))'

env PYTHONPATH=src .venv/bin/python -c 'import importlib.metadata as m, qlab_mcp; print("module", qlab_mcp.__version__); print("metadata", m.version("qlab-mcp"))'

cmp -s docs/incremental_refactor_execution_plan.md docs/current/plans/incremental_refactor_execution_plan.md; printf 'cmp_exit=%s\n' "$?"; wc -l docs/incremental_refactor_execution_plan.md docs/current/plans/incremental_refactor_execution_plan.md; diff -u docs/incremental_refactor_execution_plan.md docs/current/plans/incremental_refactor_execution_plan.md | sed -n '1,240p'; nl -ba docs/incremental_refactor_execution_plan.md | sed -n '1,80p'; nl -ba docs/current/plans/incremental_refactor_execution_plan.md | sed -n '1,80p'

nl -ba docs/current/coverage/README.md; nl -ba docs/current/architecture/codebase_graphs.md | sed -n '1,180p'; nl -ba docs/current/research/architecture/README.md; nl -ba docs/current/research/architecture/deep-research-report.md | sed -n '1,110p'

git status --short && git diff --stat && git diff --check

nl -ba /Users/filarmonica/.codex/memories/rollout_summaries/2026-07-14T14-30-38-MQBz-docs_audit_fix_fastmcp_instructions_and_delete_docs.md | sed -n '1,120p'; nl -ba /Users/filarmonica/.codex/memories/MEMORY.md | sed -n '79,158p'
```
