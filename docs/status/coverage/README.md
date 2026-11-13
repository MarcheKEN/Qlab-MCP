# Coverage

Write-registry coverage (not a census of the specialized read tools or saved
archive editors):

- [OSC coverage snapshot](osc_coverage_snapshot.md)

For the public read inventory and its deliberate exclusions, use the
[tool catalogue](../../user/tools.md) and [current state](../current-state.md).

The current public surface is 90 tools: 53 reads and 37 gated writes.
`qlab_edit_light_patch`, the saved-file branch of `qlab_edit_audio_patch`, and
`qlab_edit_workspace_audio_settings` use guarded archive transactions outside
the OSC setter registry above. Audio effect instances are preserved but are not
exposed or editable. Audio Maps, blank patch creation and unsupported patch
fields remain outside the public surface. USB-DMX assignments store explicit device identities without proving
detection, availability or output; compatible-device validation remains pending.
Definition creation supports scalar, RGB/lime, CMY, HSI, Pan/Tilt and acyclic
One-to-Many controls; unknown variants remain blocked. Existing historical
matrices do not imply coverage of these writers.

Closed phase matrices are kept in the
[coverage archive](../../archive/coverage/). The official imported source is
the [QLab OSC dictionary](../../references/qlab_osc_dictionary.md).
