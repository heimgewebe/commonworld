#!/usr/bin/env python3
"""Shared standard-library parsers for the static public surfaces.

This module centralises the HTML link, presence-group and CSS block parsing that
the ``validate_public_shell`` and ``validate_proposal_path`` gates rely on, so
neither validator carries its own copy of the logic. Everything here uses only
the Python standard library and holds no module-level mutable state, which keeps
it safe to import both as ``scripts.static_surface_parser`` (package/importlib
context) and as ``static_surface_parser`` (direct script execution with the
``scripts`` directory on ``sys.path``).
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterator, Sequence

# HTML void elements never receive an explicit end tag, so a depth stack must not
# expect one for them.
_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


# --------------------------------------------------------------------------- #
# Stylesheet links
# --------------------------------------------------------------------------- #
class _StylesheetLinkParser(HTMLParser):
    """Collect ``<link rel="stylesheet">`` hrefs in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        attr = dict(attrs)
        # rel is an unordered, case-insensitive token list (e.g. "stylesheet preload").
        rel_tokens = {token.casefold() for token in (attr.get("rel") or "").split()}
        href = attr.get("href")
        if "stylesheet" in rel_tokens and href:
            self.links.append(href)


def parse_stylesheet_links(html_text: str) -> list[str]:
    """Return every stylesheet href in source order.

    Attribute order, quoting style and extra ``rel`` tokens are all tolerated
    because the HTML is parsed structurally rather than by string matching.
    """

    parser = _StylesheetLinkParser()
    parser.feed(html_text)
    return parser.links


# --------------------------------------------------------------------------- #
# Presence group
# --------------------------------------------------------------------------- #
@dataclass
class PresenceStructure:
    """Structural summary of the intent-filter presence group."""

    fieldset_count: int = 0
    options_wrapper_count: int = 0
    legend_count: int = 0
    geographic_count: int = 0
    digital_count: int = 0

    @property
    def has_legend(self) -> bool:
        return self.legend_count > 0

    @property
    def has_both_checkboxes(self) -> bool:
        return self.geographic_count == 1 and self.digital_count == 1


class _PresenceParser(HTMLParser):
    """Depth-aware parser for the ``.filter-presence-group`` fieldset.

    A tag stack tracks whether the current node is inside the presence fieldset
    and inside its ``.filter-presence-options`` wrapper, so arbitrarily nested
    ``<div>`` layers, reordered attributes and mixed quoting do not confuse the
    presence accounting.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.result = PresenceStructure()
        self._stack: list[dict[str, object]] = []

    def _inside(self, key: str) -> bool:
        return any(frame[key] for frame in self._stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._process(tag, attrs, push=tag not in _VOID_ELEMENTS)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._process(tag, attrs, push=False)

    def _process(self, tag: str, attrs: list[tuple[str, str | None]], push: bool) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        inside_fieldset = self._inside("presence_fieldset")
        inside_wrapper = self._inside("options_wrapper")
        frame = {"tag": tag, "presence_fieldset": False, "options_wrapper": False}

        if tag == "fieldset" and "filter-presence-group" in classes:
            self.result.fieldset_count += 1
            frame["presence_fieldset"] = True
        elif tag == "legend" and inside_fieldset:
            self.result.legend_count += 1
        elif tag == "div" and "filter-presence-options" in classes and inside_fieldset:
            self.result.options_wrapper_count += 1
            frame["options_wrapper"] = True
        elif (
            tag == "input"
            and inside_wrapper
            and (attr.get("type") or "").strip().casefold() == "checkbox"
        ):
            checkbox_id = attr.get("id")
            if checkbox_id == "filter-presence-geographic":
                self.result.geographic_count += 1
            elif checkbox_id == "filter-presence-digital":
                self.result.digital_count += 1

        if push:
            self._stack.append(frame)

    def handle_endtag(self, tag: str) -> None:
        # Pop back to the nearest matching open tag, tolerating unbalanced markup.
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag:
                del self._stack[index:]
                return


def parse_presence_group(html_text: str) -> PresenceStructure:
    """Return the structural presence summary for ``html_text``."""

    parser = _PresenceParser()
    parser.feed(html_text)
    return parser.result


# --------------------------------------------------------------------------- #
# CSS blocks
# --------------------------------------------------------------------------- #
def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` comments while preserving string literals."""

    out: list[str] = []
    i = 0
    length = len(text)
    in_string: str | None = None
    while i < length:
        char = text[i]
        if in_string is not None:
            out.append(char)
            if char == "\\" and i + 1 < length:
                out.append(text[i + 1])
                i += 2
                continue
            if char == in_string:
                in_string = None
            i += 1
            continue
        if text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = length if end == -1 else end + 2
            continue
        if char in ("'", '"'):
            in_string = char
            out.append(char)
            i += 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _clean_selector(raw: str) -> str:
    """Normalise a selector prelude: drop comments and collapse whitespace."""

    return " ".join(_strip_comments(raw).split())


