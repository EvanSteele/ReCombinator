from __future__ import annotations

import argparse
import sys

from .pipeline import build_briefing
from .report import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recombinator",
        description="Create a concise Markdown briefing from the Hacker News front page.",
    )
    parser.add_argument("--limit", type=int, default=10, help="number of stories to include")
    parser.add_argument(
        "--comments",
        type=int,
        default=8,
        help="maximum comments to sample per story",
    )
    parser.add_argument(
        "--article-chars",
        type=int,
        default=12000,
        help="maximum readable article characters retained per story",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--output", help="write Markdown briefing to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.comments < 0:
        parser.error("--comments must be 0 or greater")
    if args.article_chars < 1000:
        parser.error("--article-chars must be at least 1000")

    briefing = build_briefing(
        limit=args.limit,
        max_comments=args.comments,
        max_article_chars=args.article_chars,
        timeout=args.timeout,
    )
    markdown = render_markdown(briefing)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            output.write(markdown)
            output.write("\n")
    else:
        sys.stdout.write(markdown)
        sys.stdout.write("\n")
    return 0

