from __future__ import annotations

from typing import Protocol


class StrategyInterface(Protocol):
    def identify_setup(self, data) -> bool:
        ...

    def generate_signals(self, data) -> dict:
        ...

    def validate_context(self, data) -> bool:
        ...
