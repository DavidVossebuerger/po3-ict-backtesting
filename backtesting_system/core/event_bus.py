from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, DefaultDict, List


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict


Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)

    def register(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event: Event) -> None:
        for handler in list(self._handlers.get(event.type, [])):
            handler(event)
