from __future__ import annotations

import time

from .article import extract_article
from .hn import HN_NEWS_URL, parse_comments, parse_front_page
from .http import fetch_text, is_http_url
from .models import Article, StoryBrief
from .summarizer import brief_story


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
        article = _fetch_article(story.url, max_article_chars=max_article_chars, timeout=timeout)
        comments = _fetch_comments(story.hn_url, limit=max_comments, timeout=timeout)
        briefs.append(brief_story(story, article, comments))
        if request_delay:
            time.sleep(request_delay)

    return briefs


def _fetch_article(url: str, *, max_article_chars: int, timeout: float) -> Article:
    if not is_http_url(url):
        return Article(url=url, fetched=False, error="not an HTTP URL")
    try:
        result = fetch_text(url, timeout=timeout)
        return extract_article(result.url, result.text, result.content_type, max_chars=max_article_chars)
    except Exception as error:  # noqa: BLE001 - each story should fail independently.
        return Article(url=url, fetched=False, error=str(error))


def _fetch_comments(url: str, *, limit: int, timeout: float):
    if limit == 0:
        return []
    try:
        result = fetch_text(url, timeout=timeout)
    except Exception:
        return []
    return parse_comments(result.text, limit=limit)

