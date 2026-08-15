# OSC navigation

## Correlation and transport concepts

The source documents UDP on port 53000, UDP replies on port 53001 by default, and TCP with SLIP. A message arriving on a port may be received by every open workspace listening on that port; workspace-qualified paths or distinct ports isolate the destination.

## Replies and updates

Reply:

```text
/reply/{/invoked/osc/method} json_string
```

The JSON may include `workspace_id`, `address`, `status` (`ok`, `error`, `denied`), and `data`. Status notifications use `/update/workspace/{workspace_id}` and cue/cue list variants; enable them with `/updates 1` and stop them with `/updates 0`.

## Access and booleans

Read each entry's table: `view`, `edit`, `control`, `query`, `+/-?`, `Live`. QLab accepts OSC booleans, numbers, and strings according to the source rules; `toggle` exists only where the dictionary permits it.

## Targets and variants

- Cue number: `/cue/{cue_number}/...`.
- Selected cue: `/cue/selected/...` when the entry permits it.
- Unique ID and workspace-qualified address: use exactly the documented forms.
- Live: append `/live` at the end.
- Increment/decrement: use `/+` or `/-` and preserve the `/+/live` order.

These rules are for navigation; always copy the actual signature from the original entry.
