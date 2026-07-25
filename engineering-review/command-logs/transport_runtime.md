# Transport/runtime command log

```zsh
sed -n '1,240p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '241,520p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '521,860p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '861,1160p' /Users/filarmonica/.codex/attachments/435999ec-0696-48ca-a951-a2c503e91077/pasted-text-1.txt

sed -n '1,260p' /Users/filarmonica/.codex/skills/codebase-orientation/SKILL.md

rg -n -i "OSC transport|UDP|TCP|pending request|receiver|late repl|duplicate repl|runtime behavior|concurr" /Users/filarmonica/.codex/memories/MEMORY.md

git status --short && rg --files | rg '(^|/)(osc|transport|receiver|discovery|client|server|config|test).*\.py$|pyproject\.toml$|README\.md$'

nl -ba src/qlab_mcp/osc/client.py && nl -ba src/qlab_mcp/osc/messages.py && nl -ba src/qlab_mcp/osc/addressing.py && nl -ba src/qlab_mcp/config.py

rg -n "QLabOscClient|\.request_tcp\(|\.request\(|_send_with_reply|_connected_workspaces|cache_ttl|lru_cache|Cache|Lock|thread|asyncio|timeout|retry|sleep" src tests | head -n 1000

nl -ba src/qlab_mcp/qlab.py | sed -n '1,390p'; nl -ba src/qlab_mcp/runtime/read_cache.py; nl -ba src/qlab_mcp/server.py | sed -n '1,180p'; nl -ba src/qlab_mcp/server.py | sed -n '300,430p'

nl -ba src/qlab_mcp/server.py | sed -n '176,300p'; nl -ba src/qlab_mcp/errors.py; rg -n "shared_read_cache\(\)|\.clear\(\)|_reader\(|QLabReader\(" src tests | head -n 250

nl -ba tests/test_osc.py; nl -ba tests/test_qlab_reader.py | sed -n '1,330p'; nl -ba tests/test_qlab_reader.py | sed -n '430,640p'; nl -ba tests/test_qlab_reader.py | sed -n '1920,2130p'; nl -ba tests/test_qlab_reader.py | sed -n '2920,3070p'

nl -ba tests/test_qlab_reader.py | sed -n '230,430p'; rg -n "duplicate|late|out.of.order|out of order|unrelated|cancel|cancell|pending|concurrent|simultaneous|single.flight|same address|sender|wrong sender|source port|cache|TTL|expired|inflight|clear while|TCP.*SLIP|partial frame|fragment|connection closed|retry" tests/test_osc.py tests/test_qlab_reader.py tests/test_write_mode.py src/qlab_mcp | head -n 500

rg -n -i "reply port|reply.*port|53001|/connect|connect.*passcode|TCP|SLIP|UDP|OSC Replies|OSC Queries|keep.alive|keepalive|disconnect|subscription|updates" README.md docs src tests | head -n 700

nl -ba docs/references/qlab_osc_dictionary.md | sed -n '1,90p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '195,290p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '550,685p'; nl -ba docs/references/qlab_osc_dictionary.md | sed -n '720,745p'; nl -ba README.md | sed -n '430,505p'

/usr/bin/time -p .venv/bin/pytest -q tests/test_osc.py tests/test_qlab_reader.py::QLabReaderTests::test_get_workspaces_single_flight_shares_concurrent_resolution tests/test_qlab_reader.py::QLabReaderTests::test_read_cache_can_be_disabled_with_zero_ttl tests/test_qlab_reader.py::QLabReaderTests::test_read_cache_bypasses_live_state_and_sensitive_profiles tests/test_qlab_reader.py::QLabReaderTests::test_workspace_overview_global_count_uses_tcp_after_udp_timeout tests/test_qlab_reader.py::QLabReaderTests::test_workspace_setting_details_light_patch_falls_back_to_tcp_after_udp_timeout

git log --oneline --decorate -12 -- src/qlab_mcp/osc/client.py src/qlab_mcp/runtime/read_cache.py tests/test_osc.py tests/test_qlab_reader.py; nl -ba pyproject.toml | sed -n '1,180p'; git blame -L 83,140 -- src/qlab_mcp/osc/client.py; git blame -L 27,81 -- src/qlab_mcp/runtime/read_cache.py

/usr/bin/time -p .venv/bin/python - <<'PY'
import threading
from qlab_mcp.runtime.read_cache import ReadCache

cache = ReadCache()
started = threading.Event()
release = threading.Event()

def stale_factory():
    started.set()
    release.wait()
    return "stale"

owner = threading.Thread(target=lambda: cache.get_or_set("cue", 10, stale_factory))
owner.start()
assert started.wait(1)
cache.clear()
release.set()
owner.join(1)
print("post_clear_value=", cache.get_or_set("cue", 10, lambda: "fresh"))
print("owner_alive=", owner.is_alive())
PY

/usr/bin/time -p .venv/bin/python - <<'PY'
import sys
import threading
sys.path.insert(0, "src")
from qlab_mcp.runtime.read_cache import ReadCache

cache = ReadCache()
started = threading.Event()
release = threading.Event()

def stale_factory():
    started.set()
    release.wait()
    return "stale"

owner = threading.Thread(target=lambda: cache.get_or_set("cue", 10, stale_factory))
owner.start()
assert started.wait(1)
cache.clear()
release.set()
owner.join(1)
print("post_clear_value=", cache.get_or_set("cue", 10, lambda: "fresh"))
print("owner_alive=", owner.is_alive())
PY

/usr/bin/time -p .venv/bin/python - <<'PY'
import runpy
import sys
import threading
import time
sys.path.insert(0, "src")
from qlab_mcp.config import QLabConfig
from qlab_mcp.osc.client import QLabOscClient

FakeQlabOscServer = runpy.run_path("tests/test_qlab_reader.py")["FakeQlabOscServer"]

def slow_reply(_message):
    time.sleep(0.1)
    return "ok"

with FakeQlabOscServer({"/version": slow_reply}) as server:
    config = QLabConfig(host="127.0.0.1", osc_port=server.port, reply_port=0, timeout=1)
    clients = [QLabOscClient(config), QLabOscClient(config)]
    barrier = threading.Barrier(2)
    durations = []
    def request(client):
        barrier.wait()
        started = time.monotonic()
        client.request("/version")
        durations.append(time.monotonic() - started)
    threads = [threading.Thread(target=request, args=(client,)) for client in clients]
    overall = time.monotonic()
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    elapsed = time.monotonic() - overall
    print("requests=", server.received)
    print("elapsed_seconds=", round(elapsed, 3))
    print("request_durations=", sorted(round(value, 3) for value in durations))
PY

/usr/bin/time -p .venv/bin/python - <<'PY'
import runpy
import sys
import threading
import time
sys.path.insert(0, "src")
from qlab_mcp.config import QLabConfig
from qlab_mcp.osc.client import QLabOscClient

FakeQlabOscServer = runpy.run_path("tests/test_qlab_reader.py")["FakeQlabOscServer"]

def slow_reply(_message):
    time.sleep(0.1)
    return "ok"

with FakeQlabOscServer({"/version": slow_reply}) as server:
    config = QLabConfig(host="127.0.0.1", osc_port=server.port, reply_port=0, timeout=1)
    clients = [QLabOscClient(config), QLabOscClient(config)]
    barrier = threading.Barrier(2)
    durations = []
    def request(client):
        barrier.wait()
        started = time.monotonic()
        client.request("/version")
        durations.append(time.monotonic() - started)
    threads = [threading.Thread(target=request, args=(client,)) for client in clients]
    overall = time.monotonic()
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    elapsed = time.monotonic() - overall
    print("requests=", server.received)
    print("elapsed_seconds=", round(elapsed, 3))
    print("request_durations=", sorted(round(value, 3) for value in durations))
PY

/usr/bin/time -p .venv/bin/python - <<'PY'
import json
import socket
import sys
import threading
sys.path.insert(0, "src")
from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError
from qlab_mcp.osc import decode_message, encode_message
from qlab_mcp.osc.client import QLabOscClient

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(("127.0.0.1", 0))
server_port = server.getsockname()[1]
probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
probe.bind(("127.0.0.1", 0))
reply_port = probe.getsockname()[1]
probe.close()

def reply(value):
    return encode_message("/reply/version", json.dumps({"status": "ok", "data": value}))

def serve():
    first, first_addr = server.recvfrom(65535)
    assert decode_message(first).address == "/version"
    second, second_addr = server.recvfrom(65535)
    assert decode_message(second).address == "/version"
    assert first_addr == second_addr
    server.sendto(reply("stale-first-reply"), second_addr)
    server.sendto(reply("fresh-second-reply"), second_addr)

thread = threading.Thread(target=serve)
thread.start()
client = QLabOscClient(QLabConfig(host="127.0.0.1", osc_port=server_port, reply_port=reply_port, timeout=0.3))
try:
    client.request("/version", reply_timeout=0.05)
except OscTimeoutError:
    print("first_request= timed_out")
second = client.request("/version", reply_timeout=0.3)
print("second_request_data=", second.data)
thread.join(1)
server.close()
PY

nl -ba src/qlab_mcp/write/operations.py | sed -n '520,615p'; nl -ba src/qlab_mcp/write/operations.py | sed -n '2150,2190p'; nl -ba src/qlab_mcp/write/operations.py | sed -n '2390,2525p'; nl -ba src/qlab_mcp/write/operations.py | sed -n '2675,2710p'; nl -ba src/qlab_mcp/write/operations.py | sed -n '6340,6390p'; nl -ba tests/test_qlab_reader.py | sed -n '950,1155p'

nl -ba src/qlab_mcp/server.py | tail -n 60; rg -n "def main|mcp\.run|lifespan|shutdown|close\(|disconnect|udpKeepAlive|forgetMeNot|updates" src/qlab_mcp tests | head -n 400; rg -n "QLAB_TIMEOUT|QLAB_CACHE_TTL|reply_timeout|UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS|AFTER_READ|sleep\(" src/qlab_mcp/write src/qlab_mcp | head -n 500

nl -ba tests/test_qlab_reader.py | sed -n '600,635p'; rg -n "request\(.*reply_timeout|reply_timeout=" tests/test_osc.py tests/test_qlab_reader.py tests/test_write_mode.py | head -n 120; rg -n "_request_data_with_tcp_fallback\(|tcp_fallback_on_timeout=True" src/qlab_mcp | sort

rg -n "class Tool|timeout.*tool|tool\.timeout|fail_after|move_on_after|CancelledError|cancel_scope|run_sync|to_thread" .venv/lib/python*/site-packages/fastmcp .venv/lib/python*/site-packages/mcp | head -n 500

find .venv/lib -maxdepth 4 -type d -name 'fastmcp' -o -name 'mcp' | head -n 40; .venv/bin/python -c 'import fastmcp,inspect; print(fastmcp.__file__)'

rg -uuu -n "timeout|CancelledError|cancel_scope|run_sync|to_thread" .venv/lib/python3.14/site-packages/fastmcp/tools .venv/lib/python3.14/site-packages/fastmcp/server | head -n 500

nl -ba .venv/lib/python3.14/site-packages/fastmcp/tools/function_tool.py | sed -n '80,115p'; nl -ba .venv/lib/python3.14/site-packages/fastmcp/tools/function_tool.py | sed -n '210,245p'; nl -ba .venv/lib/python3.14/site-packages/fastmcp/tools/function_tool.py | sed -n '270,335p'

rg -uuu -n "def call_sync_fn_in_threadpool|call_sync_fn_in_threadpool" .venv/lib/python3.14/site-packages/fastmcp | head -n 80; rg -uuu -n "def without_injected_parameters|run_in_thread" .venv/lib/python3.14/site-packages/fastmcp/server/dependencies.py | head -n 120

nl -ba .venv/lib/python3.14/site-packages/fastmcp/utilities/async_utils.py | sed -n '1,70p'; nl -ba .venv/lib/python3.14/site-packages/fastmcp/server/dependencies.py | sed -n '539,610p'; .venv/bin/python -c 'import fastmcp; print(fastmcp.__version__)'

/usr/bin/time -p .venv/bin/python - <<'PY'
import anyio
import time
from fastmcp import FastMCP

mcp = FastMCP("timeout-probe")
@mcp.tool(timeout=0.05)
def slow_sync() -> str:
    time.sleep(0.2)
    return "finished"

async def main():
    tool = await mcp.get_tool("slow_sync")
    started = time.monotonic()
    try:
        await tool.run({})
    except Exception as exc:
        print("exception=", type(exc).__name__, str(exc))
    print("elapsed_seconds=", round(time.monotonic() - started, 3))

anyio.run(main)
PY

/usr/bin/time -p .venv/bin/python - <<'PY'
import anyio
import time
from fastmcp import FastMCP

mcp = FastMCP("timeout-probe")
@mcp.tool(timeout=0.05)
def slow_sync() -> str:
    time.sleep(0.2)
    return "finished"

async def main():
    tool = await mcp.get_tool("slow_sync")
    started = time.monotonic()
    try:
        result = await tool.run({})
        print("result_content=", result.content[0].text)
    except Exception as exc:
        print("exception=", type(exc).__name__, str(exc))
    print("elapsed_seconds=", round(time.monotonic() - started, 3))

anyio.run(main)
PY

nl -ba src/qlab_mcp/runtime/connection.py | sed -n '40,220p'; nl -ba src/qlab_mcp/runtime/connection.py | sed -n '250,430p'; nl -ba src/qlab_mcp/runtime/connection.py | sed -n '540,690p'; nl -ba src/qlab_mcp/settings/workspace.py | sed -n '225,270p'

rg -n -i "without passcode|no passcode|passcode-less|passcodeless|QLAB_PASSCODE" README.md docs/current docs/guides | head -n 250; rg -n "class ReadCache|clear.*in.flight|stale.*cache|cache.*race|repopulat|expires_at" tests src docs | head -n 250

nl -ba README.md | sed -n '45,70p'; nl -ba src/qlab_mcp/cues/query.py | sed -n '260,340p'; nl -ba src/qlab_mcp/cues/details.py | sed -n '160,340p'

rg -n "def _chunk_keys|MAX_.*KEY|VALUES.*KEY|chunk" src/qlab_mcp/allowlist.py src/qlab_mcp/cues src/qlab_mcp/qlab.py | head -n 120; nl -ba src/qlab_mcp/allowlist.py | sed -n '630,700p'; rg -n "def _chunk_keys" src/qlab_mcp -n

nl -ba src/qlab_mcp/cues/details.py | sed -n '1,55p'; nl -ba src/qlab_mcp/cues/query.py | sed -n '100,125p'; nl -ba src/qlab_mcp/write/timeouts.py

nl -ba src/qlab_mcp/write/operations.py | sed -n '11635,11755p'; nl -ba src/qlab_mcp/write/moves.py | sed -n '240,385p'; nl -ba src/qlab_mcp/write/deletes.py | sed -n '225,310p'

git status --short; git diff -- src/qlab_mcp/osc/client.py src/qlab_mcp/osc/messages.py src/qlab_mcp/runtime/read_cache.py src/qlab_mcp/qlab.py src/qlab_mcp/server.py tests/test_osc.py tests/test_qlab_reader.py
```
