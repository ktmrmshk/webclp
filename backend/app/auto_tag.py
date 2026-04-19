"""Heuristic auto-tags from title + summary (no external API)."""

import re
from collections import Counter

# Minimal English + Japanese stopwords for demo; extend as needed
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "have",
        "has",
        "was",
        "are",
        "not",
        "you",
        "your",
        "can",
        "will",
        "our",
        "all",
        "any",
        "its",
        "into",
        "about",
        "more",
        "も",
        "の",
        "に",
        "は",
        "を",
        "た",
        "が",
        "で",
        "て",
        "と",
        "し",
        "な",
        "い",
        "る",
        "う",
        "す",
        "ま",
        "か",
        "そ",
        "あ",
        "へ",
        "や",
        "など",
        "こと",
        "ため",
        "よう",
        "これ",
        "それ",
        "する",
        "ある",
        "いる",
    }
)


def _tokens(text: str) -> list[str]:
    # Latin words
    latin = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    # Japanese runs (2+ chars, no spaces)
    jp = re.findall(r"[\u3040-\u30ff\u3400-\u9fff\u3000-\u303f]{2,}", text)
    out = []
    for w in latin:
        if w not in _STOP:
            out.append(w)
    for w in jp:
        if len(w) >= 2:
            out.append(w[:32])
    return out


def suggest_tags(title: str, summary: str, max_tags: int = 5) -> list[str]:
    blob = f"{title}\n{summary}"
    if not blob.strip():
        return []
    counts = Counter(_tokens(blob))
    return [w for w, _ in counts.most_common(max_tags)]


def suggest_category(title: str, summary: str) -> str | None:
    """Very small keyword → category map; replace with ML later."""
    blob = (title + " " + summary).lower()
    rules = [
        ("tech", ["github", "stackoverflow", "api", "docker", "kubernetes", "python", "javascript"]),
        ("news", ["news", "報道", "新聞", "速報"]),
        ("docs", ["documentation", "docs.", "仕様", "リファレンス"]),
        ("product", ["pricing", "料金", "buy", "購入"]),
    ]
    for cat, keys in rules:
        if any(k in blob for k in keys):
            return cat
    return None
