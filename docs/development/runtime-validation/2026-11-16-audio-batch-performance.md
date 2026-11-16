# Audio batch and archive performance — QLab 5.5.10

The audio cue batch preflight now reads workspace volume limits once per phase.
In a deterministic simulated reader, dry-run limit requests for 1, 10 and 50
cues changed from 2, 20 and 100 to 2, 2 and 2. Confirmed execution changed from
6, 60 and 300 to 6, 24 and 104 respectively. The fresh check before each
setter remains; no snapshot is retained between calls. These counts are not
latency measurements from QLab.

Patch pagination now copies the requested matrix page, not discarded cells or
bus details. A local in-memory measurement with 4,096 cells and a 128-cell page
changed from about 4.31 ms to 0.14 ms per call (200 iterations); a single-call
`tracemalloc` peak fell from about 1,059 KiB to 21 KiB. This is not an
end-to-end QLab benchmark. Baseline-only archive plans skip effect capture;
operations, including no-ops, still capture effects and retain postconditions.

On a temporary copy in QLab 5.5.10/build 5510, the updated code changed Audio
Volume Limits to -80/+6 dB, Playlist crossfade duration to 2 seconds and a Mic
crosspoint to -6 dB. The archive transactions reported verified effect
preservation; after saving and reopening, fresh OSC reads matched those values.
The original workspace hash remained unchanged. No cue was run, and no capture,
playback or physical output was tested.
