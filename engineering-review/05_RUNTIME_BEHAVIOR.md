# 05 — Runtime Behavior and Reliability

## Verdict

The transport is intentionally simple and usually leak-resistant: one socket/connection per request, no background receivers, no pending-request registry, no mutating retry, and strict sender/address/reply parsing. Three reproduced defects are more important than adding features:

1. **P0:** a late reply for an identical UDP address can be accepted by the next request.
2. **P1:** FastMCP decorator timeouts do not preempt these synchronous tool handlers.
3. **P1:** `ReadCache.clear()` can be undone by a read already in flight, restoring stale pre-write data.

## Confirmed defects

### P0 — Late identical UDP reply misattribution

**Evidence:** a controlled loopback reproduction made request 1 to `/version` time out, delayed its reply, then issued request 2 to `/version`. Request 2 returned the first request's payload: `second_request_data=stale-first-reply`.

**Cause:** each request binds the configured fixed reply port, but matching uses sender IP and invoked OSC address only (`osc/client.py:102-192,237-264`). OSC supplies no request ID. A late or duplicate reply for the same address is indistinguishable from the current request.

**Impact:** a fresh-looking read can be stale. This is especially serious when readback decides whether a timed-out setter succeeded.

**Next step:** add the reproducer as a regression test before choosing mitigation. TCP-per-request inherently isolates frames; UDP needs a bounded post-timeout strategy. Removing the lock is not a fix.

### P1 — Advertised tool timeout does not cancel synchronous work

**Evidence:** a FastMCP 3.3.1 probe registered a synchronous tool with `timeout=0.05`; it slept 0.2 seconds and returned normally after 0.203 seconds.

**Cause:** synchronous functions run in an AnyIO worker thread. Cancellation of the awaiting task does not preempt the running thread (`fastmcp/tools/function_tool.py:284-325`, `fastmcp/utilities/async_utils.py:26-34`). All public handlers are synchronous (`server.py:348-1119`).

**Impact:** client disconnect or advertised timeout cannot stop a long read or write already executing. The internal 90-second edit budget helps but is not a universal deadline; read tools can continue well beyond client expectations.

**Next step:** treat decorator timeouts as client metadata, not a safety boundary. Add end-to-end cancellation tests and cooperative internal deadlines, especially around broad cue scans and fallback property reads.

### P1 — Cache invalidation race

**Evidence:** a controlled threaded `ReadCache` probe called `clear()` while the owner factory was active. The factory completed afterward and repopulated `post_clear_value=stale`.

**Cause:** `clear()` removes/wakes in-flight entries, but the owner unconditionally stores its value at `runtime/read_cache.py:66-70`.

**Impact:** edit paths clear the cache before and after mutation (`write/operations.py:2172,2505,2699`), but a pre-write read completing after the final clear can reinsert stale data for the default 10-second TTL.

**Small fix:** add a cache generation counter. `clear()` increments it; owners store only when their captured generation still matches. Add one focused race test.

## Real QLab timing

Workspace: `mcp_prueba.qlab5`, QLab 5.5.10, 185 cue items, localhost UDP.

| Scenario | Result |
| --- | --- |
| 5 simultaneous identical `health` detail reads for one Memo | 27 ms total; all returned the same UUID and `ok` |
| 10 rapid sequential identical detail reads | 123 ms total; 10–20 ms each |
| 5 simultaneous unrelated reads (connection, overview, status, query, detail) | 5,343 ms total; detail 20 ms, other calls 5,081–5,343 ms |
| The same 5 unrelated reads sequentially | 500 ms total; 23–201 ms each |

Identical calls benefit from single-flight/cache behavior. Unrelated concurrent work was **10.7× slower** than the same calls sequentially. The production endpoint lock serializes individual UDP exchanges, while multi-round-trip high-level calls interleave and can reach full timeout windows. This is confirmed behavior on the current workspace, not a general throughput benchmark.

The invalid dry-run probes also exposed an order-of-work concern: local validation failures took 2.1–4.3 seconds, and an empty profile falling back to `common` took 6.0 seconds. Validation that does not require QLab should occur before connection/readiness work where safety semantics permit.

## Concurrency, matching and state

### Current strengths

