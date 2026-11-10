# Coverage

Write-registry coverage (not a census of the specialized read tools or saved
archive editors):

- [OSC coverage snapshot](osc_coverage_snapshot.md)

For the public read inventory and its deliberate exclusions, use the
[tool catalogue](../../user/tools.md) and [current state](../current-state.md).

The current public surface is 91 tools: 54 reads and 37 gated writes.
`qlab_edit_light_patch` and `qlab_edit_saved_audio_patches` use guarded archive
transactions outside the OSC setter registry above; their workflows distinguish
saved-file verification from OSC observations. Audio patch/effect writes remain
limited to operations explicitly accepted by the QLab 5.5.10 fixtures. Audio Maps,
AudioUnit identities outside the validated SnapTune cue and
AUDynamicsProcessor output-bus fixtures, and unsupported patch fields remain
read-only or blocked. USB-DMX assignments store explicit device identities without proving
detection, availability or output; compatible-device validation remains pending.
Definition creation supports scalar, RGB/lime, CMY, HSI, Pan/Tilt and acyclic
One-to-Many controls; unknown variants remain blocked. Existing historical
matrices do not imply coverage of these writers.

Closed phase matrices are kept in the
[coverage archive](../../archive/coverage/). The official imported source is
the [QLab OSC dictionary](../../references/qlab_osc_dictionary.md).
