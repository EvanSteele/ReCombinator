from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from .models import Article
from .text import clean_paragraphs, normalize_whitespace, truncate


SKIP_TAGS = {
    "aside",
    "canvas",
    "footer",
    "form",
    "header",
    "nav",
    "noscript",
    "script",
    "style",
    "svg",
}
CONTENT_ROOT_TAGS = {"article", "main"}
BLOCK_TAGS = {
    "article",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "main",
    "p",
    "pre",
    "section",
    "td",
    "th",
    "tr",
}
BOILERPLATE_PATTERNS = [
    r"\bcookie\b",
    r"\bsubscribe\b",
    r"\bsign in\b",
    r"\bsign up\b",
    r"\badvertisement\b",
    r"\badvertise\b",
    r"\bprivacy policy\b",
    r"\bterms of service\b",
    r"\baccept all\b",
    r"\bshare this\b",
    r"\bwant to add to the discussion\b",
    r"\brendered by pid\b",
    r"\bbecome a redditor\b",
    r"\bsubmit a new (link|text post)\b",
]
INLINE_BOILERPLATE_PATTERNS = [
    r"\bSkip to main content\b",
    r"\bShare\s+Facebook\s+LinkedIn\s+Mail\s+Copy link\b",
    r"\bGenerative AI is experimental\s+Voice Speed(?:\s+[0-9.]+X)+\b",
    r"\bWant to add to the discussion\?.*$",
    r"\bAdvertise\s+-\s+technology\b.*$",
    r"\bRendered by PID\b.*$",
    r"^\d+\s+\d+\s+(?=[A-Z])",
]


def extract_article(url: str, html: str, content_type: str = "", max_chars: int = 12000) -> Article:
    if _is_reddit_url(url):
        return _extract_reddit_article(url, html, max_chars=max_chars)

    if _looks_like_html(content_type, html):
        parser = ReadableTextParser()
        parser.feed(html)
        title = normalize_whitespace(parser.title or "") or None
        paragraphs = _filter_paragraphs(clean_paragraphs("\n".join(parser.parts)))
        text = "\n\n".join(paragraphs)
    else:
        title = None
        text = "\n\n".join(clean_paragraphs(html))

    return Article(url=url, title=title, text=truncate(text, max_chars), fetched=True)


class RedditSubmissionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.selftext_parts: list[str] = []
        self._in_comment_area = False
        self._capture_title = False
        self._capture_title_parts: list[str] = []
        self._capture_selftext_depth = 0
        self._thing_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        classes = set(attrs_dict.get("class", "").split())

        if self._thing_depth:
            self._thing_depth += 1

        if "commentarea" in classes:
            self._in_comment_area = True

        if self._capture_selftext_depth:
            self._capture_selftext_depth += 1
            if tag in BLOCK_TAGS:
                self.selftext_parts.append("\n")
            return

        if tag == "div" and "thing" in classes and not self._in_comment_area:
            self._thing_depth = 1

        if tag == "a" and "title" in classes and self.title is None and self._thing_depth:
            self._capture_title = True
            self._capture_title_parts = []
        elif (
            tag in {"div", "span"}
            and "usertext-body" in classes
            and not self._in_comment_area
            and self._thing_depth
        ):
            self._capture_selftext_depth = 1
            self.selftext_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._capture_selftext_depth:
            self._capture_selftext_depth -= 1
            if tag in BLOCK_TAGS:
                self.selftext_parts.append("\n")
            return

        if tag == "a" and self._capture_title:
            title = normalize_whitespace(" ".join(self._capture_title_parts))
            self.title = title or None
            self._capture_title = False
            self._capture_title_parts = []

        if self._thing_depth:
            self._thing_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._capture_title_parts.append(data)
        elif self._capture_selftext_depth:
            self.selftext_parts.append(data)


class ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.parts: list[str] = []
        self._skip_depth = 0
        self._content_depth = 0
        self._using_content_root = False
        self._capture_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in CONTENT_ROOT_TAGS:
            if not self._using_content_root:
                self._using_content_root = True
                self.parts = []
            self._content_depth += 1

        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._capture_title = True
            self._title_parts = []
        if not self._collecting_body_text():
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag in SKIP_TAGS:
                self._skip_depth -= 1
            return
        if tag == "title" and self._capture_title:
            self.title = normalize_whitespace(" ".join(self._title_parts))
            self._capture_title = False
            self._title_parts = []
        if self._collecting_body_text() and tag in BLOCK_TAGS:
            self.parts.append("\n")
        if tag in CONTENT_ROOT_TAGS and self._content_depth:
            self._content_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture_title:
            self._title_parts.append(data)
        elif self._collecting_body_text():
            self.parts.append(data)

    def _collecting_body_text(self) -> bool:
        return not self._using_content_root or self._content_depth > 0


def _looks_like_html(content_type: str, value: str) -> bool:
    lowered = content_type.casefold()
    if "html" in lowered or "xml" in lowered:
        return True
    start = value.lstrip()[:200].casefold()
    return "<html" in start or "<!doctype html" in start


def _is_reddit_url(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return host == "reddit.com" or host.endswith(".reddit.com")


def _extract_reddit_article(url: str, html: str, max_chars: int) -> Article:
    parser = RedditSubmissionParser()
    parser.feed(html)
    title = normalize_whitespace(parser.title or "") or _title_from_html(html)
    paragraphs = _filter_paragraphs(clean_paragraphs("\n".join(parser.selftext_parts)))

    text_parts = []
    if title:
        text_parts.append(title)
    text_parts.extend(paragraphs)
    text = "\n\n".join(text_parts)
    return Article(url=url, title=title, text=truncate(text, max_chars), fetched=True)


def _title_from_html(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    title = re.sub(r"\s*:\s*[^:]+$", "", title)
    return normalize_whitespace(title) or None


def _filter_paragraphs(paragraphs: list[str]) -> list[str]:
    filtered = []
    for paragraph in paragraphs:
        paragraph = _strip_inline_boilerplate(paragraph)
        lowered = paragraph.casefold()
        if len(paragraph) < 35 and not re.match(r"^#{0,6}\s*[A-Z0-9]", paragraph):
            continue
        if any(re.search(pattern, lowered) for pattern in BOILERPLATE_PATTERNS):
            continue
        if _link_farm_like(paragraph):
            continue
        filtered.append(paragraph)
    return filtered


def _strip_inline_boilerplate(paragraph: str) -> str:
    cleaned = paragraph
    for pattern in INLINE_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return normalize_whitespace(cleaned)


def _link_farm_like(paragraph: str) -> bool:
    if len(paragraph) > 240:
        return False
    words = paragraph.split()
    if len(words) < 8:
        return False
    short_words = sum(1 for word in words if len(word) <= 3)
    return short_words / len(words) > 0.7
