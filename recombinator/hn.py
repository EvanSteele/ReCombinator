from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .models import Comment, Story
from .text import normalize_whitespace


HN_BASE_URL = "https://news.ycombinator.com/"
HN_NEWS_URL = urljoin(HN_BASE_URL, "news")


def parse_front_page(html: str, limit: int | None = None) -> list[Story]:
    parser = HNFrontPageParser()
    parser.feed(html)
    stories = parser.stories
    if limit is not None:
        return stories[:limit]
    return stories


def parse_comments(html: str, limit: int | None = None) -> list[Comment]:
    parser = HNCommentParser()
    parser.feed(html)
    comments = parser.comments
    if limit is not None:
        return comments[:limit]
    return comments


def story_discussion_url(story_id: int) -> str:
    return urljoin(HN_BASE_URL, f"item?id={story_id}")


class HNFrontPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stories: list[Story] = []
        self._current: dict[str, object] | None = None
        self._in_athing = False
        self._in_subtext = False
        self._titleline_depth = 0
        self._capture_field: str | None = None
        self._capture_end_tag: str | None = None
        self._capture_parts: list[str] = []
        self._title_href: str | None = None
        self._subtext_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = _attrs(attrs)
        classes = _classes(attrs_dict)

        if tag == "tr" and "athing" in classes:
            self._finish_current()
            story_id = _parse_int(attrs_dict.get("id", ""))
            if story_id is None:
                self._current = None
                return
            self._current = {"id": story_id}
            self._in_athing = True
            return

        if self._current is None:
            return

        if self._titleline_depth:
            self._titleline_depth += 1

        if self._in_athing and tag == "span" and "rank" in classes:
            self._start_capture("rank", "span")
        elif self._in_athing and tag == "span" and "titleline" in classes:
            self._titleline_depth = 1
        elif self._titleline_depth and tag == "a" and "title" not in self._current:
            href = attrs_dict.get("href")
            if href:
                self._title_href = href
                self._start_capture("title", "a")
        elif self._in_athing and tag == "span" and "sitestr" in classes:
            self._start_capture("site", "span")
        elif tag == "td" and "subtext" in classes:
            self._in_subtext = True
            self._subtext_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture_field and tag == self._capture_end_tag:
            value = normalize_whitespace(" ".join(self._capture_parts))
            if self._current is not None and value:
                if self._capture_field == "rank":
                    rank = _parse_int(value)
                    if rank is not None:
                        self._current["rank"] = rank
                else:
                    self._current[self._capture_field] = value
            self._capture_field = None
            self._capture_end_tag = None
            self._capture_parts = []

        if self._titleline_depth:
            self._titleline_depth -= 1

        if tag == "tr" and self._in_athing:
            self._in_athing = False

        if tag == "td" and self._in_subtext:
            self._current.update(_parse_subtext(" ".join(self._subtext_parts)))
            self._finish_current()
            self._in_subtext = False
            self._subtext_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_field:
            self._capture_parts.append(data)
        if self._in_subtext:
            self._subtext_parts.append(data)

    def _start_capture(self, field: str, end_tag: str) -> None:
        self._capture_field = field
        self._capture_end_tag = end_tag
        self._capture_parts = []

    def _finish_current(self) -> None:
        if not self._current:
            return
        story_id = _int_field(self._current, "id")
        rank = _int_field(self._current, "rank")
        title = str(self._current.get("title") or "").strip()
        if story_id is None or rank is None or not title:
            self._current = None
            return

        raw_url = self._title_href or f"item?id={story_id}"
        url = urljoin(HN_BASE_URL, raw_url)
        self.stories.append(
            Story(
                id=story_id,
                rank=rank,
                title=title,
                url=url,
                hn_url=story_discussion_url(story_id),
                site=_optional_str(self._current.get("site")),
                points=_int_field(self._current, "points"),
                author=_optional_str(self._current.get("author")),
                age=_optional_str(self._current.get("age")),
                comment_count=_int_field(self._current, "comment_count"),
            )
        )
        self._current = None
        self._title_href = None


class HNCommentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.comments: list[Comment] = []
        self._current_author: str | None = None
        self._current_age: str | None = None
        self._capture_field: str | None = None
        self._capture_end_tag: str | None = None
        self._capture_parts: list[str] = []
        self._comment_depth = 0
        self._comment_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = _attrs(attrs)
        classes = _classes(attrs_dict)

        if self._comment_depth:
            self._comment_depth += 1
            if tag in {"br", "p", "div"}:
                self._comment_parts.append("\n")
            return

        if tag == "tr" and "comtr" in classes:
            self._current_author = None
            self._current_age = None
        elif tag == "a" and "hnuser" in classes:
            self._start_capture("author", "a")
        elif tag == "span" and "age" in classes:
            self._start_capture("age", "span")
        elif "commtext" in classes:
            self._comment_depth = 1
            self._comment_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._comment_depth:
            self._comment_depth -= 1
            if self._comment_depth == 0:
                self._finish_comment()
            return

        if self._capture_field and tag == self._capture_end_tag:
            value = normalize_whitespace(" ".join(self._capture_parts))
            if self._capture_field == "author":
                self._current_author = value or None
            elif self._capture_field == "age":
                self._current_age = value or None
            self._capture_field = None
            self._capture_end_tag = None
            self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._comment_depth:
            self._comment_parts.append(data)
        elif self._capture_field:
            self._capture_parts.append(data)

    def _start_capture(self, field: str, end_tag: str) -> None:
        self._capture_field = field
        self._capture_end_tag = end_tag
        self._capture_parts = []

    def _finish_comment(self) -> None:
        text = normalize_whitespace(" ".join(self._comment_parts))
        if text and text != "[dead]" and text != "[flagged]":
            self.comments.append(
                Comment(author=self._current_author, age=self._current_age, text=text)
            )
        self._comment_parts = []


def _parse_subtext(value: str) -> dict[str, object]:
    text = normalize_whitespace(value)
    parsed: dict[str, object] = {}

    points_match = re.search(r"(\d+)\s+points?", text)
    if points_match:
        parsed["points"] = int(points_match.group(1))

    author_match = re.search(r"\bby\s+([^\s|]+)", text)
    if author_match:
        parsed["author"] = author_match.group(1)

    comment_match = re.search(r"(\d+)\s+comments?", text)
    if comment_match:
        parsed["comment_count"] = int(comment_match.group(1))
    elif re.search(r"\bdiscuss\b", text):
        parsed["comment_count"] = 0

    pre_separator = text.split("|", 1)[0].strip()
    pre_separator = re.sub(r"^\d+\s+points?\s*", "", pre_separator)
    pre_separator = re.sub(r"^by\s+[^\s|]+\s*", "", pre_separator)
    if pre_separator:
        parsed["age"] = pre_separator

    return parsed


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


def _classes(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def _parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    if not match:
        return None
    return int(match.group(0))


def _int_field(values: dict[str, object], key: str) -> int | None:
    value = values.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _parse_int(value)
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
