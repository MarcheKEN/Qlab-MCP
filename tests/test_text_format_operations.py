"""No runtime setters: full Text snapshots and safe typed fragment plans."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from qlab_mcp.cues.visual import TextRun
from qlab_mcp.write import text_format as fmt

UTF16 = fmt.RuntimeSemantics(index_unit="utf16", ranges_verified=True)


def operation(attrs=None, selector=None):
    return fmt.TextFormatOperation.model_validate({"property": "text/format", "args": {
        "selector": selector or {"kind": "full"}, "attributes": attrs or {"fontSize": 36}}})


def state():
    return fmt.snapshot("hello", [
        {"range": [0, 2], "fontSize": 12, "color": [1, 0, 0, 1], "nativeExtra": {"a": [True, None]}},
        {"range": [2, 3], "fontSize": 24, "color": [0, 1, 0, 1], "nativeExtra": {"a": [False, None]}},
    ])


def test_extra_read_attributes_survive_serialization():
    raw = state()["runs"][0]
    result = TextRun.model_validate(raw).model_dump(exclude_unset=True)
    assert result == raw


def test_global_mixed_size_preserves_colors_unknown_attributes_and_original():
    before = state()
    original = deepcopy(before)
    after = fmt.preflight(before, [operation()])
    assert [run["fontSize"] for run in after["runs"]] == [36, 36]
    assert before == original
    for old, new in zip(before["runs"], after["runs"]):
        assert {k: v for k, v in old.items() if k != "fontSize"} == {k: v for k, v in new.items() if k != "fontSize"}


def test_json_wire_single_saved_setter_and_unique_binding_key():
    op = fmt.normalize(operation(), 7, state())
    assert op["property"] == "text/format@7" and op["path"] == "text/format"
    assert json.loads(op["args"][0]) == {"fontSize": 36}
    assert op["requires_confirm_token"] is True


def test_absent_requested_attribute_blocks_without_default():
    before = state()
    del before["runs"][1]["fontSize"]
    with pytest.raises(ValueError, match="absent"):
        fmt.preflight(before, [operation()])


def test_range_only_requires_attribute_in_affected_runs():
    before = state()
    del before["runs"][1]["fontSize"]
    after = fmt.preflight(before, [operation(selector={"kind": "range", "index": 0, "length": 2})], semantics=UTF16)
    assert after["runs"][0]["fontSize"] == 36
    assert "fontSize" not in after["runs"][1]


def test_range_splits_runs_and_preserves_unaffected_regions():
    before = state()
    op = operation(selector={"kind": "range", "index": 1, "length": 2})
    after = fmt.advance(before, op, UTF16)
    assert [(r["range"], r["fontSize"]) for r in after["runs"]] == [([0, 1], 12), ([1, 1], 36), ([2, 1], 36), ([3, 2], 24)]
    assert json.loads(fmt.normalize(op, 0, before, UTF16)["args"][0]) == {"fontSize": 36, "range": [1, 2]}


def test_merge_and_split_equivalent_intervals_match():
    before = fmt.snapshot("abcd", [{"range": [0, 4], "fontSize": 12, "extra": "same"}])
    split = fmt.snapshot("abcd", [{"range": [0, 1], "fontSize": 12, "extra": "same"}, {"range": [1, 3], "fontSize": 12, "extra": "same"}])
    assert fmt.matches(split, before) and fmt.matches(before, split)
    split["runs"][1]["extra"] = "changed"
    assert not fmt.matches(split, before)


@pytest.mark.parametrize("runs", [
    [{"range": [1, 4], "fontSize": 12}],
    [{"range": [0, 2]}, {"range": [3, 2]}],
    [{"range": [0, 3]}, {"range": [2, 3]}],
    [{"range": [0, 0]}, {"range": [0, 5]}],
    [{"range": [0, 4]}],
])
def test_incomplete_or_overlapping_coverage_blocks(runs):
    with pytest.raises(ValueError):
        fmt.snapshot("hello", runs)


def test_unicode_unit_pending_then_utf16_boundaries():
    runs = [{"range": [0, 4], "fontSize": 12}]
    with pytest.raises(ValueError, match="Unicode"):
        fmt.snapshot("A😀B", runs, fmt.RuntimeSemantics())
    before = fmt.snapshot("A😀B", runs, UTF16)
    selected = operation(selector={"kind": "range", "index": 1, "length": 2})
    assert fmt.resolve_selector(selected.args.selector, before, UTF16) == (1, 2)
    with pytest.raises(ValueError, match="fallback"):
        fmt.advance(before, selected, UTF16)
    with pytest.raises(ValueError, match="splits"):
        fmt.advance(before, operation(selector={"kind": "range", "index": 1, "length": 1}), UTF16)


def test_combining_crlf_coordinates_count_native_units_without_tokenization():
    text = "e\u0301\r\n😀"
    before = fmt.snapshot(text, [{"range": [0, 6], "fontSize": 12}], UTF16)
    selected = operation(selector={"kind": "range", "index": 4, "length": -1})
    assert fmt.resolve_selector(selected.args.selector, before, UTF16) == (4, 2)
    after = fmt.advance(before, operation(selector={"kind": "range", "index": 0, "length": 4}), UTF16)
    assert [r["range"] for r in after["runs"]] == [[0, 4], [4, 2]]


@pytest.mark.parametrize("text,index,length", [
    ("e\u0301", 0, 1),
    ("👩\u200d💻", 0, 2),
    ("🇪🇸", 0, 2),
    ("A\x00e\u0301", 2, 1),
    ("a\r\nb", 1, 1),
])
def test_range_rejects_split_composed_characters(text, index, length):
    size = len(text.encode("utf-16-le")) // 2
    before = fmt.snapshot(text, [{"range": [0, size], "fontSize": 12}], UTF16)
    with pytest.raises(ValueError, match="splits"):
        fmt.resolve_selector(operation(selector={"kind": "range", "index": index, "length": length}).args.selector, before, UTF16)


def test_cjk_formatting_requires_stable_core_text_fallback(monkeypatch):
    before = fmt.snapshot("漢字", [{"range": [0, 2], "fontName": "HiraginoSans-W3",
                                   "fontFamily": "Hiragino Sans", "fontStyle": "W3",
                                   "fontSize": 12, "color": [1, 1, 1, 1]}], UTF16)
    monkeypatch.setattr(fmt, "_coretext_fallback", lambda font, size, text: font)
    changed_color = operation({"color": [1, 0, 0, 1]})
    assert fmt.preflight(before, [changed_color], semantics=UTF16)["runs"][0]["color"] == [1, 0, 0, 1]

    monkeypatch.setattr(fmt, "_coretext_fallback",
                        lambda font, size, text: font if size == 12 else "PingFangSC-Regular")
    changed_size = operation({"fontSize": 24})
    with pytest.raises(ValueError, match="fallback"):
        fmt.preflight(before, [changed_size], semantics=UTF16)


def test_cjk_formatting_blocks_an_existing_font_substitution(monkeypatch):
    before = fmt.snapshot("漢", [{"range": [0, 1], "fontName": "HelveticaNeue-Bold",
                                  "fontFamily": "Helvetica Neue", "fontStyle": "Bold",
                                  "fontSize": 12, "color": [1, 1, 1, 1]}], UTF16)
    monkeypatch.setattr(fmt, "_coretext_fallback", lambda font, size, text: "PingFangSC-Regular")
    with pytest.raises(ValueError, match="substitutes"):
        fmt.preflight(before, [operation({"color": [1, 0, 0, 1]})], semantics=UTF16)


def test_pending_ranges_words_and_percentages_fail_closed():
    with pytest.raises(ValueError, match="range semantics"):
        fmt.preflight(state(), [operation(selector={"kind": "range", "index": 0, "length": 1})], semantics=fmt.RuntimeSemantics())
    with pytest.raises(ValueError, match="word tokenization"):
        fmt.preflight(state(), [operation(selector={"kind": "word", "index": 0})], semantics=UTF16)
    with pytest.raises(ValueError, match="Percentage rounding"):
        fmt.preflight(state(), [operation(selector={"kind": "range", "index": {"percent": 20}, "length": {"percent": 40}})], semantics=UTF16)


def test_proven_percentage_rounding_resolves_absolute_wire_range():
    semantics = fmt.RuntimeSemantics(index_unit="utf16", ranges_verified=True, percentage_rounding="floor")
    op = operation(selector={"kind": "range", "index": {"percent": 25}, "length": {"percent": 50}})
    assert json.loads(fmt.normalize(op, state=state(), semantics=semantics)["args"][0])["range"] == [1, 2]


@pytest.mark.parametrize("selector", [
    {"kind": "range", "index": 5, "length": 1},
    {"kind": "range", "index": 5, "length": -1},
    {"kind": "range", "index": 0, "length": {"percent": 0}},
])
def test_outside_or_empty_resolved_range_rejected(selector):
    semantics = fmt.RuntimeSemantics(index_unit="utf16", ranges_verified=True, percentage_rounding="floor")
    with pytest.raises(ValueError, match="empty or outside"):
        fmt.preflight(state(), [operation(selector=selector)], semantics=semantics)


def test_overlapping_attribute_destinations_block_but_separate_attributes_work():
    first = operation(selector={"kind": "range", "index": 0, "length": 3})
    same = operation(selector={"kind": "range", "index": 2, "length": 1})
    with pytest.raises(ValueError, match="Overlapping"):
        fmt.preflight(state(), [first, same], semantics=UTF16)
    other = operation({"color": [0, 0, 1, 1]}, {"kind": "range", "index": 2, "length": 1})
    fmt.preflight(state(), [first, other], semantics=UTF16)


def test_content_and_scalar_duplicate_destinations_block():
    with pytest.raises(ValueError, match="content replacement"):
        fmt.preflight(state(), [operation()], {"text": "other"})
    with pytest.raises(ValueError, match="each destination"):
        fmt.preflight(state(), [operation()], {"text/format/fontSize": 32})


def test_alignment_global_shadow_line_font_scope_fail_closed():
    with pytest.raises(ValidationError, match="entire text"):
        operation({"alignment": "center"}, {"kind": "range", "index": 0, "length": 2})
    with pytest.raises(ValueError, match="line scope"):
        fmt.preflight(state(), [operation({"shadowBlurRadius": 2}, {"kind": "range", "index": 0, "length": 2})], semantics=UTF16)
    with pytest.raises(ValueError, match="Font resolution"):
        fmt.preflight(state(), [operation({"fontName": "Arial"})])
    with pytest.raises(ValueError, match="JSON formatting transport"):
        fmt.preflight(state(), [operation({"alignment": "center"})])


@pytest.mark.parametrize("attrs", [{}, {"fontSize": None}, {"fontSize": True}, {"fontSize": float("nan")},
                                    {"shadowOffset": {"width": False, "height": 0}},
                                    {"color": [1, 2, 0, 1]}, {"freeJSON": {}},
                                    {"fontName": "Arial", "fontFamilyAndStyle": {"family": "Arial", "style": "Regular"}}])
def test_no_arbitrary_json_and_strict_attribute_types(attrs):
    with pytest.raises(ValidationError):
        fmt.TextFormatOperation.model_validate({"property": "text/format", "args": {"attributes": attrs}})


def test_changed_text_coverage_attributes_and_missing_extras_fail_matches():
    before = state()
    for change in ("text", "coverage", "attribute", "extra"):
        after = deepcopy(before)
        if change == "text":
            after["text"] = "other"
        elif change == "coverage":
            after["runs"][1]["range"][1] = 2
        elif change == "attribute":
            after["runs"][1]["color"] = [1, 1, 1, 1]
        else:
            del after["runs"][1]["nativeExtra"]
        assert not fmt.matches(after, before)


def test_nonfinite_raw_extras_rejected():
    before = state()
    before["runs"][0]["nativeExtra"] = float("inf")
    with pytest.raises(ValueError, match="nonfinite"):
        fmt.snapshot(before["text"], before["runs"])


@pytest.mark.parametrize("value", [-1.0, True, False])
def test_to_end_sentinel_is_strict_integer(value):
    with pytest.raises(ValidationError):
        operation(selector={"kind": "range", "index": 0, "length": value})


def test_operation_count_and_direct_normalization_baseline_validation():
    with pytest.raises(ValueError, match="1–50"):
        fmt.preflight(state(), [])
    with pytest.raises(ValueError, match="1–50"):
        fmt.preflight(state(), [operation()] * 51)
    broken = state()
    broken["runs"][0]["range"] = [1, 1]
    with pytest.raises(ValueError, match="cover"):
        fmt.normalize(operation(), state=broken)


def test_dependency_checker_compares_complete_effective_format(monkeypatch):
    from qlab_mcp.write import control
    before = state()
    monkeypatch.setattr(control, "_scalar", lambda reader, ws, uid, key: before["text"] if key == "text" else before["runs"])
    fmt.check_dependencies(None, "ws", "uid", deepcopy(before))
    expected = deepcopy(before)
    expected["runs"][1]["nativeExtra"] = {"changed": True}
    with pytest.raises(ValueError, match="changed before setter"):
        fmt.check_dependencies(None, "ws", "uid", expected)


@pytest.fixture
def format_reader(monkeypatch):
    from types import SimpleNamespace
    from qlab_mcp.errors import OscPreparationError, OscTimeoutError
    from qlab_mcp.write import control
    from test_control_cue_writes import Reader, MEMO

    class FormatReader(Reader):
        def _request(self, address, *args, **kwargs):
            uid, field = address.split("/cue_id/")[1].split("/", 1)
            if field != "text/format" or not args:
                return super()._request(address, *args, **kwargs)
            if self.fail == "prepare":
                raise OscPreparationError("preparation failed")
            self.setters.append((uid, field, args))
            payload = json.loads(args[0])
            start, length = payload.pop("range", [0, len(self.values[uid]["text"])])
            characters = []
            for run in self.values[uid][field]:
                attributes = {k: deepcopy(v) for k, v in run.items() if k != "range"}
                characters.extend(deepcopy(attributes) for _ in range(run["range"][1]))
            for position in range(start, start+length):
                characters[position].update(deepcopy(payload))
            runs = []
            for position, attrs in enumerate(characters):
                if runs and {k: v for k, v in runs[-1].items() if k != "range"} == attrs:
                    runs[-1]["range"][1] += 1
                else:
                    runs.append({"range": [position, 1], **attrs})
            self.values[uid][field] = runs
            if self.fail == "mismatch":
                runs[-1]["nativeExtra"] = "unrequested change"
            if self.fail == "timeout":
                raise OscTimeoutError("timeout")
            return SimpleNamespace(data=None)

    monkeypatch.setattr(control, "check_write_readiness", lambda *a: {"ok": True})
    monkeypatch.setattr(control, "ensure_write_ready", lambda *a: None)
    monkeypatch.setattr(fmt, "SEMANTICS", UTF16)
    reader = FormatReader()
    reader.values[MEMO].update(type="Text", text="hello", **{"text/format": deepcopy(state()["runs"])})
    return reader


def _format_request(*ops, properties=None):
    from test_control_cue_writes import MEMO
    item = {"cue_id": MEMO, "operations": [op.model_dump(exclude_unset=True) for op in ops]}
    if properties is not None:
        item["properties"] = properties
    return item


def _execute_format(reader, items):
    from qlab_mcp.write.visual import edit_text_cues
    from test_control_cue_writes import WS
    plan = edit_text_cues(reader, WS, items, True)
    assert plan["ok"], plan
    assert not reader.setters
    for item, result in zip(items, plan["results"]):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    return edit_text_cues(reader, WS, items, False)


def test_integrated_format_operations_only_cumulative_ranges(format_reader):
    from test_control_cue_writes import MEMO
    first = operation(selector={"kind": "range", "index": 0, "length": 2})
    second = operation({"color": [0, 0, 1, 1]}, {"kind": "range", "index": 2, "length": 2})
    result = _execute_format(format_reader, [_format_request(first, second)])
    assert result["ok"] and len(format_reader.setters) == 2, result
    actual = format_reader.values[MEMO]["text/format"]
    assert [(run["range"], run["fontSize"], run["color"]) for run in actual] == [
        ([0, 2], 36, [1, 0, 0, 1]), ([2, 2], 24, [0, 0, 1, 1]), ([4, 1], 24, [0, 1, 0, 1])]
    assert actual[0]["nativeExtra"] == {"a": [True, None]}
    assert actual[1]["nativeExtra"] == actual[2]["nativeExtra"] == {"a": [False, None]}


def test_integrated_format_plus_unrelated_property(format_reader):
    from test_control_cue_writes import MEMO
    result = _execute_format(format_reader, [_format_request(operation(), properties={"name": "formatted"})])
    assert result["ok"] and len(format_reader.setters) == 2, result
    assert format_reader.values[MEMO]["name"] == "formatted"


@pytest.mark.parametrize("problem", ["overlap", "content", "absent"])
def test_integrated_preflight_no_setters(format_reader, problem):
    from qlab_mcp.write.visual import edit_text_cues
    from test_control_cue_writes import MEMO, WS
    item = _format_request(operation())
    if problem == "overlap":
        item["operations"].append(operation().model_dump(exclude_unset=True))
    elif problem == "content":
        item["properties"] = {"text": "replacement"}
    else:
        del format_reader.values[MEMO]["text/format"][1]["fontSize"]
    result = edit_text_cues(format_reader, WS, [item], True)
    assert not result["ok"] and not format_reader.setters


def test_integrated_unrequested_change_stops_second_setter(format_reader):
    format_reader.fail = "mismatch"
    result = _execute_format(format_reader, [_format_request(operation(), operation({"color": [0, 0, 1, 1]}))])
    assert not result["ok"] and len(format_reader.setters) == 1


def test_integrated_timeout_readback_confirms_without_retry(format_reader):
    format_reader.fail = "timeout"
    result = _execute_format(format_reader, [_format_request(operation())])
    assert result["ok"] and len(format_reader.setters) == 1, result
    assert result["status"] == "updated_with_confirmed_timeouts"


def test_integrated_snapshot_change_invalidates_confirmation(format_reader):
    from qlab_mcp.write.visual import edit_text_cues
    from test_control_cue_writes import MEMO, WS
    item = _format_request(operation())
    plan = edit_text_cues(format_reader, WS, [item], True)
    assert plan["ok"], plan
    item["confirm_gates"] = [op["confirm_token"] for op in plan["results"][0]["planned_operations"]]
    format_reader.values[MEMO]["text/format"][1]["nativeExtra"] = "changed"
    result = edit_text_cues(format_reader, WS, [item], False)
    assert not result["ok"] and not format_reader.setters


def test_integrated_native_merge_then_next_format_operation(format_reader):
    from test_control_cue_writes import MEMO
    format_reader.values[MEMO]["text/format"] = [
        {"range": [0, 2], "fontSize": 12, "color": [1, 0, 0, 1], "extra": "same"},
        {"range": [2, 3], "fontSize": 24, "color": [1, 0, 0, 1], "extra": "same"}]
    result = _execute_format(format_reader, [_format_request(operation(), operation({"color": [0, 0, 1, 1]}))])
    assert result["ok"] and len(format_reader.setters) == 2, result
    assert format_reader.values[MEMO]["text/format"] == [{"range": [0, 5], "fontSize": 36, "color": [0, 0, 1, 1], "extra": "same"}]


@pytest.mark.parametrize("health", ["isRunning", "isPaused", "isAuditioning", "isBroken", "isWarning"])
def test_integrated_format_operations_require_safe_cue_state(format_reader, health):
    from qlab_mcp.write.visual import edit_text_cues
    from test_control_cue_writes import MEMO, WS
    format_reader.values[MEMO][health] = True
    result = edit_text_cues(format_reader, WS, [_format_request(operation())], True)
    assert not result["ok"] and not format_reader.setters


def test_integrated_content_and_scalar_format_also_require_separate_dry_runs(format_reader):
    from qlab_mcp.write.visual import edit_text_cues
    from test_control_cue_writes import MEMO, WS
    result = edit_text_cues(format_reader, WS, [{"cue_id": MEMO, "properties": {"text": "changed", "text/format/fontSize": 32}}], True)
    assert not result["ok"] and not format_reader.setters


def test_live_unicode_font_fallback_is_not_accepted_as_requested_size():
    before = fmt.snapshot("A😀B", [{"range": [0, 4], "fontSize": 72, "fontName": "HelveticaNeue-Bold", "fontFamily": "Helvetica Neue", "fontStyle": "Bold"}], UTF16)
    with pytest.raises(ValueError, match="fallback"):
        fmt.advance(before, operation({"fontSize": 48}, {"kind": "range", "index": 1, "length": 2}), UTF16)
    expected = deepcopy(before)
    expected['runs'][0]['fontSize'] = 48
    actual = deepcopy(expected)
    actual["runs"][0].update(fontName="AppleColorEmoji", fontFamily="Apple Color Emoji", fontStyle="Regular")
    assert not fmt.matches(actual, expected, UTF16)
    # Native coordinate units alone cannot make companion font changes predictable.
    with pytest.raises(ValueError, match="Unicode"):
        fmt.snapshot(before["text"], before["runs"], fmt.RuntimeSemantics())


def test_verified_ascii_range_is_available_while_unicode_remains_blocked():
    op = operation(selector={"kind": "range", "index": 0, "length": 3})
    assert json.loads(fmt.normalize(op, state=state())["args"][0])["range"] == [0, 3]
    assert fmt.capabilities()["ranges_verified"]
    assert fmt.capabilities()["unicode_formatting_pending"]


def test_installed_percentage_rounding_and_simple_word_scope():
    before = fmt.snapshot('uno dos tres cuatro', [{'range': [0, 19], 'fontSize': 72}])
    percent = operation(selector={'kind':'range','index':{'percent':25},'length':{'percent':25}})
    assert fmt.resolve_selector(percent.args.selector, before) == (5, 5)
    word = operation(selector={'kind':'word','index':2})
    assert fmt.resolve_selector(word.args.selector, before) == (8, 4)
    with pytest.raises(ValueError, match='word'):
        fmt.resolve_selector(operation(selector={'kind':'word','index':4}).args.selector, before)
    for text in ['one\ttwo', 'one\ntwo', 'one\rtwo']:
        supported = fmt.snapshot(text, [{'range':[0,len(text)],'fontSize':72}])
        second = operation(selector={'kind':'word','index':1})
        assert fmt.resolve_selector(second.args.selector, supported) == (4, 3)
    punctuation = fmt.snapshot('one-two', [{'range':[0,7],'fontSize':72}])
    with pytest.raises(ValueError, match='tokenization'):
        fmt.resolve_selector(word.args.selector, punctuation)


def test_latin_unicode_range_and_unknown_fallback_block():
    before = fmt.snapshot('Árbol 😀', [{'range':[0,8],'fontSize':72,'fontName':'HelveticaNeue-Bold'}])
    after = fmt.advance(before, operation(selector={'kind':'range','index':0,'length':1}))
    assert after['runs'][0]['fontSize'] == 36
    with pytest.raises(ValueError, match='fallback'):
        fmt.advance(before, operation(selector={'kind':'range','index':6,'length':2}))


def test_partial_font_requires_complete_observed_companion_metadata():
    before = fmt.snapshot('AB', [
        {'range':[0,1],'fontName':'HelveticaNeue','fontFamily':'Helvetica Neue','fontStyle':'Regular','fontSize':72},
        {'range':[1,1],'fontName':'HelveticaNeue-Bold','fontFamily':'Helvetica Neue','fontStyle':'Bold','fontSize':72},
    ])
    op = operation({'fontName':'HelveticaNeue-Bold'},{'kind':'range','index':0,'length':1})
    expected = fmt.advance(before,op)
    assert expected['runs'][0]['fontStyle'] == 'Bold'
    assert json.loads(fmt.normalize(op,state=before)['args'][0]) == {'fontName':'HelveticaNeue-Bold','range':[0,1]}
    with pytest.raises(ValueError, match='observed'):
        fmt.advance(before,operation({'fontName':'UnknownFont'}))
    inconsistent = deepcopy(before)
    inconsistent['runs'][0]['fontName'] = 'HelveticaNeue-Bold'
    with pytest.raises(ValueError, match='ambiguous'):
        fmt.advance(inconsistent,op)


@pytest.mark.parametrize('text', ['A—B', 'A“”B', 'A\u00a0B', 'Ae\u0301B'])
def test_unicode_color_preserves_font_metadata_and_utf16_range(text):
    size = len(text.encode('utf-16-le')) // 2
    before = fmt.snapshot(text, [{'range': [0, size], 'fontName': 'HelveticaNeue-Bold',
                                 'fontSize': 72, 'color': [1, 1, 1, 1]}])
    op = operation({'color': [0, 0, 1, 1]}, {'kind': 'range', 'index': 1, 'length': size-2})
    expected = fmt.advance(before, op)
    assert expected['runs'][1]['range'] == [1, size-2]
    assert expected['runs'][1]['color'] == [0, 0, 1, 1]
    assert all(run['fontName'] == 'HelveticaNeue-Bold' and run['fontSize'] == 72
               for run in expected['runs'])
    changed_font = deepcopy(expected)
    changed_font['runs'][1]['fontName'] = 'UnexpectedFallback'
    assert not fmt.matches(changed_font, expected)


@pytest.mark.parametrize('text', ['A😀B', 'AЖB'])
def test_color_also_blocks_unpredictable_emoji_and_non_cjk_fallback(text):
    size = len(text.encode('utf-16-le')) // 2
    before = fmt.snapshot(text, [{'range': [0, size], 'fontName': 'HelveticaNeue-Bold',
                                 'fontSize': 72, 'color': [1, 1, 1, 1]}])
    with pytest.raises(ValueError, match='fallback'):
        fmt.advance(before, operation({'color': [0, 0, 1, 1]}))


@pytest.mark.parametrize('attributes', [{'fontSize': 48}, {'color': [0, 0, 1, 1], 'fontSize': 48}])
def test_punctuation_expansion_does_not_authorize_typography(attributes):
    before = fmt.snapshot('A—B', [{'range': [0, 3], 'fontSize': 72, 'color': [1, 1, 1, 1]}])
    with pytest.raises(ValueError, match='fallback'):
        fmt.advance(before, operation(attributes))


@pytest.mark.parametrize('index, expected', [(0, (1, 5)), (1, (8, 3)), (2, (13, 4))])
def test_native_proven_latin_word_delimiters(index, expected):
    before = fmt.snapshot('«Árbol»—luz\u00a0“azul”', [{'range': [0, 18], 'fontSize': 72}])
    op = operation(selector={'kind': 'word', 'index': index})
    assert fmt.resolve_selector(op.args.selector, before) == expected
    assert json.loads(fmt.normalize(op, state=before)['args'][0])['range'] == list(expected)


@pytest.mark.parametrize('text', ["don't stop", 'one_two', '中文 luz', 'luz 😀', '\u0301luz'])
def test_unproved_word_tokenization_stays_blocked(text):
    size = len(text.encode('utf-16-le')) // 2
    before = fmt.snapshot(text, [{'range': [0, size], 'fontSize': 72}])
    with pytest.raises(ValueError, match='tokenization'):
        fmt.resolve_selector(operation(selector={'kind':'word', 'index':0}).args.selector, before)
