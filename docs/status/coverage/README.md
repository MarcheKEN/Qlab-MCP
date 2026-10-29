# Coverage

Write-registry coverage (not a census of the specialized read tools):

- [OSC coverage snapshot](osc_coverage_snapshot.md)

For the public read inventory and its deliberate exclusions, use the
[tool catalogue](../../user/tools.md) and [current state](../current-state.md).

The current public surface is 80 tools: 49 reads and 31 gated writes. The local
`qlab_edit_light_patch` archive writer is outside the OSC setter registry above;
its [workflow](../../user/agent-workflows.md#edit-the-light-patch) distinguishes
saved-file verification from partial OSC-visible readback. USB-DMX assignments
store explicit device identities without proving detection, availability or
output; compatible-device validation remains pending. Parameter creation is
limited to scalar/RGB.
Existing historical matrices do not imply coverage of this new writer.

Closed phase matrices are kept in the
[coverage archive](../../archive/coverage/). The official imported source is
the [QLab OSC dictionary](../../references/qlab_osc_dictionary.md).
