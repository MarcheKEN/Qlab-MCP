from qlab_mcp.cues.query import CueQueryMixin
from qlab_mcp.server_responses import query_success_payload
import pytest


class Reader(CueQueryMixin):
    def __init__(self, failure):
        self.failure = failure

    def _resolve_workspace_id_strict(self, workspace_id):
        return workspace_id

    def get_cue_lists(self, *args, **kwargs):
        if self.failure == "root":
            raise RuntimeError("root unavailable")
        return {"cue_lists": [{"uniqueID": "list-1", "type": "Cue List"}]}

    def get_cue_children(self, *args, **kwargs):
        if self.failure in {"branch", "both"}:
            raise RuntimeError("branch unavailable")
        if self.failure == "invalid":
            return {"children": [None]}
        if self.failure == "missing_id":
            return {"children": [{"type": "Video"}]}
        if self.failure == "empty_fallback":
            if not kwargs["ids_only"]:
                raise RuntimeError("metadata unavailable")
            return {"children": []}
        if self.failure == "two_cues":
            return {"children": [{"uniqueID": "cue-1", "type": "Video"}, {"uniqueID": "cue-2", "type": "Video"}]}
        return {"children": [{"uniqueID": "cue-1", "type": "Video"}]}

    def read_cue_values(self, workspace_id, cue_id, keys, **kwargs):
        if (self.failure == "cue" and cue_id == "cue-1") or (self.failure == "both" and cue_id == "list-1"):
            raise RuntimeError("cue unavailable")
        return {"values": {"uniqueID": cue_id, "type": "Video" if cue_id.startswith("cue-") else "Cue List"}}


@pytest.mark.parametrize(
    ("failure", "status", "reason", "error_key"),
    [("root", "failed", "root_read_error", "cueLists/shallow"),
     ("branch", "partial", "child_read_error", "list-1"),
     ("cue", "partial", "cue_read_error", "cue-1")],
)
def test_query_reports_incomplete_reads(failure, status, reason, error_key):
    result = Reader(failure).query_cues("ws-1", "type", "Video")

    assert result["query_completeness"] == status
    assert reason in result["query_completeness_reasons"]
    assert not result["scanned_all_cues"]
    assert result["truncated"]
    assert reason in result["truncation_reasons"]
    assert error_key in result["errors"]


def test_query_without_read_errors_is_complete():
    result = Reader(None).query_cues("ws-1", "type", "Video")

    assert result["query_completeness"] == "complete"
    assert result["scanned_all_cues"]
    assert not result["truncated"]
    assert result["matched_count"] == 1


def test_root_read_failure_is_an_error_in_public_response():
    result = query_success_payload(Reader("root").query_cues("ws-1", "type", "Video"))

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["query_completeness"] == "failed"


def test_query_reports_branch_metadata_failure_even_with_empty_id_fallback():
    result = Reader("empty_fallback").query_cues("ws-1", "type", "Video")

    assert result["query_completeness"] == "partial"
    assert "child_metadata_unavailable" in result["query_completeness_reasons"]
    assert not result["scanned_all_cues"]


@pytest.mark.parametrize("failure", ["invalid", "missing_id"])
def test_query_reports_invalid_cue_entry_as_incomplete(failure):
    result = Reader(failure).query_cues("ws-1", "type", "Video")

    assert result["query_completeness"] == "partial"
    assert "invalid_payload" in result["query_completeness_reasons"]
    assert result["truncated"]
    assert not result["scanned_all_cues"]
    assert result["errors"]


def test_query_preserves_branch_and_cue_errors_for_same_id():
    result = Reader("both").query_cues("ws-1", "type", "Video")

    assert result["query_completeness"] == "partial"
    assert result["errors"]["list-1"] == "branch unavailable"
    assert result["errors"]["cue:list-1"] == "cue unavailable"


def test_result_limit_does_not_make_search_incomplete():
    result = Reader("two_cues").query_cues("ws-1", "type", "Video", max_results=1)

    assert result["query_completeness"] == "complete"
    assert result["scanned_all_cues"]
    assert result["result_limited"]
    assert result["truncation_reasons"] == ["max_results"]
    assert result["matched_count"] == 2
    assert result["returned_count"] == 1
