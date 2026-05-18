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
        ranked_documents: list[tuple[int, SourceDocument]] = []
        for record in self._records:
            keywords = [keyword.lower() for keyword in record.get("keywords", [])]
            required_keywords = [keyword.lower() for keyword in record.get("required_keywords", [])]
            if required_keywords and not all(keyword in haystack for keyword in required_keywords):
                continue
            overlap = sum(1 for keyword in keywords if keyword in haystack)
            if keywords and overlap == 0:
                continue
            publication_date = None
            if record.get("publication_date"):
                publication_date = date.fromisoformat(record["publication_date"])
            ranked_documents.append(
                (
                    overlap,
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
                    ),
                )
            )
        ranked_documents.sort(
            key=lambda item: (
                item[0],
                item[1].publication_date.toordinal() if item[1].publication_date else 0,
            ),
            reverse=True,
        )
        return [document for _, document in ranked_documents[:1]]
