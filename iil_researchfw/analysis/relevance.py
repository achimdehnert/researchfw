"""Relevance scoring for research results."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ScoredResult:
    item: object
    score: float
    reasons: list[str]


class RelevanceScorer:
    """
    Keyword-based relevance scorer.

    Scores items by query term overlap — no ML dependencies.
    """

    def score(
        self,
        query: str,
        items: list[dict[str, str]],
        fields: list[str] | None = None,
    ) -> list[ScoredResult]:
        """Score items by relevance to query."""
        fields = fields or ["title", "abstract", "content", "snippet"]
        stop_words = {"the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at"}
        query_terms = set(query.lower().split()) - stop_words
        weights = {"title": 3.0, "abstract": 2.0, "content": 1.5, "snippet": 1.0}

        scored = []
        for item in items:
            score = 0.0
            reasons: list[str] = []
            for f in fields:
                text = item.get(f, "").lower()
                if not text:
                    continue
                matches = query_terms & set(text.split())
                if matches:
                    field_score = weights.get(f, 1.0) * math.log1p(len(matches))
                    score += field_score
                    reasons.append(f"{f}: {len(matches)} term(s)")
            scored.append(ScoredResult(item=item, score=round(score, 4), reasons=reasons))

        return sorted(scored, key=lambda r: r.score, reverse=True)
