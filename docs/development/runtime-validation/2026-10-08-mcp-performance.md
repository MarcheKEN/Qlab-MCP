# MCP performance — 2026-10-08

## Scope

Read-only measurements against the installed MCP and the open QLab 5.5.10
workspace, followed by four measured source optimizations. No QLab mutations,
cue execution, new dependencies, configuration changes or release.
The first measurements preceded a connector reload. The user then restarted
the connector and the same reads were measured again; see the follow-up below.
The subsequent catalogue/expiry changes were measured locally. The user
restarted again and live reads were rechecked; see the final verification below.
[Numeric evidence](2026-10-08-mcp-performance.json).

## Live baseline

Three sequential calls per tool; wall time includes the connector and QLab.
These small samples describe this local workspace, not a latency guarantee.

| Read | Median ms | Range ms |
|---|---:|---:|
| Connection | 20 | 17–23 |
| Cue Lists | 26 | 26–26 |
| Audio detail | 70 | 70–71 |
| Control detail | 68 | 67–78 |
| Video settings | 67 | 65–72 |
| Video detail | 87 | 84–88 |
| Overview with bounded tree and minimal index | 116 | 108–233 |

Video detail retains the previously observed `infiniteLoop` validation error
for the image cue. Overview reports partial coverage. These responses are not
counted as complete correctness validations. Initial overview requests with
invalid depth/profile were excluded from successful-call timings.
The overview returned approximately 474,000 serialized JSON characters,
including both text and structured representations. Payload size is distinct
from OSC bytes and tool latency.

## Optimization 1: reuse field validators

`cues/family.py` and `cues/lists.py` rebuilt a Pydantic `TypeAdapter` for every
observed field on every read. Profiling 100 fixture reads per family attributed
roughly 84–90% of CPU time to section parsing, predominantly schema creation.
Both parsers now share a bounded 512-entry cache keyed by model class and field.
It stores compiled validators, never observed values or QLab replies.
Fresh identity checks, OSC reads, strict types, aliases, field errors,
unavailable fields and partial-result behavior remain in place.

Using existing Audio, Video, Text and Cue List fixtures: one warm-up, 200 reader
samples and 50 `Client(mcp)` round trips per case, in separate before/after
processes on the same machine. Typed payloads excluding redaction bookkeeping
and the exact OSC request traces match before/after. Fixtures deliberately
include missing fields; their partial coverage is unchanged.

| Read | Reader before → after ms | CPU path reduction | MCP before → after ms |
|---|---:|---:|---:|
| Audio | 1.990 → 0.428 | 78.5% | 95.50 → 93.45 |
| Video | 4.609 → 0.490 | 89.4% | 129.25 → 124.05 |
| Text | 3.975 → 0.646 | 83.8% | 142.53 → 138.89 |
| Cue List | 1.518 → 0.127 | 91.7% | 79.96 → 78.87 |

The full simulated MCP improvement is only 1.4–4.0%; do not present the reader
CPU improvement as an equivalent whole-tool speedup. Initial reads can still
pay schema compilation costs. No live-response TTL was extended.

## Optimization 2: avoid copying unescaped TCP frames

`osc/client.py::_slip_decode` previously walked every byte in Python even when
no SLIP escapes were present. It now returns the same immutable bytes directly
when there is no escape byte. Escaped frames retain the existing decoder and
malformed-escape errors. A byte-value round-trip regression covers all 256
values; existing transport regressions cover session preparation, malformed
data, deadlines, acknowledgements and no resend.

Fifty samples per variant and size, using identical valid OSC/SLIP JSON replies
split into chunks of at most 65,535 bytes. The simulated socket excludes network,
authentication and TCP connection time; it measures reply framing/parsing.

| JSON string size | Decoder before → after ms | Whole reply parse before → after ms |
|---|---:|---:|
| 4 KiB | 0.240 → 0.0003 | 0.274 → 0.016 |
| 128 KiB | 7.637 → 0.0045 | 7.928 → 0.228 |
| 512 KiB | 30.517 → 0.0161 | 31.589 → 0.928 |

Escaped frames do not receive this fast path. These numbers do not imply that
every QLab or MCP response is 97% faster.

## Remaining costs and next steps

Post-change profiling of `Client(mcp)` still concentrates time in MCP SDK
`jsonschema.validate` and its repeated `check_schema` work on server/client
output schemas. This is visible in the installed dependency source; these
dependencies and validation checks were not patched or disabled.
The local source catalogue contains 73 tools, approximately 727,000 serialized
schema characters; its first `list_tools()` observation took 167 ms. That is
discovery cost, not repeated QLab read time.

