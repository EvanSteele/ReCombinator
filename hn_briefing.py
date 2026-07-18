#!/usr/bin/env python3
"""Create a Markdown briefing from the Hacker News front page.

This is the single-file version of ReCombinator. It uses only Python's standard
library, scrapes the ranked Hacker News front page, fetches linked articles and
HN comments, summarizes the extracted text, and writes Markdown to the output
path supplied on the command line.
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


HN_BASE_URL = "https://news.ycombinator.com/"
HN_NEWS_URL = urljoin(HN_BASE_URL, "news")
DEFAULT_USER_AGENT = (
    "ReCombinator/0.1 (+https://news.ycombinator.com/; "
    "brief personal technology digest)"
)


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int | None
    content_type: str
    text: str


@dataclass(slots=True)
class Story:
    id: int
    rank: int
    title: str
    url: str
    hn_url: str
    site: str | None = None
    points: int | None = None
    author: str | None = None
    age: str | None = None
    comment_count: int | None = None


@dataclass(slots=True)
class Article:
    url: str
    title: str | None = None
    text: str = ""
    fetched: bool = False
    error: str | None = None


@dataclass(slots=True)
class Comment:
    author: str | None
    text: str
    age: str | None = None


@dataclass(slots=True)
class StoryBrief:
    story: Story
    article: Article
    comments: list[Comment] = field(default_factory=list)
    article_summary: str = ""
    discussion_summary: str = ""


STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "and",
    "are",
    "because",
    "been",
    "being",
    "between",
    "but",
    "can",
    "could",
    "from",
    "has",
    "have",
    "how",
    "into",
    "its",
    "more",
    "not",
    "our",
    "over",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}
PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }
)


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
TECH_TERMS = {
    "ai",
    "api",
    "app",
    "cloud",
    "code",
    "compiler",
    "data",
    "database",
    "developer",
    "gpu",
    "hardware",
    "internet",
    "kernel",
    "language",
    "linux",
    "llm",
    "model",
    "network",
    "open",
    "privacy",
    "programming",
    "release",
    "research",
    "security",
    "server",
    "software",
    "startup",
    "system",
    "tool",
    "web",
}
CLUTTER_TERMS = {
    "copy link",
    "share facebook",
    "skip to main content",
    "voice speed",
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.comments < 0:
        parser.error("--comments must be 0 or greater")
    if args.article_chars < 1000:
        parser.error("--article-chars must be at least 1000")
    if args.delay < 0:
        parser.error("--delay must be 0 or greater")

    output_path = Path(args.output).expanduser()
    briefing = build_briefing(
        limit=args.limit,
        max_comments=args.comments,
        max_article_chars=args.article_chars,
        timeout=args.timeout,
        request_delay=args.delay,
    )
    markdown = render_markdown(briefing)

    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown + "\n", encoding="utf-8")
    print(f"Wrote {len(briefing)} stories to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hn_briefing.py",
        description="Write a concise Markdown briefing from the Hacker News front page.",
    )
    parser.add_argument("output", help="path where the Markdown briefing should be written")
    parser.add_argument("--limit", type=int, default=10, help="number of stories to include")
    parser.add_argument(
        "--comments",
        type=int,
        default=8,
        help="maximum HN comments to sample per story",
    )
    parser.add_argument(
        "--article-chars",
        type=int,
        default=12000,
        help="maximum readable article characters retained per story",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="polite delay between stories in seconds",
    )
    return parser


def build_briefing(
    *,
    limit: int = 10,
    max_comments: int = 8,
    max_article_chars: int = 12000,
    timeout: float = 15.0,
    request_delay: float = 0.2,
) -> list[StoryBrief]:
    front_page = fetch_text(HN_NEWS_URL, timeout=timeout)
    stories = parse_front_page(front_page.text, limit=limit)
    briefs: list[StoryBrief] = []

    for story in stories:
        article = fetch_article(story.url, max_article_chars=max_article_chars, timeout=timeout)
        comments = fetch_comments(story.hn_url, limit=max_comments, timeout=timeout)
        briefs.append(brief_story(story, article, comments))
        if request_delay:
            time.sleep(request_delay)

    return briefs


def fetch_text(url: str, timeout: float = 15.0) -> FetchResult:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            headers = response.headers
            encoding = headers.get("Content-Encoding", "").lower()
            content_type = headers.get("Content-Type", "")
            raw = decompress(raw, encoding)
            charset = headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=response.geturl(),
                status=getattr(response, "status", None),
                content_type=content_type,
                text=raw.decode(charset, errors="replace"),
            )
    except HTTPError as error:
        body = error.read()
        body = decompress(body, error.headers.get("Content-Encoding", "").lower())
        charset = error.headers.get_content_charset() or "utf-8"
        return FetchResult(
            url=error.geturl(),
            status=error.code,
            content_type=error.headers.get("Content-Type", ""),
            text=body.decode(charset, errors="replace"),
        )
    except URLError as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(f"Could not fetch {url}: {reason}") from error


def decompress(raw: bytes, encoding: str) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


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
        attrs_dict = attrs_to_dict(attrs)
        classes = classes_from_attrs(attrs_dict)

        if tag == "tr" and "athing" in classes:
            self._finish_current()
            story_id = parse_int(attrs_dict.get("id", ""))
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
                    rank = parse_int(value)
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
            self._current.update(parse_subtext(" ".join(self._subtext_parts)))
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
        story_id = int_field(self._current, "id")
        rank = int_field(self._current, "rank")
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
                site=optional_str(self._current.get("site")),
                points=int_field(self._current, "points"),
                author=optional_str(self._current.get("author")),
                age=optional_str(self._current.get("age")),
                comment_count=int_field(self._current, "comment_count"),
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
        attrs_dict = attrs_to_dict(attrs)
        classes = classes_from_attrs(attrs_dict)

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
        attrs_dict = attrs_to_dict(attrs)
        classes = classes_from_attrs(attrs_dict)

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


def fetch_article(url: str, *, max_article_chars: int, timeout: float) -> Article:
    if not is_http_url(url):
        return Article(url=url, fetched=False, error="not an HTTP URL")
    try:
        result = fetch_text(url, timeout=timeout)
        return extract_article(result.url, result.text, result.content_type, max_chars=max_article_chars)
    except Exception as error:  # Each story should fail independently.
        return Article(url=url, fetched=False, error=str(error))


def fetch_comments(url: str, *, limit: int, timeout: float) -> list[Comment]:
    if limit == 0:
        return []
    try:
        result = fetch_text(url, timeout=timeout)
    except Exception:
        return []
    return parse_comments(result.text, limit=limit)


def extract_article(url: str, html: str, content_type: str = "", max_chars: int = 12000) -> Article:
    if is_reddit_url(url):
        return extract_reddit_article(url, html, max_chars=max_chars)

    if looks_like_html(content_type, html):
        parser = ReadableTextParser()
        parser.feed(html)
        title = normalize_whitespace(parser.title or "") or None
        paragraphs = filter_paragraphs(clean_paragraphs("\n".join(parser.parts)))
        text = "\n\n".join(paragraphs)
    else:
        title = None
        text = "\n\n".join(clean_paragraphs(html))

    return Article(url=url, title=title, text=truncate(text, max_chars), fetched=True)


def is_reddit_url(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return host == "reddit.com" or host.endswith(".reddit.com")


def extract_reddit_article(url: str, html: str, max_chars: int) -> Article:
    parser = RedditSubmissionParser()
    parser.feed(html)
    title = normalize_whitespace(parser.title or "") or title_from_html(html)
    paragraphs = filter_paragraphs(clean_paragraphs("\n".join(parser.selftext_parts)))

    text_parts = []
    if title:
        text_parts.append(title)
    text_parts.extend(paragraphs)
    text = "\n\n".join(text_parts)
    return Article(url=url, title=title, text=truncate(text, max_chars), fetched=True)


def brief_story(story: Story, article: Article, comments: list[Comment]) -> StoryBrief:
    return StoryBrief(
        story=story,
        article=article,
        comments=comments,
        article_summary=summarize_article(story, article),
        discussion_summary=summarize_discussion(story, comments),
    )


def summarize_article(story: Story, article: Article) -> str:
    if not article.text:
        if article.error:
            return f"Article text unavailable: {article.error}"
        return "Article text could not be extracted automatically."

    candidates = sentence_candidates(article.text)
    selected = select_sentences(candidates, keywords(story.title), count=2)
    if not selected:
        return truncate(article.text, 360)
    return truncate(" ".join(selected), 460)


def summarize_discussion(story: Story, comments: list[Comment]) -> str:
    if not comments:
        return "No sampled HN discussion yet."

    comment_text = " ".join(comment.text for comment in comments[:8])
    candidates = sentence_candidates(comment_text)
    selected = select_sentences(candidates, keywords(story.title), count=2)
    if not selected:
        return truncate(comment_text, 300)
    return truncate("HN discussion highlights: " + " ".join(selected), 420)


def sentence_candidates(text: str) -> list[str]:
    candidates = []
    for sentence in split_sentences(text):
        sentence = normalize_whitespace(sentence)
        lowered = sentence.casefold()
        if any(term in lowered for term in CLUTTER_TERMS):
            continue
        if 50 <= len(sentence) <= 320 and has_enough_words(sentence):
            candidates.append(sentence)
    return candidates


def select_sentences(candidates: list[str], title_keywords: set[str], count: int) -> list[str]:
    scored = []
    for index, sentence in enumerate(candidates[:80]):
        sentence_words = set(words(sentence))
        overlap = len(sentence_words & title_keywords)
        tech_overlap = len(sentence_words & TECH_TERMS)
        score = overlap * 4 + tech_overlap * 1.5 + max(0, 8 - index) * 0.3
        if sentence.endswith("?"):
            score -= 0.5
        scored.append((score, index, sentence))

    picked = sorted(scored, reverse=True)[:count]
    picked.sort(key=lambda item: item[1])
    return [sentence for score, index, sentence in picked if score > 0]


def render_markdown(briefs: list[StoryBrief]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Hacker News Front-Page Briefing",
        "",
        f"Generated: {generated_at}",
        f"Source: [{HN_NEWS_URL}]({HN_NEWS_URL})",
        "",
    ]

    for brief in briefs:
        story = brief.story
        lines.extend(
            [
                f"## {story.rank}. [{escape_link_text(story.title)}]({story.url})",
                "",
                metadata_line(brief),
                "",
                f"**Article:** {brief.article_summary}",
                "",
                f"**HN reaction:** {brief.discussion_summary}",
                "",
                f"Links: [article]({story.url}) | [discussion]({story.hn_url})",
                "",
            ]
        )

    return "\n".join(lines).rstrip()


def metadata_line(brief: StoryBrief) -> str:
    story = brief.story
    bits = []
    if story.site:
        bits.append(story.site)
    if story.points is not None:
        bits.append(f"{story.points} points")
    if story.comment_count is not None:
        comment_label = "comment" if story.comment_count == 1 else "comments"
        bits.append(f"{story.comment_count} {comment_label}")
    if story.author:
        bits.append(f"by {story.author}")
    if story.age:
        bits.append(story.age)
    return " | ".join(bits) if bits else "No HN metadata captured"


def escape_link_text(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.translate(PUNCTUATION_TRANSLATION)).strip()


def clean_paragraphs(value: str) -> list[str]:
    paragraphs = []
    seen = set()
    for raw_line in re.split(r"\n{1,}", value):
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        folded = line.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        paragraphs.append(line)
    return paragraphs


def words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_+\-.]{2,}", value.casefold())


def keywords(value: str) -> set[str]:
    return {word for word in words(value) if word not in STOPWORDS and len(word) > 3}


def split_sentences(value: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalize_whitespace(value))
    return [piece.strip() for piece in pieces if piece.strip()]


def truncate(value: str, limit: int) -> str:
    value = normalize_whitespace(value)
    if len(value) <= limit:
        return value
    clipped = value[: max(0, limit - 1)].rstrip()
    last_space = clipped.rfind(" ")
    if last_space > limit * 0.7:
        clipped = clipped[:last_space]
    return f"{clipped}..."


def parse_subtext(value: str) -> dict[str, object]:
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


def looks_like_html(content_type: str, value: str) -> bool:
    lowered = content_type.casefold()
    if "html" in lowered or "xml" in lowered:
        return True
    start = value.lstrip()[:200].casefold()
    return "<html" in start or "<!doctype html" in start


def title_from_html(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    title = re.sub(r"\s*:\s*[^:]+$", "", title)
    return normalize_whitespace(title) or None


def filter_paragraphs(paragraphs: list[str]) -> list[str]:
    filtered = []
    for paragraph in paragraphs:
        paragraph = strip_inline_boilerplate(paragraph)
        lowered = paragraph.casefold()
        if len(paragraph) < 35 and not re.match(r"^#{0,6}\s*[A-Z0-9]", paragraph):
            continue
        if any(re.search(pattern, lowered) for pattern in BOILERPLATE_PATTERNS):
            continue
        if link_farm_like(paragraph):
            continue
        filtered.append(paragraph)
    return filtered


def strip_inline_boilerplate(paragraph: str) -> str:
    cleaned = paragraph
    for pattern in INLINE_BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    return normalize_whitespace(cleaned)


def link_farm_like(paragraph: str) -> bool:
    if len(paragraph) > 240:
        return False
    paragraph_words = paragraph.split()
    if len(paragraph_words) < 8:
        return False
    short_words = sum(1 for word in paragraph_words if len(word) <= 3)
    return short_words / len(paragraph_words) > 0.7


def has_enough_words(sentence: str) -> bool:
    return len(words(sentence)) >= 8


def attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


def classes_from_attrs(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    if not match:
        return None
    return int(match.group(0))


def int_field(values: dict[str, object], key: str) -> int | None:
    value = values.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return parse_int(value)
    return None


def optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
