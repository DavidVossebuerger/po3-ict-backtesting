from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    def __init__(self, params: dict):
        self.params = params
        self.positions = []

    @abstractmethod
    def generate_signals(self, data) -> dict:
        ...

    @abstractmethod
    def identify_setup(self, data) -> bool:
        ...

    @abstractmethod
    def validate_context(self, data) -> bool:
        ...

    def calculate_position_size(self, account_size: float, risk_per_trade: float, stop_distance: float) -> float:
        if stop_distance <= 0:
            return 0.0
        return (account_size * risk_per_trade) / stop_distance

    def get_confluences(self, data) -> dict:
        return {}
