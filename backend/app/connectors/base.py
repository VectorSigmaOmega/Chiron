from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.common import ParsedQuery, SourceDocument, SpecialistTask


class BaseConnector(ABC):
    connector_name: str

    @abstractmethod
    async def search(self, parsed_query: ParsedQuery, task: SpecialistTask) -> list[SourceDocument]:
        raise NotImplementedError
