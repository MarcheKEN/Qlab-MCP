"""Typed saved Text formatting with complete, interval-based verification.

Selectors resolve to native UTF-16 coordinates. Unproved tokenization, font
fallback and paragraph normalization fail closed before a setter is planned.
"""
from __future__ import annotations

from copy import deepcopy
import ctypes
from dataclasses import dataclass
import json
import math
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from .control import Number, Nonnegative


class Percent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    percent: Annotated[Number, Field(ge=0, le=100)]


class FullSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["full"] = "full"


class RangeSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["range"]
    index: Annotated[StrictInt, Field(ge=0)] | Percent
    length: Annotated[StrictInt, Field(ge=1)] | Literal[-1] | Percent

    @field_validator("length", mode="before")
    @classmethod
    def strict_length(cls, value):
        if not isinstance(value, (dict, Percent)) and type(value) is not int:
            raise ValueError("Range length requires an integer or typed percentage.")
        return value


class WordSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["word"]
    index: Annotated[StrictInt, Field(ge=0)]


Selector = Annotated[FullSelector | RangeSelector | WordSelector, Field(discriminator="kind")]
Color = Annotated[list[Annotated[Number, Field(ge=0, le=1)]], Field(min_length=4, max_length=4)]


class ShadowOffset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: Number
    height: Number


class FontPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: Annotated[StrictStr, Field(min_length=1)]
    style: Annotated[StrictStr, Field(min_length=1)]


class TextAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fontName: Annotated[StrictStr, Field(min_length=1)] | None = None
    fontFamilyAndStyle: FontPair | None = None
    fontSize: Annotated[Number, Field(gt=0)] | None = None
    lineSpacing: Number | None = None
    color: Color | None = None
    backgroundColor: Color | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = None
    shadowColor: Color | None = None
    shadowBlurRadius: Nonnegative | None = None
    shadowOffset: ShadowOffset | None = None
    underlineColor: Color | None = None
    strikethroughColor: Color | None = None
    underlineStyle: Literal["none", "single", "double"] | None = None
    strikethroughStyle: Literal["none", "single", "double"] | None = None

    @model_validator(mode="after")
    def valid_attributes(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Supply known attributes; null is not a format edit.")
        if {"fontName", "fontFamilyAndStyle"} <= self.model_fields_set:
            raise ValueError("Use fontName or fontFamilyAndStyle.")
        return self


class TextFormatArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selector: Selector = Field(default_factory=FullSelector)
    attributes: TextAttributes

    @model_validator(mode="after")
    def scope(self):
        if self.attributes.alignment is not None and self.selector.kind != "full":
            raise ValueError("Alignment affects the entire text; use the full selector.")
        return self


class TextFormatOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property: Literal["text/format"]
    args: TextFormatArgs


@dataclass(frozen=True)
class RuntimeSemantics:
    """Only populate fields with fixture evidence for the installed QLab version."""
    index_unit: Literal["utf16", "codepoint"] | None = None
    ranges_verified: bool = False
    percentage_rounding: Literal["floor", "ceil", "nearest"] | None = None
    word_tokenization: Literal["ascii_space", "latin_delimiters"] | None = None
    # JSON attribute transport must be proved independently of scalar setters.
    json_attributes: frozenset[str] = frozenset({"fontSize", "lineSpacing", "color", "fontName", "fontFamily", "fontStyle"})


# QLab 5.5.10: UTF-16, nearest percentages and bounded Latin words verified.
SEMANTICS = RuntimeSemantics(index_unit="utf16", ranges_verified=True,
                             percentage_rounding="nearest", word_tokenization="latin_delimiters")
_SHADOWS = {"shadowColor", "shadowBlurRadius", "shadowOffset"}


def _units(text, semantics):
    if semantics.index_unit == "utf16":
        return len(text.encode("utf-16-le")) // 2
    if semantics.index_unit == "codepoint" or text.isascii():
        return len(text)
    raise ValueError("Native Unicode coordinate units are pending runtime validation.")


def _boundaries(text, semantics):
    positions = {0}
    offset = 0
    for char in text:
        offset += _units(char, semantics)
        positions.add(offset)
    return positions


def _composed_boundaries(text):
    """Use macOS character clusters rather than splitting combined glyphs."""
    if text.isascii():
        return set(range(len(text) + 1)) - {i + 1 for i in range(len(text) - 1) if text[i:i + 2] == '\r\n'}
    class Range(ctypes.Structure):
        _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]
    try:
        cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        create = cf.CFStringCreateWithBytes
        create.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32, ctypes.c_bool]
        create.restype = ctypes.c_void_p
        find = cf.CFStringGetRangeOfComposedCharactersAtIndex
        find.argtypes = [ctypes.c_void_p, ctypes.c_long]
        find.restype = Range
        release = cf.CFRelease
        release.argtypes = [ctypes.c_void_p]
        release.restype = None
        encoded = text.encode('utf-8')
        value = create(None, encoded, len(encoded), 0x08000100, False)
        if not value:
            raise ValueError('Cannot inspect composed character boundaries.')
        try:
            size = len(text.encode('utf-16-le')) // 2
            result, offset = {0}, 0
            while offset < size:
                part = find(value, offset)
                if part.location != offset or part.length < 1 or offset + part.length > size:
                    raise ValueError('Invalid composed character boundaries.')
                offset += part.length
                result.add(offset)
            units = 0
            for index, char in enumerate(text[:-1]):
                units += 2 if ord(char) > 0xffff else 1
                if char == '\r' and text[index + 1] == '\n':
                    result.discard(units)
            return result
        finally:
            release(value)
    except (OSError, AttributeError, UnicodeError) as exc:
        raise ValueError('Composed character boundaries are unavailable.') from exc


