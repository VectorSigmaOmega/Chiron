from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.common import NormalizedQuery, SourceDocument, SpecialistTask


class BaseConnector(ABC):
    connector_name: str

    @abstractmethod
    async def search(self, normalized_query: NormalizedQuery, task: SpecialistTask) -> list[SourceDocument]:
        raise NotImplementedError
