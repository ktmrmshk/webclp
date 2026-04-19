"""プレーンテキストと Markdown の相互補助（検索用プレーン化など）。"""

from __future__ import annotations

import re


def plain_text_to_markdown(text: str) -> str:
    """拡張機能が送るプレーン本文を、段落区切りを保った Markdown にする。"""
    if not text or not text.strip():
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not parts:
        line = re.sub(r"\s+", " ", text.strip())
        return line
    return "\n\n".join(parts)


def markdown_to_plain_preview(md: str, max_len: int = 50_000) -> str:
    """一覧・検索用に Markdown から大まかなプレーンテキストを得る。"""
    if not md:
        return ""
    t = md
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"[*_~]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_len] if max_len else t