def snapshot(text, runs, semantics=None):
    """Validate contiguous complete coverage while preserving all raw attributes."""
    from ..cues.visual import TextRun
    semantics = semantics or SEMANTICS
    if not isinstance(text, str) or not isinstance(runs, list) or not runs:
        raise ValueError("Complete saved text and format runs are required.")
    total = _units(text, semantics)
    boundaries = _boundaries(text, semantics)
    composed = _composed_boundaries(text) if semantics.index_unit == "utf16" else boundaries
    cursor = 0
    for run in runs:
        TextRun.model_validate(run)
        start, length = run["range"]
        if (start != cursor or length <= 0 or start not in boundaries or start + length not in boundaries
                or start not in composed or start + length not in composed):
            raise ValueError("Format runs must cover text exactly without gaps, overlap or split characters.")
        _json_value(run)
        cursor += length
    if cursor != total:
        raise ValueError("Format run coverage does not match saved text.")
    return {"text": text, "runs": deepcopy(runs)}


def _json_value(value):
    # Extras remain readable, but must be finite JSON data before token binding.
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Format attribute names must be strings.")
        for item in value.values():
            _json_value(item)
    elif isinstance(value, list):
        for item in value:
            _json_value(item)
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("Format baseline contains a nonfinite value.")
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("Format baseline contains a non-JSON value.")


def read(reader, ws, uid, semantics=None):
    from .control import _scalar
    text = _scalar(reader, ws, uid, "text")
    runs = _scalar(reader, ws, uid, "text/format")
    # Detect content changing while its runs were queried.
    if _scalar(reader, ws, uid, "text") != text:
        raise ValueError("Text changed during format snapshot reads.")
    return snapshot(text, runs, semantics)


def _percent(value, total, semantics):
    if type(value) is int:
        return value
    if semantics.percentage_rounding is None:
        raise ValueError("Percentage rounding is pending runtime validation.")
    amount = total * value.percent / 100
    if semantics.percentage_rounding == "floor":
        return math.floor(amount)
    if semantics.percentage_rounding == "ceil":
        return math.ceil(amount)
    return math.floor(amount + 0.5)


def resolve_selector(selected, state, semantics=None):
    semantics = semantics or SEMANTICS
    total = _units(state["text"], semantics)
    if selected.kind == "full":
        return 0, total
    if selected.kind == "word":
        text = state["text"]
        if semantics.word_tokenization == "ascii_space":
            valid = re.fullmatch(r"[A-Za-z0-9 ]+", text) is not None
        else:
            valid = semantics.word_tokenization == "latin_delimiters" and all(
                char in " \t\r\n\u00a0«»“”—" or char.isascii() and char.isalnum()
                or unicodedata.name(char, "").startswith("LATIN ") and char.isalpha()
                for char in text)
        if not valid:
            raise ValueError("Native word tokenization is unverified for this text; use explicit UTF-16 ranges.")
        words = list(re.finditer(r"[^\W_]+", text))
        if selected.index >= len(words):
            raise ValueError("Text word index is outside saved text.")
        word = words[selected.index]
        return _units(text[:word.start()], semantics), _units(word.group(), semantics)
    if not semantics.ranges_verified:
        raise ValueError("Native range semantics are pending runtime validation.")
    start = _percent(selected.index, total, semantics)
    length = total - start if selected.length == -1 else _percent(selected.length, total, semantics)
    boundaries = _boundaries(state["text"], semantics)
    if length <= 0 or start < 0 or start + length > total:
        raise ValueError("Text range is empty or outside saved text.")
    if start not in boundaries or start + length not in boundaries:
        raise ValueError("Text range splits a native Unicode character.")
    if semantics.index_unit == "utf16":
        composed = _composed_boundaries(state["text"])
        if start not in composed or start + length not in composed:
            raise ValueError("Text range splits a composed Unicode character.")
    return start, length


