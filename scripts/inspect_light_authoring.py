"""Read-only evidence for lighting research, not a workspace writer.

Usage: PYTHONPATH=src .venv/bin/python scripts/inspect_light_authoring.py FILE.qlab5
Add --catalogue to inventory installed parameter variants (no vendor JSON export).
Archive objects may be templates or residuals; this is not an active cue inventory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import plistlib

from qlab_mcp.light_patch.archive import Archive, MAX_BYTES
from qlab_mcp.light_patch.catalogue import load_catalogue, read_stable


def prepare_curve_point_sample(data: bytes, cue_id: str, point_index: int, value: float) -> bytes:
    """Offline research only: change one existing Custom control point, no file I/O.

    The caller must close the clean native document and verify identity/recovery
    before installing these bytes. This is not a public MCP write capability.
    """
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Point value must be finite and within 0..1.")
    outer = Archive(data)
    meta = outer.mapping(outer.root)
    if outer.ref(meta.get("QLabBuildNumber")) != 5510 or outer.ref(meta.get("QLabShortVersionString")) != "5.5.10":
        raise ValueError("Research sample requires QLab 5.5.10/build 5510.")
    carrier = outer.ref(meta["cueLists"])
    a = Archive(carrier["NS.data"])
    pending, visited, matches = [a.data["$top"]["root"]], set(), []
    while pending:
        item = pending.pop()
        if isinstance(item, plistlib.UID):
            if item.data in visited:
                continue
            visited.add(item.data)
        item = a.ref(item)
        if isinstance(item, dict):
            if "$class" in item and a.kind(item) == "LightCue" and a.ref(item.get("uniqueID")) == cue_id:
                matches.append(item)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    if len(matches) != 1:
        raise ValueError("Expected one reachable exact Light cue UUID.")
    shape = a.ref(a.ref(a.ref(matches[0]["fade"])["shapes"])["upShape"])
    entries = a.array(shape["shapeEntries"])
    if a.ref(shape["type"]) != 0 or type(point_index) is not int or not 0 < point_index < len(entries) - 1:
        raise ValueError("Sample requires an existing interior Custom curve point.")
    point = entries[point_index]
    if sum(isinstance(obj, dict) and point in obj.get("NS.objects", []) for obj in a.objects) != 1:
        raise ValueError("Shared curve point is outside this narrow research probe.")
    a.ref(point)["v"] = float(value)
    carrier["NS.data"] = a.dump()
    return outer.dump()


def inspect_curves(data: bytes) -> dict:
    """Follow only the known curve fields; never recursively expand cyclic UIDs."""
    pending = [(data, "outer")]
    seen, samples = set(), []
    decoded_bytes = 0
    while pending:
        payload, location = pending.pop()
        digest = hashlib.sha256(payload).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        decoded_bytes += len(payload)
        if len(seen) > 64 or decoded_bytes > 2 * MAX_BYTES:
            raise ValueError("Nested archive research budget exceeded.")
        a = Archive(payload)
        for index, value in enumerate(a.objects):
            if not isinstance(value, dict):
                continue
            for key, nested in value.items():
                if isinstance(nested, bytes) and nested.startswith(b"bplist00"):
                    pending.append((nested, f"{location}/{index}/{key}"))
            if "$class" not in value or a.kind(value) != "LightCue":
                continue
            if len(samples) >= 1000:
                raise ValueError("Light cue research sample budget exceeded.")
            fade = a.ref(value.get("fade"))
            shapes = a.ref(fade.get("shapes")) if isinstance(fade, dict) else None
            if not isinstance(shapes, dict):
                continue
            result = dict(location=location, object_index=index,
                          cue_id=a.ref(value.get("uniqueID")),
                          number=a.ref(value.get("number")),
                          mirror_shape=a.ref(shapes.get("mirrorShape")), curves={})
            for side in ("upShape", "downShape"):
                shape = a.ref(shapes.get(side))
                if not isinstance(shape, dict):
                    continue
                entries = a.array(shape["shapeEntries"])
                if len(entries) > 4096:
                    raise ValueError("Curve point budget exceeded.")
                points = []
                for ref in entries:
                    entry = a.ref(ref)
                    points.append(dict(t=a.ref(entry.get("t")), v=a.ref(entry.get("v"))))
                result["curves"][side] = dict(type=a.ref(shape.get("type")),
                    curve_parameter=a.ref(shape.get("curveParameter")), points=points)
            samples.append(result)
    return dict(sha256=hashlib.sha256(data).hexdigest(), archive_count=len(seen),
                coverage="archive_objects_including_possible_templates_and_residuals",
                samples=samples, write_acceptance="not_demonstrated")


def catalogue_evidence() -> dict:
    records, sources = load_catalogue("bundled")
    counts, examples = Counter(), {}
    for record in records:
        for parameter in record["parameters"]:
            kind = parameter["type"]
            counts[kind] += 1
            examples.setdefault(kind, dict(definition=record["name"],
                definition_id=record["definition_id"], outputs=parameter.get("outputs"),
                channel=parameter["channel"], importable=record["importable"],
                source_sha256=record["source_sha256"]))
    return dict(sources=sources, definitions=len(records),
                importable=sum(record["importable"] for record in records),
                parameter_counts=dict(counts), examples=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--catalogue", action="store_true")
    args = parser.parse_args()
    before = read_stable(args.workspace)
    result = inspect_curves(before)
    if args.catalogue:
        result["catalogue"] = catalogue_evidence()
    if read_stable(args.workspace) != before:
        raise ValueError("Workspace changed during research capture; discard this result.")
    result["file_unchanged_during_capture"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
