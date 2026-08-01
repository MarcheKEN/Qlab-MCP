# Test-quality investigation command log

Read-only shell commands executed by the `test_quality` subagent. Commands are listed in execution order. No production files, tests, QLab workspaces, or Git history were changed.

For heredoc AST probes whose exact bodies were compacted from the available transcript, the body is explicitly marked unavailable rather than reconstructed.

1.

```sh
sed -n '1,240p' <ATTACHMENT_PATH>
```

2.

```sh
sed -n '241,520p' <ATTACHMENT_PATH>
```

3.

```sh
sed -n '521,800p' <ATTACHMENT_PATH>
```

4.

```sh
sed -n '801,1080p' <ATTACHMENT_PATH>
```

5.

```sh
sed -n '1,260p' <CODEX_HOME>/skills/codebase-inspection/SKILL.md
```

6.

```sh
sed -n '1,260p' <CODEX_HOME>/skills/verification-before-completion/SKILL.md
```

7.

```sh
rg -n -i 'automated tests|test quality|pytest|write_mode|transport' <MEMORY_PATH> | head -n 80
```

8.

```sh
rg --files -g 'test*.py' -g '*test*.py' -g 'conftest.py' -g 'pytest.ini' -g 'tox.ini' -g 'noxfile.py' -g 'pyproject.toml' -g '.github/workflows/*' -g '!engineering-review/**' | sort
```

9.

```sh
wc -l pyproject.toml tests/*.py
```

10.

```sh
rg -n '^def test_|^async def test_|^class Test|^@pytest|^pytestmark|^@unittest|^class Fake|^class Stub|^class Mock' tests pyproject.toml
```

11.

```sh
sed -n '1,260p' pyproject.toml
```

12.

```sh
git status --short && git branch --show-current && git rev-parse HEAD
```

13.

```sh
rg --files src/qlab_mcp | sort
```

14.

```sh
find tests -maxdepth 1 -type f -name 'test_*.py' -print0 | xargs -0 -n1 sh -c 'printf "%s " "$0"; rg -c "^def test_|^async def test_" "$0"'
```

15.

```sh
rg -n 'pytest|ruff|mypy|pyright|coverage|hypothesis|tox|nox|test' README.md AGENTS.md CONTRIBUTING.md CHANGELOG.md pyproject.toml .github docs -g '*.md' -g '*.toml' -g '*.yml' -g '*.yaml' 2>/dev/null | head -n 240
```

16.

```sh
rg -n '^(from qlab_mcp|import qlab_mcp)' tests/*.py
```

17.

```sh
/usr/bin/time -p .venv/bin/pytest --collect-only -q
```

18.

```sh
.venv/bin/pytest --collect-only -q 2>/dev/null | rg '^tests/' | cut -d: -f1 | sort | uniq -c
```

19.

```sh
/usr/bin/time -p .venv/bin/pytest -q --tb=short
```

20.

```sh
ps -axo pid,ppid,command | rg -i 'pytest|python.*qlab'
```

21.

```sh
git status --short
```

22.

```sh
/usr/bin/time -p .venv/bin/pytest tests/test_osc.py -q --tb=short
```

23.

```sh
/usr/bin/time -p .venv/bin/pytest tests/test_qlab_reader.py -q --tb=short -x
```

24. This command was rerun outside the sandbox after the loopback-socket restriction was confirmed.

```sh
.venv/bin/pytest -q --tb=short
```

25. Python AST assertion scan. Exact heredoc body unavailable after transcript compaction.

```sh
python3 - <<'PY'
[exact body unavailable after compaction]
PY
```

26. UTF-8-SIG-aware Python AST assertion scan. Exact heredoc body unavailable after transcript compaction.

```sh
python3 - <<'PY'
[exact body unavailable after compaction]
PY
```

27.

```sh
sed -n '1628,1685p' tests/test_write_mode.py && sed -n '1,150p' tests/test_osc.py && sed -n '1,90p' tests/test_qlab_reader.py
```

28.

```sh
sed -n '90,180p' tests/test_qlab_reader.py && sed -n '1,140p' src/qlab_mcp/osc/client.py && sed -n '140,360p' src/qlab_mcp/osc/client.py && sed -n '360,680p' src/qlab_mcp/osc/client.py
```

29.

```sh
rg -n -i 'concurrent|thread|single.flight|simultaneous|overlap|lock|duplicate repl|duplicate.*reply|late repl|delayed repl|out.of.order|stale repl|cancel|pending|shutdown|close|retry' tests/*.py
```