- One class-global lock per `(host, osc_port, reply_port)` prevents simultaneous use of the same configured UDP endpoint (`osc/client.py:86-121`).
- UDP and TCP resources are context-managed per request. Exceptions release the lock and close sockets.
- The receive deadline is monotonic and includes discarded unrelated packets.
- Qualified workspace addresses require exact matching; unqualified queries intentionally accept matching workspace-qualified suffixes.
- Sender IP is validated against the configured host.
- Non-reply packets, unrelated addresses, malformed OSC/JSON, non-object JSON and missing string `status` are rejected.
- QLab error/denied statuses become `QLabReplyError`.
- Mutating setters are never retried. Fresh readback or convergence polling decides success after timeout.
- No background task or pending-request dictionary can leak at shutdown.

### Current risks

- The endpoint lock models the remote tuple, not the local fixed reply port. Two different remote configurations sharing one local port can get different locks and collide at bind.
- Sender source port is not checked; another local process at the allowed IP could inject a matching reply.
- DNS resolution occurs inside the receive loop and is outside the OSC monotonic deadline.
- The JSON reply's documented `address` field is ignored.
- Bind/send/connect `OSError` values are not normalized consistently as transport errors.
- `_locks` is unbounded; dynamic endpoint configurations accumulate entries.
- `_entries` is unbounded; expired cache keys are removed only when that exact key is requested or the whole cache is cleared.
- TTL is calculated before a potentially slow factory runs, so a value can be expired immediately when stored.
- Single-flight waiters use unbounded `Event.wait()`.

## Timeout, retry and round-trip behavior

- Ordinary UDP request: one send/reply. The first authenticated workspace request on a client adds `/connect`.
- Every MCP invocation creates a fresh client, so authenticated tools reconnect once per invocation and reuse connection state only inside that tool.
- No generic retry exists. This is correct for setters.
- Known large reads try UDP, then TCP only after the full UDP timeout (`qlab.py:81+`). With passcode, worst case can consume UDP wait, TCP connect, TCP `/connect` reply, and TCP query reply as separate windows.
- A failed `valuesForKeys` detail read can fall back to many sequential property requests (`cues/details.py:162+`), amplifying an outage.
- Move/Delete use fresh structural convergence polling. Edit uses readback delays of 0.2, 0.5 and 1.0 seconds and never resends the setter.

## Restart, updates and cleanup

No `/disconnect`, `/udpKeepAlive`, `/updates`, reconnect hook, or shutdown lifecycle exists. Local QLab documentation says idle UDP clients are disconnected after 61 seconds and exposes update/disconnect messages. Because each normal tool creates a new client, stale connection state is usually short-lived; a long-running high-level tool can still retain it.

The lack of subscriptions means external workspace/cue changes rely on TTL expiry. `/workspaces` may remain stale for up to 10 seconds after workspace close/restart.

## Existing test evidence

Focused transport/cache set: 14 passed in 0.12 seconds.

Strong coverage includes:

- OSC encode/decode and SLIP escaping.
- Basic reply parsing and address matching.
- UDP loopback and unreachable timeout.
- Cache reuse/disablement, live/sensitive bypass and identical-call single-flight.
- UDP-to-TCP fallback selection for large reads.
- TCP reconnect/authentication per socket.
- Broad setter-timeout/fresh-readback behavior.

Missing regression coverage:

- Late/duplicate identical replies.
- Actual receive-loop handling of updates and unrelated datagrams.
- Wrong sender source port.
- Out-of-order concurrent calls.
- `clear()` versus active cache owner.
- Cache bound/expiry sweep.
- MCP cancellation and real timeout enforcement.
- TCP loopback fragmentation, multiple/malformed SLIP frames, unrelated frames and close/reset cases.
- QLab restart/workspace close/reconnect.
- Fixed reply-port collision.

## Recommended order

1. P0 late-identical-reply regression and bounded mitigation.
2. P1 cache generation invalidation.
3. P1 cooperative overall deadlines and cancellation semantics.
4. P1 real UDP/TCP contract tests.
5. P2 cache/lock bounding and TTL-at-completion.
6. Add connection invalidation/subscriptions only after real QLab evidence justifies the added lifecycle.

Keep socket-per-request and no-setter-retry unless measurements show a clear reason to change them.