def iter_css_blocks(css: str) -> Iterator[tuple[str, str]]:
    """Yield ``(selector, body)`` for every top-level CSS block.

    The scan is comment-, string- and brace-safe: braces that appear inside
    comments or string literals are ignored, and nested blocks (for example
    rules inside an ``@media`` query) stay attached to their top-level owner.
    """

    i = 0
    length = len(css)
    prelude_start = 0
    in_string: str | None = None
    in_comment = False

    while i < length:
        if in_comment:
            if css[i : i + 2] == "*/":
                in_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string is not None:
            char = css[i]
            if char == "\\":
                i += 2
            elif char == in_string:
                in_string = None
                i += 1
            else:
                i += 1
            continue
        if css[i : i + 2] == "/*":
            in_comment = True
            i += 2
            continue
        char = css[i]
        if char in ("'", '"'):
            in_string = char
            i += 1
            continue
        if char == "{":
            selector = _clean_selector(css[prelude_start:i])
            body_start = i + 1
            i = body_start
            depth = 1
            inner_string: str | None = None
            inner_comment = False
            while i < length and depth > 0:
                if inner_comment:
                    if css[i : i + 2] == "*/":
                        inner_comment = False
                        i += 2
                    else:
                        i += 1
                    continue
                if inner_string is not None:
                    inner_char = css[i]
                    if inner_char == "\\":
                        i += 2
                    elif inner_char == inner_string:
                        inner_string = None
                        i += 1
                    else:
                        i += 1
                    continue
                if css[i : i + 2] == "/*":
                    inner_comment = True
                    i += 2
                    continue
                inner_char = css[i]
                if inner_char in ("'", '"'):
                    inner_string = inner_char
                    i += 1
                    continue
                if inner_char == "{":
                    depth += 1
                elif inner_char == "}":
                    depth -= 1
                i += 1
            body = css[body_start : i - 1] if depth == 0 else css[body_start:]
            yield (selector, body)
            prelude_start = i
            continue
        if char == "}":
            # Stray closing brace: begin a fresh prelude.
            prelude_start = i + 1
            i += 1
            continue
        if char == ";":
            # A top-level statement terminator (e.g. @charset/@import) ends the
            # current prelude so it cannot bleed into the following selector.
            prelude_start = i + 1
            i += 1
            continue
        i += 1


def find_css_block(css: str, target_selector: str) -> tuple[str, str] | None:
    """Return the ``(selector, body)`` of the block matching ``target_selector``.

    The target must appear as an exact member of the block's comma-separated
    selector list, so neither a descendant selector such as ``.wrapper
    .layer-discovery`` nor a near-miss such as ``.layer-discovery-alt`` is ever
    mistaken for an exact ``.layer-discovery`` rule.
    """

    target = " ".join(target_selector.split())
    for selector, body in iter_css_blocks(css):
        for part in selector.split(","):
            if part.strip() == target:
                return (selector, body)
    return None


def _normalize_media_query(text: str) -> str:
    """Fold comments, whitespace and case out of a media prelude/token.

    This lets required feature tokens be compared regardless of comments,
    spacing around colons or the casing used in the stylesheet.
    """

    return "".join(_strip_comments(text).split()).casefold()


def find_media_block(css: str, required_tokens: Sequence[str]) -> tuple[str, str] | None:
    """Return the ``@media`` block whose prelude contains every required token.

    This lets a caller find its target media query by its actual feature tests
    regardless of unrelated media queries emitted before it or plain rules after.
    Comments, whitespace and case are normalised on both sides before matching.
    """

    wanted = [_normalize_media_query(token) for token in required_tokens]
    for selector, body in iter_css_blocks(css):
        normalized = _normalize_media_query(selector)
        if normalized.startswith("@media") and all(token in normalized for token in wanted):
            return (selector, body)
    return None
