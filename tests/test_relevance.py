"""Tests for RelevanceScorer."""
from iil_researchfw.analysis.relevance import RelevanceScorer


def test_sorted_by_score():
    scorer = RelevanceScorer()
    items = [
        {"title": "Cooking recipes"},
        {"title": "Machine learning NLP", "abstract": "Deep learning transformers"},
        {"title": "Learning algorithms"},
    ]
    results = scorer.score("machine learning", items)
    assert results[0].score >= results[1].score >= results[2].score


def test_empty_query_zero_score():
    scorer = RelevanceScorer()
    results = scorer.score("", [{"title": "Some paper"}])
    assert all(r.score == 0.0 for r in results)
