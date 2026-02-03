from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfluenceReport:
    total_score: float
    components: dict
    recommendation: str


class ConfluenceScorer:
    def __init__(self) -> None:
        self.max_score = 1.0
        self.min_trade_threshold = 0.50
        self.components: dict = {}

    def calculate_score(
        self,
        profile_type: str,
        profile_confidence: float,
        pda_type: str,
        pda_at_entry: bool,
        session_quality: str,
        opening_range_aligned: bool,
        stop_hunt_confirmed: bool,
        news_impact: str,
        adr_remaining_pct: float,
    ) -> float:
        score = 0.0
        self.components = {}

        if not pda_at_entry:
            self.components["pda"] = {"value": 0.0, "required": True, "type": pda_type}
            return 0.0

        pda_weights = {
            "order_block": 0.30,
            "fvg": 0.25,
            "breaker": 0.20,
        }
        pda_factor = pda_weights.get(pda_type, 0.20)
        score += pda_factor
        self.components["pda"] = {"value": pda_factor, "type": pda_type}

        if profile_type and profile_confidence:
            profile_factor = profile_confidence * 0.30
            score += profile_factor
            self.components["profile"] = {"value": profile_factor, "type": profile_type}
        else:
            self.components["profile"] = {"value": 0.0, "type": profile_type}

        if stop_hunt_confirmed:
            score += 0.15
            self.components["stop_hunt"] = {"value": 0.15, "confirmed": True}
        else:
            self.components["stop_hunt"] = {"value": 0.0, "confirmed": False}

        if opening_range_aligned:
            score += 0.10
            self.components["opening_range"] = {"value": 0.10, "aligned": True}
        else:
            self.components["opening_range"] = {"value": 0.0, "aligned": False}

        session_scores = {
            "NY_reversal": 0.10,
            "london_premium": 0.05,
            "london_discount": 0.05,
            "neutral": 0.02,
        }
        session_factor = session_scores.get(session_quality, 0.0)
        score += session_factor
        self.components["session"] = {"value": session_factor, "type": session_quality}

        news_scores = {
            "high_impact": 0.05,
            "medium_impact": 0.02,
            "none": 0.0,
        }
        news_factor = news_scores.get(news_impact, 0.0)
        score += news_factor
        self.components["news"] = {"value": news_factor, "impact": news_impact}

        if adr_remaining_pct > 1.5:
            adr_factor = 0.05
            adr_status = "plenty"
        elif adr_remaining_pct > 1.0:
            adr_factor = 0.02
            adr_status = "moderate"
        else:
            adr_factor = 0.0
            adr_status = "depleted"
        score += adr_factor
        self.components["adr"] = {
            "value": adr_factor,
            "remaining_pct": adr_remaining_pct,
            "status": adr_status,
        }

        return min(score, self.max_score)

    def get_detailed_report(self) -> ConfluenceReport:
        total = sum(c.get("value", 0.0) for c in self.components.values())
        recommendation = "ENTER" if total >= self.min_trade_threshold else "SKIP"
        return ConfluenceReport(total_score=total, components=self.components, recommendation=recommendation)
