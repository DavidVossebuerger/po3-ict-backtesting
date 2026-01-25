from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfluenceReport:
    total_score: float
    components: dict
    recommendation: str


class ConfluenceScorer:
    def __init__(self) -> None:
        self.max_score = 5.0
        self.components: dict = {}

    def calculate_score(
        self,
        profile_type: int,
        profile_confidence: float,
        pda_alignment: bool,
        session_quality: str,
        rhrl_active: bool,
        stop_hunt_confirmed: bool,
        news_impact: str,
        adr_remaining_pct: float,
    ) -> float:
        score = 0.0
        self.components = {}

        if profile_type > 0:
            profile_factor = profile_confidence
            score += profile_factor
            self.components["profile"] = {
                "value": profile_factor,
                "weight": "high",
                "rationale": f"Profile {profile_type} active",
            }
        else:
            self.components["profile"] = {
                "value": 0.0,
                "weight": "critical",
                "rationale": "No valid profile (Seek & Destroy)",
            }

        if pda_alignment:
            pda_factor = 0.5
            score += pda_factor
            self.components["pda"] = {"value": pda_factor, "weight": "high"}

        session_scores = {
            "NY_reversal": 0.5,
            "london_premium": 0.25,
            "london_discount": 0.25,
            "asia_volatile": 0.0,
            "neutral": 0.1,
        }
        session_factor = session_scores.get(session_quality, 0.0)
        score += session_factor
        self.components["session"] = {"value": session_factor, "type": session_quality}

        rhrl_factor = 0.5 if rhrl_active else 0.0
        score += rhrl_factor
        self.components["rhrl"] = {"value": rhrl_factor, "active": rhrl_active}

        stop_hunt_factor = 0.5 if stop_hunt_confirmed else 0.0
        score += stop_hunt_factor
        self.components["stop_hunt"] = {"value": stop_hunt_factor, "confirmed": stop_hunt_confirmed}

        news_scores = {
            "high_impact": 0.5,
            "medium_impact": 0.25,
            "low_impact": 0.0,
            "none": 0.0,
        }
        news_factor = news_scores.get(news_impact, 0.0)
        score += news_factor
        self.components["news"] = {"value": news_factor, "impact": news_impact}

        if adr_remaining_pct > 1.5:
            adr_factor = 0.5
            adr_status = "plenty"
        elif adr_remaining_pct > 1.0:
            adr_factor = 0.25
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
        recommendation = "ENTER" if total >= 4.0 else "SKIP"
        return ConfluenceReport(total_score=total, components=self.components, recommendation=recommendation)
