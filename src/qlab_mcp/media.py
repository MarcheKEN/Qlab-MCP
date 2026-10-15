"""Bounded local file discovery after conversational user consent."""
from __future__ import annotations

import os
import time

MAX_SCAN_ENTRIES = 20_000
SCAN_SECONDS = 5.0


def search_media_files(roots: tuple[str, ...], query: str, max_results: int) -> dict:
    query = query.strip().casefold()
    if not query:
        raise ValueError("query must contain a filename substring.")
    if not roots:
        raise ValueError("File search needs a directory to search.")
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")
    pending = list(dict.fromkeys(os.path.realpath(root) for root in roots))
    visited = set()
    files, warnings = [], []
    scanned = 0
    deadline = time.monotonic() + SCAN_SECONDS
    truncated = False
    while pending:
        if scanned >= MAX_SCAN_ENTRIES or time.monotonic() >= deadline:
            truncated = True
            break
        directory = pending.pop()
        if directory in visited:
            continue
        visited.add(directory)
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if scanned >= MAX_SCAN_ENTRIES or time.monotonic() >= deadline:
                        truncated = True
                        break
                    scanned += 1
                    # Avoid symlink cycles and unexpected traversal outside the search folder.
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
                    elif query in entry.name.casefold() and entry.is_file(follow_symlinks=False):
                        stat = entry.stat(follow_symlinks=False)
                        files.append({"path": entry.path, "name": entry.name, "size_bytes": stat.st_size})
                        if len(files) == max_results:
                            truncated = True
                            break
        except OSError:
            warnings.append(f"Could not fully inspect directory: {directory}")
        if truncated:
            break
    return {"files": sorted(files, key=lambda item: item["path"]), "scanned_entries": scanned,
            "truncated": truncated, "warnings": warnings}