def _attributes(operation):
    attrs = operation.args.attributes.model_dump(exclude_unset=True)
    if "fontFamilyAndStyle" in attrs:
        pair = attrs.pop("fontFamilyAndStyle")
        attrs.update(fontFamily=pair["family"], fontStyle=pair["style"])
    return attrs


def _font_attributes(state, attrs):
    if not {"fontName", "fontFamily", "fontStyle"} & attrs.keys():
        return attrs
    fields = ("fontName", "fontFamily", "fontStyle")
    candidates = {tuple(run.get(key) for key in fields) for run in state["runs"]
                  if all(run.get(key) == value for key, value in attrs.items() if key in fields)}
    if not candidates or any(None in candidate for candidate in candidates):
        raise ValueError("Font resolution requires complete companion metadata already observed in this cue.")
    if len(candidates) != 1:
        raise ValueError("Observed font companion metadata is ambiguous.")
    return {**attrs, **dict(zip(fields, next(iter(candidates)), strict=True))}


def _is_cjk(char):
    name = unicodedata.name(char, "")
    return name.startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY", "HANGUL ",
                            "HIRAGANA ", "KATAKANA ", "IDEOGRAPHIC ", "BOPOMOFO "))


def _unicode_scope(state, start, length, semantics, *, color_only=False):
    encoded = state["text"].encode("utf-16-le") if semantics.index_unit == "utf16" else None
    selected = encoded[start*2:(start+length)*2].decode("utf-16-le") if encoded is not None else state["text"][start:start+length]
    if any(not (char.isascii() or unicodedata.name(char, "").startswith("LATIN ") or 0x300 <= ord(char) <= 0x36f
                or color_only and char in "\u00a0«»“”—" or _is_cjk(char)) for char in selected):
        raise ValueError("Font fallback for emoji and this script is not validated; use a supported Latin or CJK range.")


def _coretext_fallback(font_name, font_size, text):
    """Return Core Text's concrete font for a grapheme without opening a text view."""
    class Range(ctypes.Structure):
        _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]

    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    create_string = cf.CFStringCreateWithBytes
    create_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32, ctypes.c_bool]
    create_string.restype = ctypes.c_void_p
    copy_font = ct.CTFontCreateWithName
    copy_font.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_void_p]
    copy_font.restype = ctypes.c_void_p
    for_string = ct.CTFontCreateForString
    for_string.argtypes = [ctypes.c_void_p, ctypes.c_void_p, Range]
    for_string.restype = ctypes.c_void_p
    postscript = ct.CTFontCopyPostScriptName
    postscript.argtypes = [ctypes.c_void_p]
    postscript.restype = ctypes.c_void_p
    get_string = cf.CFStringGetCString
    get_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    get_string.restype = ctypes.c_bool
    release = cf.CFRelease
    release.argtypes = [ctypes.c_void_p]
    encoding = 0x08000100
    name_data = font_name.encode("utf-8")
    text_data = text.encode("utf-8")
    name = create_string(None, name_data, len(name_data), encoding, False)
    string = create_string(None, text_data, len(text_data), encoding, False)
    font = resolved = resolved_name = None
    try:
        if not name or not string:
            raise ValueError("Core Text could not create a font query.")
        font = copy_font(name, float(font_size), None)
        if not font:
            raise ValueError("Core Text could not resolve the observed font.")
        units = len(text.encode("utf-16-le")) // 2
        resolved = for_string(font, string, Range(0, units))
        resolved_name = postscript(resolved) if resolved else None
        if not resolved_name:
            raise ValueError("Core Text could not resolve the selected grapheme.")
        buffer = ctypes.create_string_buffer(1024)
        if not get_string(resolved_name, buffer, len(buffer), encoding):
            raise ValueError("Core Text returned an unreadable font name.")
        return buffer.value.decode("utf-8")
    except (OSError, AttributeError, UnicodeError, TypeError, OverflowError) as exc:
        raise ValueError("Core Text font fallback could not be verified.") from exc
    finally:
        for value in (resolved_name, resolved, font, string, name):
            if value:
                release(value)


