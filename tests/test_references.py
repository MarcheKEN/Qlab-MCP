from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "docs" / "references" / "manifest.json"


def test_reference_manifest_matches_local_files() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    references = manifest["references"]

    assert manifest["schema_version"] == 1
    assert {item["path"] for item in references} == {
        "docs/references/osc_queries.md",
        "docs/references/qlab_osc_dictionary.md",
    }
    for item in references:
        content = (PROJECT_ROOT / item["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
        assert item["documented_qlab_version"] == "QLab 5; exact patch unknown"
        assert item["retrieval_date"] is None
        assert item["first_repository_import"] == "2026-05-15"
        assert item["provenance_status"] == "inferred"
        assert item["source_url"].startswith("https://qlab.app/docs/v5/")
