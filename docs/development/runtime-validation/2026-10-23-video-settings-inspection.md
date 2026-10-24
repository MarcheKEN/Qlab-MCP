# Saved video settings inspection — 2026-10-23

Baseline: local QLab 5.5.10/build 5510; authorized `mcp_prueba.qlab5`
fixture, UUID `95F0A03D-140E-4673-974A-E76748EBB023`.

## Native observations

- The existing connected MCP OSC overview and passive QLab Settings observation
  both reported 12 stages, five output routes and three input patches.
- The new source implementation was called through an in-process FastMCP Client
  against QLab. An initial sandbox attempt could not access native/OSC services;
  the authorized unsandboxed repeat completed in approximately 1.5 seconds.
- The saved archive returned nine stages, five routes, three CameraPatch records
  and one configured NDI destination. The document reported unsaved changes;
  the tool retained separate live and saved sources with `possibly_stale` freshness.
- Stage geometry, viewport layer, nested regions, control points, edge blends,
  route layout and NDI settings were decoded. No decode diagnostics occurred in
  this fixture. Direct archive inspection verified stage-to-route references.
- QLab's Video Outputs page agreed on representative dimensions: Cuadro Superior
  960×110, inferior centro 445×230 and Stage 9 2940×1912. Output Devices showed
  the built-in Retina display and NDI 1920×1080, 30 fps, two audio channels,
  48 kHz, buffer size 512. The saved destination list describes workspace virtual
  configuration, not this process-wide detected-device list.
- All five route Show switches were off. Settings was closed with Done after
  observation; no Monitor, capture, cue or output was activated.
- Workspace bytes remained SHA-256
  `30cddd67a25d115ce27aa2c08b17570fe8581b558c0cdb0fc68222805fced554`
  before and after the call. No Save, Close, Open or setter was used.

## Limits

The native sample does not validate every format, mask variant or physical video
endpoint. The 12-live/9-saved distinction is observed; no claim is made that the
entire in-memory state equals the saved archive. The connected MCP process must
be restarted to load the changed schema and implementation.

## Exact stage and route follow-up

The source FastMCP client read Cuadro Superior by UUID with limit 10. The
saved stage yielded 109 geometry entries; its next request retained the file
SHA-256 and successfully returned offset 10. The exact Output 1 route also
returned saved configuration. Both reported `needs_save` for the already dirty
document. The SHA-256 above remained unchanged. This exercised source code
through FastMCP; the attached MCP needs another restart for the new detail
arguments. No editing or global device inventory was added.


## Stage inspection follow-up

Source FastMCP Client acceptance against QLab 5.5.10/build 5510 read the exact
`Cuadro Superior` stage. Current inspection returned Perspective (raw code 3),
lower-left (-480,-55), upper-right (480,55), size 960x110, grid off, region guide
off and the shared Output 5 route guides off. All 129 saved geometry leaves fit
on the default page. The document was clean at this later observation; its saved
SHA-256 was `7170baaf3db4401f977400568ceab433eb524ec7b544de3f0b94f689029c1139`
before and after. No Save/Close/Open, setter, cue or output activation was used.
The earlier dirty observation above describes a different snapshot.

Synthetic archive regression checks additionally exercise Linear, Bézier,
Perspective and unknown warp codes, mask aliases, nested regions, shared point
links, shadow points, unknown fields, dirty documents and hash continuations.
Native acceptance of newly created masked/Linear/Bézier configurations was not
repeated in this follow-up; synthetic coverage is not a native round-trip claim.

The added `inspection` response is tested through source FastMCP; the attached MCP
process must restart to load these latest changes. Shared OSC payload validation
now accepts only actual boolean values for region enableGrid/enableGuide, matching
the existing dedicated region reader. Supplemental UUIDs are normalized, queries
are bounded and missing values remain null with explicit continuation requests.
