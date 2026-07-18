from __future__ import annotations

from .models import Article, Comment, Story, StoryBrief
from .text import keywords, normalize_whitespace, split_sentences, truncate, words


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

    candidates = _sentence_candidates(article.text)
    selected = _select_sentences(candidates, keywords(story.title), count=2)
    if not selected:
        return truncate(article.text, 360)
    return truncate(" ".join(selected), 460)


def summarize_discussion(story: Story, comments: list[Comment]) -> str:
    if not comments:
        return "No sampled HN discussion yet."

    comment_text = " ".join(comment.text for comment in comments[:8])
    candidates = _sentence_candidates(comment_text)
    selected = _select_sentences(candidates, keywords(story.title), count=2)
    if not selected:
        return truncate(comment_text, 300)
    return truncate("HN discussion highlights: " + " ".join(selected), 420)


def _sentence_candidates(text: str) -> list[str]:
    candidates = []
    for sentence in split_sentences(text):
        sentence = normalize_whitespace(sentence)
        lowered = sentence.casefold()
        if any(term in lowered for term in CLUTTER_TERMS):
            continue
        if 50 <= len(sentence) <= 320 and _has_enough_words(sentence):
            candidates.append(sentence)
    return candidates


def _select_sentences(candidates: list[str], title_keywords: set[str], count: int) -> list[str]:
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


def _has_enough_words(sentence: str) -> bool:
    return len(words(sentence)) >= 8