def _cjk_fallbacks(state, spans, semantics=None):
    semantics = semantics or SEMANTICS
    text = state["text"]
    encoded = text.encode("utf-16-le")
    bounds = sorted(_composed_boundaries(text)) if semantics.index_unit == "utf16" else sorted(_boundaries(text, semantics))
    rows = []
    for start, end in zip(bounds, bounds[1:]):
        if not any(a <= start and end <= b for a, b in spans):
            continue
        cluster = encoded[start * 2:end * 2].decode("utf-16-le") if semantics.index_unit == "utf16" else text[start:end]
        if not any(_is_cjk(char) for char in cluster):
            continue
        run = next((item for item in state["runs"]
                    if item["range"][0] <= start and start + item["range"][1] >= end), None)
        if run is None or not isinstance(run.get("fontName"), str) or type(run.get("fontSize")) not in (int, float):
            raise ValueError("CJK formatting requires an observed font name and size for every selected run.")
        fallback = _coretext_fallback(run["fontName"], run["fontSize"], cluster)
        rows.append({"range": [start, end - start], "fontName": run["fontName"],
                     "fontSize": run["fontSize"], "fallback": fallback})
    return rows


def validate_cjk_fallbacks(before, after, spans, semantics=None):
    """Allow a CJK edit only when Core Text preserves fallback or selects the requested font."""
    old, new = _cjk_fallbacks(before, spans, semantics), _cjk_fallbacks(after, spans, semantics)
    if len(old) != len(new):
        raise ValueError("CJK font coverage changed during preview.")
    for previous, requested in zip(old, new, strict=True):
        if previous["range"] != requested["range"]:
            raise ValueError("CJK grapheme identity changed during preview.")
        if previous["fallback"] != previous["fontName"]:
            raise ValueError("The observed font substitutes this CJK grapheme; setter blocked.")
        if previous["fontName"] == requested["fontName"]:
            if requested["fallback"] != requested["fontName"]:
                raise ValueError("Requested formatting changes Core Text's CJK fallback; setter blocked.")
        elif requested["fallback"] != requested["fontName"]:
            raise ValueError("Requested font does not cover every selected CJK grapheme; setter blocked.")
    return new


def _cjk_spans(state, spans, semantics):
    text = state["text"]
    encoded = text.encode("utf-16-le") if semantics.index_unit == "utf16" else None
    result = []
    for start, length in spans:
        selected = (encoded[start * 2:(start + length) * 2].decode("utf-16-le")
                    if encoded is not None else text[start:start + length])
        if any(_is_cjk(char) for char in selected):
            result.append((start, start + length))
    return result


def advance(state, operation, semantics=None):
    """Return expected effective intervals, never synthesize absent defaults."""
    operation = TextFormatOperation.model_validate(operation)
    semantics = semantics or SEMANTICS
    state = snapshot(state["text"], state["runs"], semantics)
    start, length = resolve_selector(operation.args.selector, state, semantics)
    end = start + length
    attrs = _font_attributes(state, _attributes(operation))
    # Even color can trigger emoji fallback; punctuation is separately verified.
    _unicode_scope(state, start, length, semantics, color_only=attrs.keys() == {"color"})
    if _SHADOWS & attrs.keys() and operation.args.selector.kind != "full":
        raise ValueError("Partial shadows affect a line; native line scope is pending runtime validation.")
    if attrs.keys() - semantics.json_attributes:
        raise ValueError("JSON formatting transport is pending runtime validation for: " + ", ".join(sorted(attrs.keys() - semantics.json_attributes)))
    expected = {"text": state["text"], "runs": []}
    for run in state["runs"]:
        left, size = run["range"]
        right = left + size
        overlaps = left < end and start < right
        if overlaps and any(key not in run or run[key] is None for key in attrs):
            raise ValueError("Requested attributes are absent in affected runs; no reliable baseline.")
        cuts = sorted({left, right, max(left, min(right, start)), max(left, min(right, end))})
        for a, b in zip(cuts, cuts[1:]):
            if a == b:
                continue
            fragment = deepcopy(run)
            fragment["range"] = [a, b-a]
            if overlaps and a >= start and b <= end:
                fragment.update(deepcopy(attrs))
            expected["runs"].append(fragment)
    return expected


