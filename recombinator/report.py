from __future__ import annotations

from datetime import datetime, timezone

from .hn import HN_NEWS_URL
from .models import StoryBrief


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
                f"## {story.rank}. [{_escape_link_text(story.title)}]({story.url})",
                "",
                _metadata_line(brief),
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


def _metadata_line(brief: StoryBrief) -> str:
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


def _escape_link_text(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")
