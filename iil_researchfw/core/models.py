"""Pydantic v2 models for iil-researchfw."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    content: str
    source_url: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)


class Source(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    domain: str = ""
    snippet: str = ""
    fetched_at: datetime = Field(default_factory=datetime.now)


class ResearchContext(BaseModel):
    query: str
    domain: str | None = None
    max_sources: int = Field(default=10, ge=1, le=100)
    include_local: bool = False
    language: str = "de"
    filters: dict[str, Any] = Field(default_factory=dict)


class ResearchOutput(BaseModel):
    success: bool
    query: str
    sources: list[Source] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
