from __future__ import annotations

from typing import Any


DEFAULT_PIP_SIZE = 0.0001
JPY_PIP_SIZE = 0.01


def normalize_symbol(symbol: str | None) -> str:
    if not symbol:
        return ""
    cleaned = symbol.replace("/", "").upper()
    return cleaned[:6] if len(cleaned) >= 6 else cleaned


def get_pip_size(params: dict[str, Any] | None, symbol: str | None = None) -> float:
    config = params or {}
    symbol_specs = config.get("symbol_specs", {}) or {}
    normalized = normalize_symbol(symbol)
    if normalized and isinstance(symbol_specs, dict):
        spec = symbol_specs.get(normalized)
        if isinstance(spec, dict):
            pip_size = spec.get("pip_size")
            if isinstance(pip_size, (int, float)) and pip_size > 0:
                return float(pip_size)

    default_pip_size = config.get("default_pip_size")
    if isinstance(default_pip_size, (int, float)) and default_pip_size > 0:
        return float(default_pip_size)

    if normalized.endswith("JPY"):
        return JPY_PIP_SIZE
    return DEFAULT_PIP_SIZE


def pips_to_price(pips: float, params: dict[str, Any] | None, symbol: str | None = None) -> float:
    return float(pips) * get_pip_size(params, symbol)


def price_to_pips(price_delta: float, params: dict[str, Any] | None, symbol: str | None = None) -> float:
    pip_size = get_pip_size(params, symbol)
    if pip_size <= 0:
        return 0.0
    return float(price_delta) / pip_size
