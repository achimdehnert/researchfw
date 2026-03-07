"""pytest fixtures and test data for iil-researchfw."""

ARXIV_XML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>Test Paper: Machine Learning Advances</title>
    <author><name>Smith, John</name></author>
    <summary>This paper presents advances in machine learning.</summary>
  </entry>
</feed>
"""

SEMANTIC_SCHOLAR_FIXTURE = {
    "data": [{
        "paperId": "abc123",
        "title": "Deep Learning Survey",
        "authors": [{"name": "LeCun, Yann"}],
        "abstract": "A survey of deep learning methods.",
        "year": 2024,
        "externalIds": {"DOI": "10.1234/dl-survey"},
        "citationCount": 100,
        "openAccessPdf": None,
    }]
}

OPENALEX_FIXTURE = {
    "results": [{
        "id": "https://openalex.org/W123",
        "title": "Transformer Architecture Review",
        "authorships": [{"author": {"display_name": "Vaswani, Ashish"}}],
        "doi": "https://doi.org/10.5678/transformer",
        "publication_year": 2023,
        "cited_by_count": 50,
        "open_access": {"is_oa": False},
        "primary_location": {"source": {"display_name": "NeurIPS"}},
    }]
}

CROSSREF_FIXTURE = {
    "message": {
        "title": ["Test Article Title"],
        "author": [
            {"family": "Smith", "given": "John"},
            {"family": "Doe", "given": "Jane"},
        ],
        "published": {"date-parts": [[2024]]},
        "type": "journal-article",
        "container-title": ["Journal of Testing"],
        "volume": "10", "issue": "2", "page": "100-110",
        "publisher": "Test Publisher",
        "DOI": "10.1234/test",
        "URL": "https://doi.org/10.1234/test",
    }
}