30.

```sh
rg -n -i 'multi.*workspace|multiple workspace|two workspace|ws-2|workspace.*ambiguous|ambiguous.*workspace|displayName|workspace_id.*ws' tests/*.py
```

31.

```sh
rg -n -i '/live|live_mode|live mode|relative|increment|decrement|delta|enum|continueMode|frameRate|blend|mode' tests/*.py
```

32.

```sh
rg -n -i 'readback|fresh|setter.*once|one setter|count\(.*setter|received.*count|timeout.*matching|poll' tests/*.py
```

33.

```sh
rg -n '^\s*assert\s+(not\s+)?[A-Za-z_][A-Za-z0-9_]*\s*$|assert\s+.+\bis not None\s*$|assert\s+len\(.+\)\s*$|self\.assertTrue\([^=]+\)$|self\.assertIsNotNone\(' tests/*.py
```

34.

```sh
rg -n 'except\s+(Exception|BaseException)|except\s*:\s*$|contextlib\.suppress|pytest\.warns|filterwarnings|xfail|skip|flaky|rerun|random|time\.sleep|thread\.join|setUp|tearDown|autouse' tests/*.py pyproject.toml
```

35.

```sh
rg -n 'assert .* in (result|str\(|message|error|description)|assert .*startswith|assert .*endswith|assert any\(|assert all\(|assert not any\(' tests/*.py
```

36.

```sh
rg -n 'test_.*(concurrent|duplicate|late|delay|workspace|live|relative|enum|readback|timeout|retry|order)' tests/*.py
```

37. Python AST category/name/line inventory. Exact heredoc body unavailable after transcript compaction.

```sh
python3 - <<'PY'
[exact body unavailable after compaction]
PY
```

38. Python exact structural-duplicate scan. Exact heredoc body unavailable after transcript compaction.

```sh
python3 - <<'PY'
[exact body unavailable after compaction]
PY
```

39.

```sh
sed -n '1,240p' tests/test_update_registry_coverage.py && sed -n '1,120p' tests/test_read_coverage.py && sed -n '1340,1668p' tests/test_write_mode.py
```

40.

```sh
sed -n '220,285p' tests/test_qlab_reader.py && rg -n 'shared_read_cache\.(clear|invalidate)|_locks|_consumed|_confirmation|clear\(' tests/test_*.py | head -n 240 && rg -n '^def _|^class Fake|^class .*Tests|^    def setUp|^    def tearDown' tests/*.py
```

41.

```sh
rg -n '^_[A-Z][A-Z0-9_]*\s*[:=]|threading\.(Lock|RLock)|lru_cache|cache|consum|token|baseline' src/qlab_mcp/write/*.py src/qlab_mcp/runtime/*.py src/qlab_mcp/osc/client.py | head -n 300
```

42.

```sh
sed -n '9700,10130p' tests/test_write_mode.py && sed -n '330,430p' src/qlab_mcp/write/operations.py && sed -n '9900,10180p' src/qlab_mcp/write/operations.py
```

43.

```sh
rg -n 'FADE_RECOVERY|recovery' tests/test_write_mode.py | head -n 120 && rg -n '_CONSUMED_GROUP_TOKENS|PHASE8_STAGEID_RECOVERY_BASELINES|_FADE_RECOVERY_RECORDS|_locks' tests/*.py
```

44.

```sh
rg -n '_PHASE8_STAGEID_RECOVERY_BASELINES' src/qlab_mcp/write/operations.py && rg -n '_FADE_RECOVERY_RECORDS' src/qlab_mcp/write/operations.py && sed -n '10000,10110p' src/qlab_mcp/write/operations.py
```

45.

```sh
sed -n '150,265p' tests/test_server_tools.py && sed -n '360,435p' tests/test_server_tools.py && sed -n '703,860p' tests/test_server_tools.py
```

46.

```sh
sed -n '1,280p' src/qlab_mcp/osc/messages.py && sed -n '1,220p' src/qlab_mcp/runtime/read_cache.py && sed -n '730,792p' tests/test_qlab_reader.py && sed -n '4400,4510p' tests/test_qlab_reader.py
```

47.

```sh
sed -n '1,260p' src/qlab_mcp/config.py && sed -n '2040,2085p' tests/test_write_mode.py && rg -n 'QLAB_HOST|QLAB_OSC_PORT|QLAB_REPLY_PORT|QLAB_TIMEOUT|cache_ttl|from_env|QLAB_CACHE' tests/*.py
```

