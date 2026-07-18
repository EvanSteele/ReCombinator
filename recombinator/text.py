from __future__ import annotations

import re


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
