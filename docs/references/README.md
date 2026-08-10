# References

Imported QLab source material:

- [QLab OSC Dictionary](qlab_osc_dictionary.md)
- [OSC Queries](osc_queries.md)
- [QLab AppleScript Dictionary](qlab_applescript_dictionary.md)
- [`manifest.json`](manifest.json) records each local file's source URL, version scope,
  provenance limits, and SHA-256 checksum.

Keep these content-immutable unless regenerating from the upstream source.
The manifest and its checksum tests define the local imported snapshot; the
official QLab documentation remains authoritative when versions differ.

The current copies describe QLab 5, but their exact upstream patch version and
retrieval date are unknown. Git history first imports them on 2026-05-15; that
date is an inferred repository provenance bound, not a claimed retrieval date.
Do not infer QLab 5.6.x runtime support from these references.

The AppleScript Dictionary snapshot also retains its source HTML at
[`docs/sources/qlab-5-applescript/applescript_dictionary_v5.local.html`](../sources/qlab-5-applescript/applescript_dictionary_v5.local.html)
so the Markdown can be regenerated deterministically.