48.

```sh
wc -l src/qlab_mcp/*.py src/qlab_mcp/cues/*.py src/qlab_mcp/osc/*.py src/qlab_mcp/runtime/*.py src/qlab_mcp/settings/*.py src/qlab_mcp/write/*.py | sort -n
```

49.

```sh
sed -n '1,180p' tests/test_server_tools.py && rg -n '^def qlab_|^@mcp\.tool' src/qlab_mcp/server.py
```

50.

```sh
sed -n '1,390p' src/qlab_mcp/qlab.py && sed -n '1,150p' src/qlab_mcp/osc/addressing.py && sed -n '1,160p' src/qlab_mcp/write/timeouts.py && sed -n '1,150p' src/qlab_mcp/write/results.py
```

51.

```sh
rg -n '(/\+|/-|\+\\"|-\\"|increment_decrement|address.*\+|address.*-)' tests/*.py src/qlab_mcp/write/*.py | head -n 240 && sed -n '4690,5130p' tests/test_write_mode.py
```

52.

```sh
.venv/bin/python -m coverage --version
```

53. This diagnostic duration run was allowed to use local loopback sockets outside the sandbox.

```sh
.venv/bin/pytest -q --tb=short --durations=20
```

54.

```sh
rg -n 'pytest\.skip|@pytest\.mark\.skip|skipif|xfail' tests/*.py
```

55.

```sh
.venv/bin/pytest --collect-only -q 2>/dev/null | rg 'NOTSET|empty_parameter_set|SKIPPED|skip'
```

56.

```sh
sed -n '7400,7528p' tests/test_write_mode.py && rg -n 'VIDEO_PHASE2_SCALAR|scalar_matrix' tests/test_write_mode.py
```

57.

```sh
sed -n '7740,7835p' tests/test_write_mode.py
```

58. This command failed before `rg` because zsh expanded an unmatched `requirements*.txt` glob.

```sh
for path in pytest.ini setup.cfg tox.ini noxfile.py .coveragerc .github; do if [ -e "$path" ]; then printf '%s\n' "$path"; fi; done; rg -n '^\[tool\.(ruff|mypy|pyright|coverage)|pytest-cov|hypothesis|pytest-asyncio|pytest-xdist' pyproject.toml uv.lock requirements*.txt 2>/dev/null
```

59.

```sh
rg --files -g 'pytest.ini' -g 'setup.cfg' -g 'tox.ini' -g 'noxfile.py' -g '.coveragerc' -g '.github/**' -g 'requirements*.txt' -g 'uv.lock' -g 'pyproject.toml' | sort && rg -n '^\[tool\.(ruff|mypy|pyright|coverage)|pytest-cov|hypothesis|pytest-asyncio|pytest-xdist' pyproject.toml
```

60.

```sh
rg -n 'name = "(pytest|pytest-cov|coverage|ruff|mypy|pyright|hypothesis|pytest-asyncio|pytest-xdist)"' uv.lock
```

61.

```sh
command -v uv || true; command -v hatch || true; .venv/bin/python --version; .venv/bin/pytest --version
```

62.

```sh
nl -ba <MEMORY_PATH> | sed -n '140,166p;432,448p'
```

63.

```sh
nl -ba <MEMORY_PATH> | sed -n '110,140p;410,432p'
```

64.

```sh
nl -ba <MEMORY_PATH> | sed -n '80,112p'
```

65. Python percentage calculation probe. Exact heredoc body unavailable after transcript compaction.

```sh
python3 - <<'PY'
[exact body unavailable after compaction]
PY
```

66.

```sh
.venv/bin/pytest -q -rs tests/test_write_mode.py::test_video_phase2_scalar_matrix_plans_normalized_diff_without_token
```

67.

```sh
rg -n '^def test_.*(doc|matrix|snapshot)|\.read_text\(' tests/*.py
```

68.

```sh
sed -n '348,825p' tests/test_write_mode.py
```

69.

```sh
nl -ba pyproject.toml && nl -ba tests/test_osc.py | sed -n '1,150p' && nl -ba tests/test_qlab_reader.py | sed -n '1,180p'
```

70.

```sh
nl -ba src/qlab_mcp/osc/client.py | sed -n '80,315p' && nl -ba src/qlab_mcp/runtime/read_cache.py | sed -n '20,110p'
```

71.

```sh
git status --short && git diff -- tests pyproject.toml src/qlab_mcp
```

