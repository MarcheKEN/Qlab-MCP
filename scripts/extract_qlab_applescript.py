#!/usr/bin/env python3
"""Fetch and convert QLab's AppleScript Dictionary to repository Markdown.

The converter deliberately uses the standard library so the imported reference
can be regenerated without adding a project dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


SOURCE_URL = "https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML = PROJECT_ROOT / "docs/sources/qlab-5-applescript/applescript_dictionary_v5.local.html"
DEFAULT_MARKDOWN = PROJECT_ROOT / "docs/references/qlab_applescript_dictionary.md"
DEFAULT_SKILL_COPY = PROJECT_ROOT / "skills/qlab-5-applescript/references/qlab_applescript_dictionary.md"
_UNIQUE_ANCHORS: set[str] = set()


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)


class TreeParser(html.parser.HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag.lower() not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self.VOID and len(self.stack) > 1:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def descendants(node: Node, tag: str | None = None):
    for child in node.children:
        if isinstance(child, Node):
            if tag is None or child.tag == tag:
                yield child
            yield from descendants(child, tag)


def has_class(node: Node, fragment: str) -> bool:
    return fragment in node.attrs.get("class", "").split()


def find_content(root: Node) -> Node:
    for node in descendants(root, "div"):
        if has_class(node, "markdown-table-docs"):
            return node
    raise ValueError("could not find QLab documentation content container")


def text_content(node: Node, *, skip: set[str] | None = None) -> str:
    skip = skip or set()
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag not in skip:
            parts.append(text_content(child, skip=skip))
    return "".join(parts)


def clean_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def href_for(href: str) -> str:
    absolute = urljoin(SOURCE_URL, href)
    source = urlparse(SOURCE_URL)
    target = urlparse(absolute)
    if target.netloc == source.netloc and target.path.rstrip("/") == source.path.rstrip("/"):
        return f"#{target.fragment}" if target.fragment else "./"
    return absolute


def inline(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    if node.tag in {"button", "svg", "script", "style"}:
        return ""
    if node.attrs.get("data-name") == "checkmark":
        return "✓"
    if node.tag == "br":
        return "  \n"
    if node.tag == "a":
        label = clean_inline("".join(inline(child) for child in node.children))
        return f"[{label}]({href_for(node.attrs.get('href', ''))})" if node.attrs.get("href") else label
    if node.tag == "img":
        alt = node.attrs.get("alt", "image")
        src = urljoin(SOURCE_URL, node.attrs.get("src", ""))
        return f"![{alt}]({src})"
    content = "".join(inline(child) for child in node.children)
    if node.tag in {"strong", "b"}:
        return f"**{content.strip()}**"
    if node.tag in {"em", "i"}:
        return f"*{content.strip()}*"
    if node.tag == "code":
        return f"`{content.strip()}`"
    return content


def render_list(node: Node, depth: int = 0) -> str:
    ordered = node.tag == "ol"
    lines: list[str] = []
    number = 1
    for child in node.children:
        if not isinstance(child, Node) or child.tag != "li":
            continue
        marker = f"{number}." if ordered else "-"
        value: list[str] = []
        nested: list[str] = []
        for part in child.children:
            if isinstance(part, Node) and part.tag in {"ul", "ol"}:
                nested.append(render_list(part, depth + 1))
            else:
                value.append(inline(part))
        text = clean_inline("".join(value))
        lines.append(f"{'  ' * depth}{marker} {text}".rstrip())
        for block in nested:
            lines.extend(f"{'  ' * (depth + 1)}{line}" for line in block.splitlines())
        number += 1
    return "\n".join(lines)


def render_table(node: Node) -> str:
    rows: list[tuple[str, list[str]]] = []
    for row in descendants(node, "tr"):
        cells: list[str] = []
        kind = "td"
        for cell in row.children:
            if isinstance(cell, Node) and cell.tag in {"th", "td"}:
                kind = "th" if cell.tag == "th" else kind
                value = clean_inline(inline(cell)).replace("|", "\\|")
                cells.append(value)
        if cells:
            rows.append((kind, cells))
    if not rows:
        return ""
    width = max(len(cells) for _, cells in rows)
    normalized = [cells + [""] * (width - len(cells)) for _, cells in rows]
    lines = ["| " + " | ".join(normalized[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(cells) + " |" for cells in normalized[1:])
    return "\n".join(lines)


def render_pre(node: Node) -> str:
    code_nodes = list(descendants(node, "code"))
    code_node = code_nodes[-1] if code_nodes else node
    language = ""
    for candidate in descendants(node, "div"):
        if "font-mono" in candidate.attrs.get("class", ""):
            candidate_text = clean_inline(text_content(candidate, skip={"svg", "button"}))
            if candidate_text:
                language = candidate_text
                break
    code = text_content(code_node, skip={"svg", "button"}).replace("\r\n", "\n").strip("\n")
    return f"```{language}\n{code}\n```"


def render_block(node: Node) -> str:
    if node.tag in {"script", "style", "button", "svg"}:
        return ""
    if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        title = clean_inline("".join(inline(child) for child in node.children if not isinstance(child, Node) or child.tag != "button"))
        anchor_id = node.attrs.get("id", "")
        anchor = f"<a id=\"{anchor_id}\"></a>\n" if anchor_id in _UNIQUE_ANCHORS else ""
        return f"{anchor}{'#' * int(node.tag[1:])} {title}"
    if node.tag == "hr":
        return "---"
    if node.tag in {"p", "div"}:
        return "".join(render_block(child) if isinstance(child, Node) and child.tag in {"h1", "h2", "h3", "h4", "h5", "h6", "hr", "table", "pre", "ul", "ol", "p"} else inline(child) for child in node.children).strip()
    if node.tag in {"ul", "ol"}:
        return render_list(node)
    if node.tag == "table":
        return render_table(node)
    if node.tag == "pre":
        return render_pre(node)
    return "".join(render_block(child) if isinstance(child, Node) else child for child in node.children).strip()


def to_markdown(raw_html: str) -> str:
    global _UNIQUE_ANCHORS
    parser = TreeParser()
    parser.feed(raw_html)
    content = find_content(parser.root)
    ids = [node.attrs["id"] for node in descendants(content) if node.attrs.get("id")]
    _UNIQUE_ANCHORS = {anchor_id for anchor_id in ids if ids.count(anchor_id) == 1}
    blocks: list[str] = ["# QLab's AppleScript Dictionary"]
    for child in content.children:
        if not isinstance(child, Node):
            continue
        rendered = render_block(child).strip()
        if rendered:
            blocks.append(rendered)
    markdown = "\n\n".join(blocks)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.rstrip() + "\n"


def fetch_source() -> bytes:
    request = Request(SOURCE_URL, headers={"User-Agent": "qlab-mcp-osc documentation snapshot"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-html", type=Path, help="Use an existing HTML file instead of downloading")
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--skill-copy", type=Path, default=DEFAULT_SKILL_COPY)
    parser.add_argument("--check", action="store_true", help="Check generated Markdown and portable copy")
    args = parser.parse_args()

    if args.check:
        raw_html = args.html_output.read_text(encoding="utf-8")
        expected = to_markdown(raw_html)
        actual = args.markdown_output.read_text(encoding="utf-8")
        portable = args.skill_copy.read_text(encoding="utf-8")
        if expected != actual or portable != actual:
            print("AppleScript reference is not reproducible or portable copy is stale", file=sys.stderr)
            return 1
        print(f"ok: {args.markdown_output} ({sha256(args.markdown_output)})")
        return 0

    raw = args.source_html.read_bytes() if args.source_html else fetch_source()
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.skill_copy.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_bytes(raw)
    markdown = to_markdown(raw.decode("utf-8"))
    args.markdown_output.write_text(markdown, encoding="utf-8")
    shutil.copyfile(args.markdown_output, args.skill_copy)
    print(f"html: {args.html_output} ({sha256(args.html_output)})")
    print(f"markdown: {args.markdown_output} ({sha256(args.markdown_output)})")
    print(f"portable: {args.skill_copy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
