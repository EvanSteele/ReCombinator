#!/usr/bin/env python3
"""Create an RSS 2.0 feed from the Hacker News front page briefing.

This script reuses the single-file scraper in hn_briefing.py, then writes the
results as RSS 2.0 XML. It follows the standard RSS shape:

    <rss version="2.0">
      <channel>
        <title>...</title>
        <link>...</link>
        <description>...</description>
        <item>...</item>
      </channel>
    </rss>
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from hn_briefing import HN_NEWS_URL, StoryBrief, build_briefing


CHANNEL_TITLE = "Hacker News Front-Page Briefing"
CHANNEL_DESCRIPTION = (
    "Brief summaries of top Hacker News front-page stories, linked articles, "
    "and sampled HN discussion."
)


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
    generated_at = datetime.now(timezone.utc)
    briefing = build_briefing(
        limit=args.limit,
        max_comments=args.comments,
        max_article_chars=args.article_chars,
        timeout=args.timeout,
        request_delay=args.delay,
    )
    rss = render_rss(briefing, generated_at=generated_at)

    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rss, encoding="utf-8")
    print(f"Wrote {len(briefing)} RSS items to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hn_briefing_rss.py",
        description="Write an RSS 2.0 XML feed from the Hacker News front page.",
    )
    parser.add_argument("output", help="path where the RSS XML file should be written")
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


def render_rss(briefs: list[StoryBrief], *, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '  <channel>',
        f'    <title>{xml_escape(CHANNEL_TITLE)}</title>',
        f'    <link>{xml_escape(HN_NEWS_URL)}</link>',
        f'    <description>{xml_escape(CHANNEL_DESCRIPTION)}</description>',
        '    <language>en-us</language>',
        f'    <lastBuildDate>{xml_escape(format_datetime(generated_at, usegmt=True))}</lastBuildDate>',
        '    <generator>ReCombinator hn_briefing_rss.py</generator>',
        '    <ttl>30</ttl>',
    ]

    for brief in briefs:
        lines.extend(render_item_lines(brief))

    lines.extend(
        [
            "  </channel>",
            "</rss>",
            "",
        ]
    )
    return "\n".join(lines)


def render_item_lines(brief: StoryBrief) -> list[str]:
    story = brief.story
    return [
        "    <item>",
        f"      <title>{xml_escape(story.title)}</title>",
        f"      <link>{xml_escape(story.url)}</link>",
        "      <description>",
        "        <![CDATA[",
        indent_cdata(item_description(brief), spaces=8),
        "        ]]>",
        "      </description>",
        "    </item>",
    ]


def item_description(brief: StoryBrief) -> str:
    story = brief.story
    article_date = story.age or "Date unavailable"
    article_source = story.site or source_from_url(story.url)
    hn_comments = comment_count_label(story.comment_count)
    return "\n\n".join(
        [
            f"{article_date} - {article_source} - {hn_comments}",
            "<br>",
            "<p>Article Summary:</p>",
            f"<p>{html_text(brief.article_summary)}</p>",
            "<p>HN Response:</p>",
            f"<p>{html_text(clean_response_summary(brief.discussion_summary))}</p>",
            "<br>",
            (
                f'<a href="{html_attr(story.url)}">Article</a> -- '
                f'<a href="{html_attr(story.hn_url)}">HN Discussion</a>'
            ),
        ]
    )


def clean_response_summary(value: str) -> str:
    return value.removeprefix("HN discussion highlights: ").strip()


def comment_count_label(comment_count: int | None) -> str:
    if comment_count is None:
        return "HN comments unavailable"
    comment_label = "comment" if comment_count == 1 else "comments"
    return f"{comment_count} HN {comment_label}"


def source_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host.removeprefix("www.") or "Source unavailable"


def xml_escape(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def html_text(value: str) -> str:
    return escape_cdata(escape(value))


def html_attr(value: str) -> str:
    return escape_cdata(escape(value, {'"': "&quot;"}))


def indent_cdata(value: str, spaces: int) -> str:
    padding = " " * spaces
    return "\n".join(f"{padding}{line}" for line in escape_cdata(value).splitlines())


def escape_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


if __name__ == "__main__":
    raise SystemExit(main())
