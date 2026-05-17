from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.connectors.base import BaseConnector
from app.core.config import Settings, get_settings
from app.schemas.common import ParsedQuery, SourceDocument, SpecialistTask


class GuidelineFixtureConnector(BaseConnector):
    connector_name = "guideline_fixture"

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._records = self._load_records(self.settings.guideline_fixture_path)

    @staticmethod
    def _load_records(path: str) -> list[dict]:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return list(payload.get("guidelines", []))

    async def search(self, parsed_query: ParsedQuery, task: SpecialistTask) -> list[SourceDocument]:
        haystack = " ".join(
            [parsed_query.original_question, parsed_query.rewritten_question, *task.focus_entities]
        ).lower()
        documents: list[SourceDocument] = []
        for record in self._records:
            keywords = [keyword.lower() for keyword in record.get("keywords", [])]
            if keywords and not any(keyword in haystack for keyword in keywords):
                continue
            publication_date = None
            if record.get("publication_date"):
                publication_date = date.fromisoformat(record["publication_date"])
            documents.append(
                SourceDocument(
                    source_id=record["source_id"],
                    source_type="guideline",
                    title=record["title"],
                    url=record["url"],
                    publication_date=publication_date,
                    publisher=record.get("publisher"),
                    abstract=record.get("summary"),
                    full_text=None,
                    metadata={
                        "condition": record.get("condition"),
                        "population": record.get("population"),
                        "source_mode": "fixture",
                    },
                )
            )
        return documents
