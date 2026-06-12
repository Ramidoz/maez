"""Page digestion for the Page-Read Sense (spec 2026-06-12).

stdlib only. Quality bar: honest bounded text, not beauty. Garbage in becomes
empty out; the caller maps empty to an honest EMPTY failure, never fake page
content.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser


MAX_EXTRACT_CHARS = 6000
_SKIP_SUBTREES = frozenset({"script", "style", "noscript", "nav", "header", "footer", "svg"})
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def extract_first_url(text: str) -> str | None:
    """The one owner-URL notion shared by the Layer0 arm and the stash."""
    match = _URL_RE.search(text or "")
    return match.group(0) if match else None


class _ReadableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        del attrs
        if tag in _SKIP_SUBTREES:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in _SKIP_SUBTREES and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):  # noqa: ANN001
        if self._in_title:
            self.title_parts.append(data)
        elif self._skip_depth == 0:
            self.text_parts.append(data)


def extract_readable(raw: str, *, content_type: str) -> tuple[str, str]:
    """Return (title, bounded_text). Empty strings on anything unreadable."""
    try:
        if not raw or not raw.strip():
            return "", ""
        base_type = (content_type or "").split(";", 1)[0].strip().lower()
        if base_type == "text/plain":
            return "", " ".join(raw.split())[:MAX_EXTRACT_CHARS]
        parser = _ReadableParser()
        parser.feed(raw)
        parser.close()
        title = " ".join("".join(parser.title_parts).split())[:200]
        text = " ".join("".join(parser.text_parts).split())[:MAX_EXTRACT_CHARS]
        if text and not re.search(r"[A-Za-z0-9]", text):
            text = ""
        return title, text
    except Exception:
        return "", ""