Prefer scoped cue details and bounded inventories for agent workflows that
need only a few cues. A future dependency-level investigation can measure
reusing compiled JSON Schema validators while preserving validation. Network
waits, QLab processing and timed-out optional endpoints require separate
evidence; this change does not remove checks or shorten error timeouts.

## Verification and reproduction

273 focused read/cache tests passed. 56 OSC/transport tests and 26 subtests
passed. Full suite: 1629 passed, 35 skipped, 61 subtests passed in 49.90 s.
Socket tests used permitted local simulated servers. Source `Client(mcp)`
listing still exposes 73 tools. `git diff --check` passed.

Reproduce the reader CPU measurement with existing fixtures, without QLab:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python - <<'PY'
import statistics, time
from qlab_mcp.qlab import QLabReader
from test_visual_cue_tools import fixture, WS, FIRST
reader = QLabReader(fixture('video'))
reader.get_video_cue_details(WS, FIRST)
times = []
for _ in range(200):
    start = time.perf_counter()
    reader.get_video_cue_details(WS, FIRST)
    times.append((time.perf_counter() - start) * 1000)
print('Median reader milliseconds:', statistics.median(times))
PY
```

## Follow-up after the user restarted the connector

The same QLab 5.5.10 workspace and cue UUIDs were resolved through MCP.
Ten sequential samples per tool, read-only, with the same arguments as the
initial three-sample baseline:

| Read | Initial median ms | After restart median ms | After restart range ms |
|---|---:|---:|---:|
| Connection | 20 | 19 | 17–20 |
| Cue Lists | 26 | 25 | 24–26 |
| Audio detail | 70 | 67 | 65–139 |
| Control detail | 68 | 62 | 60–67 |
| Video settings | 67 | 50.5 | 49–52 |
| Video detail | 87 | 77 | 75–81 |
| Bounded overview | 116 | 96 | 91–114 |

All calls returned without MCP transport errors. Image `infiniteLoop` and
overview partial coverage remain visible. No setters, cue execution or UI edits
were used. These small samples show lower medians, not a controlled proof that
all of the difference comes from code; the Audio outlier also shows variability.

### Additional source change: avoid unnecessary expiry scans

`ReadCache` now tracks the earliest possible expiry under its existing lock.
It scans for expired entries only when that time arrives. TTLs still start after
factory completion; expired untouched entries are pruned, short TTLs inserted
after long TTLs are respected, and `clear()` still invalidates in-flight owners.
No OSC value is retained longer and writer readbacks remain fresh.

Five batches of 1,000 accesses per size, before/after, with a 120-second TTL to
prevent expiry inside this stress measurement:

| Existing entries | Cache hit before → after µs | Cached reader before → after µs |
|---|---:|---:|
| 100 | 2.616 → 0.371 | 3.923 → 1.612 |
| 1,000 | 21.796 → 0.387 | 23.694 → 1.663 |
| 5,000 | 104.168 → 0.376 | 106.838 → 1.636 |

The reader uses the existing Cue List fixture; identical results and one OSC
factory call were checked. These are cache stress measurements, not a claim
that the open workspace currently has 5,000 cache entries or that whole tools
become 277 times faster. An actual expiry still requires a scan.

### Additional source change: cache the static tool catalogue

The installed FastMCP `ResponseCachingMiddleware` is configured in the server
constructor, before schema dereferencing, to cache only `tools/list` for five
minutes. Caching is explicitly disabled for tool calls, all resource operations
and prompts. Its default one-MiB item limit bounds catalogue storage.
The current catalogue is static for the process; changing registered tools
requires a restart or waiting for catalogue expiry. Tool inputs, outputs,
readiness, tokens and setter execution are not cached by this middleware.
[FastMCP middleware reference](https://gofastmcp.com/python-sdk/fastmcp-server-middleware-caching).

Same source fixtures and `Client(mcp)`, separate before/after processes:

| Measurement | Before median ms | After median ms | Samples per variant |
|---|---:|---:|---:|
| Repeated catalogue listing | 225.52 | 20.03 | 19 |
| First Audio read by a new client, catalogue warm on server | 294.91 | 117.57 | 10 |
| Audio read on an existing client | 94.41 | 94.90 | 24 |
| Process import | 2,127.89 | 2,256.20 | 5 |

Catalogue schemas and fixture responses have identical SHA-256 hashes. A second
experiment alternated uncached/cached listings in one process: 173.54 → 24.64 ms,
20 samples per variant. Initial catalogue generation still incurs the work and
cache population; the separate cold listing observations were 170.84/261.41 ms.
There is no demonstrated cold-start improvement. Import profiling attributes
approximately 29 ms to loading the native cache middleware; CPU contention
and run-to-run variation also affect the separate process measurements.

The SDK output-schema check remains a substantial cost for an already connected
client. The official upstream [validator cache change](https://github.com/modelcontextprotocol/python-sdk/pull/3134)
addresses client-side compilation, while the [v1.30 client source](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/src/mcp/client/session.py)
still uses one-shot validation. No SDK upgrade, monkeypatch or validation bypass was
introduced. Response caching is not used to hide errors or repeated-token checks.

### Follow-up verification and remaining scope

345 focused reader/writer tests and 35 subtests passed; nine focused cache and
catalogue checks passed, including invalid output rejection with a warm catalogue.
Full suite: 1632 passed, 35 skipped, 61 subtests passed in 30.65 s. A sandboxed
reader test attempt could not bind local simulator sockets; the permitted
localhost run passed. All 73 public tools and their catalogue schemas are preserved.
`git diff --check` and authored documentation links passed.

At this stage the catalogue/expiry changes still required a connector restart.
The next section records the subsequent live verification. Playback performance,
real edit throughput and long audio-file analysis remain outside this task.

## Final live verification after the latest restart

The user restarted the installed connector again. MCP resolved the same
`redacted-workspace-6b31c91e.qlab5`, QLab 5.5.10, one open workspace and Edit Mode. Fourteen
read-only tools were sampled ten times each, sequentially. Timing uses
`Date.now()` around the awaited installed MCP call, with one-millisecond
resolution. First calls in each series are not process cold-start measurements.

| Read | Previous reload median ms | Latest median ms | Latest range ms |
|---|---:|---:|---:|
| Connection | 19 | 19.5 | 19–23 |
| Cue Lists | 25 | 25 | 24–31 |
| Audio detail | 67 | 67 | 66–86 |
| Control detail | 62 | 62 | 61–67 |
| Video settings | 50.5 | 51 | 49–52 |
| Video detail | 77 | 76.5 | 75–87 |
| Bounded overview | 96 | 95.5 | 93–164 |

Repeated request medians are effectively unchanged versus the previous reload.
This is consistent with the latest optimizations targeting catalogue discovery
and cache bookkeeping rather than making every already-connected call faster.
No installed connector `tools/list` latency was exposed by these tool calls;
the catalogue speedup above remains a local `Client(mcp)` measurement.

| Additional read | First in series ms | Median ms | Range ms |
|---|---:|---:|---:|
| Write readiness, no setters | 17 | 16 | 15–58 |
| Nine-cue list detail | 53 | 50 | 48–190 |
| Audio inventory in that list | 38 | 22 | 21–38 |
| Light detail | 51 | 46.5 | 45–51 |
| Audio-target Fade detail | 78 | 75 | 73–78 |
| Workspace Audio search | 211 | 58 | 57–211 |
| Workspace status, timecode omitted | 252 | 109.5 | 104–252 |

Overview inspected 427 items across 25 containers; Audio search inspected all
427 and returned 68 matches without truncation. The existing short-lived read
cache remains enabled. Initial lookup work, payload size and scheduling can
affect these timings; ten samples do not establish a reliable tail-latency
guarantee. No MCP transport error or timeout occurred. Image `infiniteLoop`
and overview health coverage still produce their previously documented partial
results, so this does not close those correctness findings.

### Existing batch reads reduce round trips

`qlab_get_cue_details(profile='health')` was measured with 1, 10 and 50 exact
Audio UUIDs, five samples per size. Medians were 6, 16 and 42 ms respectively;
all requested cues succeeded. Fifty sequential individual calls then took
287 ms in total, against the 42 ms batch median. Their returned properties
matched the batch for every cue. These are consecutive safe-profile reads with
the existing cache, not an Inspector-completeness or uncached-network claim.
Use the batch already provided when the requested information fits that profile.

The numeric record contains 205 timed calls: 140 standard reads, 15 validated
batch reads and 50 individual comparison reads. Fifteen earlier batch pilot
calls and one untimed connection check are excluded from those aggregates.
No setters, playback or UI edits were sent. No further source change was
needed for this verification; source regression results remain those above.
The final documentation update passed `git diff --check` and local link checks.
