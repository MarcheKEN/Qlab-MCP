# Light Patch authoring acceptance — 2026-10-20

## Environment and limits

QLab 5.5.10/build 5510 on macOS arm64; one owner-authorized disposable
workspace, plus a temporary peer document for the multiple-workspace case.
The existing workspace's original path was used for final execution.
Private workspaces, process credentials and raw local capture paths are not
published. The writer, typed operations and regression cases are retained in
source; no vendor binary or imported fixture library is committed.

No cues were run. No physical DMX output, device compatibility or show readiness
was tested. QLab reported no supported USB-DMX devices detected. USB evidence
therefore concerns serialization and native acceptance of an explicitly
synthetic serial, not an operational device or emitted packets.

## Native cases

| Case | Observation |
|---|---|
| Nested archive no-change reserialization | QLab reopened the result and preserved workspace identity. |
| Minimal note edit | Reopened; the changed note appeared in MCP readback and the native Light Patch table. |
| Definition creation | Scalar 8-bit, scalar 16-bit and RGB virtual parameter definitions were accepted; used definitions were returned by OSC. |
| Address boundaries | Native table displayed RGB 510–512 and 16-bit 511–512. |
| Art-Net | Native table displayed Net 2, Sub-Net 3, Universes 4 and 5. Final original-path batch also exercised Net 1/Sub-Net 2/Universes 3 and 4. |
| Nested groups | Native patch and OSC showed the parent/subgroup and expected instruments. |
| Internal identifiers | New archived instruments used provisional IDs. Reopen and QLab Save yielded distinct regenerated runtime IDs, corroborating the bounded static decoder observation. IDs are not public identity. |
| USB native reference | Selecting USB in the native editor produced LightDMXUSBInfo with deviceSerial, deviceString, deviceNumUniverses and universe. No device was available to select. |
| USB explicit identity | A deliberately synthetic serial/label and device universe were serialized and accepted on reopen. This does not establish device existence. |
| Public MCP creation | A preview and one execution created two definitions, two instruments and two nested groups on the original path; result verified file replacement, reopen and native patch readback. |
| Latest-source mixed batch | One execution renamed instrument/group/definition, edited instrument/group/definition, deleted instrument/group/definition and created an unpatched instrument. Result was verified. |
| Another document open | Latest-source MCP execution reopened the target with an independently identified peer open; the peer's complete native inventory row was unchanged. The temporary peer was then closed. |
| Cleanup | One batch removed the remaining test instruments, group and definition. Result was verified. Final semantic patch matched the initial snapshot: six instruments, four explicit groups and four stored definitions. |

Across the original-path batches, all twelve public operation actions were
exercised. This is representative acceptance, not every argument permutation.
The temporary peer had a distinct workspace UUID; the public Open contract was
not relaxed to perform the target transaction.

## Problems found and corrected

- Native path comparison could disagree between Foundation `/tmp` paths and
  Python `/private/tmp` canonicalization. Target and expected inventory paths
  now use the same native normalization.
- Scalar Home uses the selected percentage/DMX unit. Percentage permits finite
  values 0–100; raw DMX requires an integer fitting the selected width.
- A two-second Open timeout occurred after file replacement. Fresh inspection
  confirmed the document had opened, but the tool correctly retained uncertain
  recovery. Open now has at least 30 seconds, and a lost acknowledgement can
  be confirmed through one fresh readback without resending the event.
- QLab can mark a reopened document dirty. The result reports that condition;
  it never automatically saves those later changes.
- The exterior patch NSData could be aliased outside Light. The writer now
  clones the root/settings/Light/carrier branch instead of modifying the old
  carrier. In the original-path native run, every object in the preceding
  exterior object-table prefix was preserved exactly.
- Initial-state validation prevented repair of an existing overlap. Reading
  the source is now separate from validating the final proposed patch.
- Native readback now checks used definition manufacturer, default and parameter
  semantics, in addition to instrument identity/properties and group members.
- Optional native filesystem locking no longer prevents importing the read
  server on a platform without fcntl.

## Verification boundaries

Saved-file readback checks routing, parameter encoding, stored definitions and
internal patch relationships. Independent OSC readback checks instruments,
notes, used definitions/defaults/parameters and group membership. OSC does not
expose complete address/output identity or unused-definition inventory, so
those remain file checks. Native accessibility observation corroborated names,
notes, Art-Net fields and address ranges. A screenshot API was unavailable in
the final observation; no pixel-comparison result is claimed.

Light cues, Dashboard MIDI and unrelated settings are preserved. Cue-reference
warnings remain partial and do not block patch rename/delete; operators repair
those references later using other tools. No lighting-command execution proof
is inferred from unchanged saved cue objects.

## Automated verification

The final full macOS suite passed **2,048 tests and 61 subtests**, with **35
skips**. FastMCP inspection succeeded and reported **80 tools**, using the
current environment interpreter explicitly because its CLI wrapper retained
an obsolete interpreter path from an earlier checkout location. The first sandboxed attempts could not use fixture
sockets; the accepted run had local socket access.

Focused synthetic tests cover malformed input, type/range rejection, graph
preservation, no-op and repeated create, final-state repair, default-parameter
preservation, group membership/ranges, overlaps and shared footprints, signed
single-use/expired tokens, stale state, recovery failures, lost acknowledgements,
other documents, dirty state and native-script compilation/normalization.
Failure-phase unit tests do not claim power-loss durability on every filesystem.
