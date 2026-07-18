from __future__ import annotations

from dataclasses import dataclass, field


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