def preflight(state, operations, properties=None, semantics=None):
    """Reject dependent content edits and overlapping attribute destinations."""
    if properties and "text" in properties:
        raise ValueError("Separate content replacement and formatting with a fresh dry run.")
    semantics = semantics or SEMANTICS
    state = snapshot(state["text"], state["runs"], semantics)
    if not 1 <= len(operations) <= 50:
        raise ValueError("Provide 1–50 Text formatting operations.")
    operations = [TextFormatOperation.model_validate(op) for op in operations]
    occupied = []
    selected_spans = []
    expected = state
    for operation in operations:
        start, length = resolve_selector(operation.args.selector, state, semantics)
        selected_spans.append((start, length))
        attrs = set(_font_attributes(state, _attributes(operation)))
        for a, b, previous in occupied:
            if start < b and a < start + length and attrs & previous:
                raise ValueError("Overlapping Text formatting destinations require separate dry runs.")
        scalar_attrs = {key.removeprefix("text/format/").split("/")[0] for key in properties or {} if key.startswith("text/format/")}
        if scalar_attrs & attrs or (scalar_attrs & {"fontName", "fontFamilyAndStyle"} and attrs & {"fontName", "fontFamily", "fontStyle"}):
            raise ValueError("Use a property or a format operation for each destination.")
        occupied.append((start, start+length, attrs))
        expected = advance(expected, operation, semantics)
    cjk = _cjk_spans(state, selected_spans, semantics)
    if cjk:
        validate_cjk_fallbacks(state, expected, cjk, semantics)
    return expected


def normalize(operation, index=0, state=None, semantics=None):
    """One saved JSON setter, keyed uniquely for confirmation binding."""
    operation = TextFormatOperation.model_validate(operation)
    attrs = _attributes(operation)
    if state is None:
        raise ValueError("Text formatting normalization requires a complete baseline.")
    advance(state, operation, semantics)  # Validate transport and scope before producing a setter.
    if {"fontFamily", "fontStyle"} & attrs.keys():
        resolved = _font_attributes(state, attrs)
        attrs = {key: value for key, value in attrs.items() if key not in {"fontFamily", "fontStyle"}}
        attrs["fontName"] = resolved["fontName"]
    if operation.args.selector.kind != "full":
        attrs["range"] = list(resolve_selector(operation.args.selector, state, semantics))
    return {"property": f"text/format@{index}", "path": "text/format",
            "args": [json.dumps(attrs, ensure_ascii=False, allow_nan=False, separators=(",", ":"))],
            "arg_values": operation.args.model_dump(exclude_unset=True),
            "real_write_enabled": True, "real_write_possible": True, "requires_confirm_token": True}


def _same(a, b):
    if type(a) in (float, int) and type(b) in (float, int):
        return math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-6)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def matches(observed, expected, semantics=None):
    """Compare full coverage and every attribute; allow equivalent split/merged runs."""
    try:
        observed = snapshot(observed["text"], observed["runs"], semantics)
        expected = snapshot(expected["text"], expected["runs"], semantics)
    except (ValueError, TypeError, KeyError):
        return False
    if observed["text"] != expected["text"]:
        return False
    i = j = 0
    while i < len(observed["runs"]) and j < len(expected["runs"]):
        a, b = observed["runs"][i], expected["runs"][j]
        if not _same({k: v for k, v in a.items() if k != "range"}, {k: v for k, v in b.items() if k != "range"}):
            return False
        a_end, b_end = sum(a["range"]), sum(b["range"])
        if a_end <= b_end:
            i += 1
        if b_end <= a_end:
            j += 1
    return i == len(observed["runs"]) and j == len(expected["runs"])


def check_dependencies(reader, ws, uid, expected, semantics=None):
    if not matches(read(reader, ws, uid, semantics), expected, semantics):
        raise ValueError("Saved text or effective formatting changed before setter.")


def capabilities():
    return {"property": "text/format", "selectors": ["full", "range", "word"],
            "requires_complete_text_and_runs": True,
            "pending_validation": ["other word delimiters and contractions", "unobserved font companion metadata", "emoji and non-CJK fallback", "partial shadow line scope"],
            "native_index_unit": SEMANTICS.index_unit,
            "ranges_verified": SEMANTICS.ranges_verified,
            "unicode_scope": "ASCII/Latin and CJK selections; CJK requires Core Text fallback to remain stable for the selected graphemes",
            "color_only_extra_characters": list("\u00a0«»“”—"),
            "conditional_cjk_formatting": "Allowed only when Core Text reports unchanged fallback before and after the planned edit",
            "unicode_formatting_pending": True,
            "percentage_rounding": SEMANTICS.percentage_rounding,
            "word_tokenization": SEMANTICS.word_tokenization,
            "word_delimiters": ["space", "tab", "LF", "CR", "NBSP", "«", "»", "“", "”", "—"],
            "font_scope": "Complete fontName/family/style mapping already observed in the same cue",
            "validated_json_attributes": sorted(SEMANTICS.json_attributes)}
