from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache


@dataclass
class _RunProgressState:
    history: list[dict] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    completed: bool = False


class ProgressBroker:
    def __init__(self) -> None:
        self._runs: dict[str, _RunProgressState] = defaultdict(_RunProgressState)

    def start_run(self, run_id: str) -> None:
        self._runs[run_id] = _RunProgressState()

    def publish(self, run_id: str, event: dict) -> None:
        state = self._runs.setdefault(run_id, _RunProgressState())
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            **event,
        }
        state.history.append(payload)
        for queue in list(state.subscribers):
            queue.put_nowait(payload)

    def finish(self, run_id: str) -> None:
        state = self._runs.setdefault(run_id, _RunProgressState())
        state.completed = True
        for queue in list(state.subscribers):
            queue.put_nowait({"type": "__done__"})

    async def subscribe(self, run_id: str) -> AsyncIterator[dict]:
        state = self._runs.setdefault(run_id, _RunProgressState())
        for event in state.history:
            yield event
        if state.completed:
            return

        queue: asyncio.Queue = asyncio.Queue()
        state.subscribers.append(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield {"type": "heartbeat", "timestamp": datetime.now(UTC).isoformat()}
                    continue
                if event.get("type") == "__done__":
                    break
                yield event
        finally:
            if queue in state.subscribers:
                state.subscribers.remove(queue)


@lru_cache
def get_progress_service() -> ProgressBroker:
    return ProgressBroker()
